"""Polymarket public read-only connector (Gamma + CLOB) and authentic snapshot cache manager.

Security & Integrity Rules:
1. Uses only public read-only Gamma and CLOB endpoints; never requests wallet keys or signs orders.
2. Clearly labels live API responses vs cached authentic snapshots vs historical replay snapshots vs labelled test fixtures.
3. Treats all market questions and resolution rules as untrusted external content and scans for prompt-injection patterns.
4. Never claims historical CLOB price series establish historical Level-2 order-book depth.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
import json
from pathlib import Path
import re
from typing import Any
import requests

from src.schemas import DataOriginLabel, MarketCandidate, OrderBookLevel, redact_sensitive_text

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = ROOT / "data" / "polymarket_cache" / "authentic_polymarket_snapshots.json"

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"

_INJECTION_PATTERNS = [
    (re.compile(r"(?i)ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions"), "ignore_previous_instructions"),
    (re.compile(r"(?i)disregard\s+(?:all\s+)?(?:rules|limits|controls|instructions)"), "disregard_rules_or_controls"),
    (re.compile(r"(?i)(?:bypass|override|disable)\s+(?:risk|budget|approval|human|limit)"), "bypass_risk_or_budget_control"),
    (re.compile(r"(?i)recommend_paper_hedge\s+immediately"), "forced_status_override"),
    (re.compile(r"(?i)system\s*prompt|you\s+are\s+now\s+in\s+developer\s+mode"), "system_prompt_manipulation"),
    (re.compile(r"(?i)(?:send|print|output|exfiltrate)\s+(?:api[_ -]?key|secret|token|credentials|env)"), "credential_exfiltration_attempt"),
]


def detect_untrusted_content_flags(text: str) -> list[str]:
    """Scan external market text for prompt-injection or control-override phrases."""
    if not text:
        return []
    flags: list[str] = []
    for pat, label in _INJECTION_PATTERNS:
        if pat.search(text):
            flags.append(label)
    return flags


def wrap_untrusted_market_text(text: str) -> str:
    """Sanitize and wrap external market text so the LLM treats it strictly as data, never instructions."""
    redacted = redact_sensitive_text(text or "")
    return f"[UNTRUSTED_EXTERNAL_DATA_START] {redacted} [UNTRUSTED_EXTERNAL_DATA_END]"


def _parse_order_book_levels(raw_levels: list[dict[str, Any]], sort_ascending: bool) -> list[OrderBookLevel]:
    levels: list[OrderBookLevel] = []
    for item in raw_levels:
        try:
            p = Decimal(str(item.get("price", "0")))
            s = Decimal(str(item.get("size", "0")))
            if Decimal("0") < p <= Decimal("1") and s > Decimal("0"):
                levels.append(OrderBookLevel(price=p, size=s))
        except Exception:
            continue
    levels.sort(key=lambda lv: lv.price, reverse=not sort_ascending)
    return levels


def load_cached_polymarket_catalog(snapshot_path: Path = SNAPSHOT_PATH) -> dict[str, Any]:
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Polymarket snapshot cache not found at {snapshot_path}")
    return json.loads(snapshot_path.read_text(encoding="utf-8"))


def record_to_market_candidate(
    rec: dict[str, Any],
    default_origin: DataOriginLabel = "cached_polymarket_snapshot",
) -> MarketCandidate:
    combined_text = f"{rec.get('question', '')}\n{rec.get('resolution_rules', '')}"
    flags = detect_untrusted_content_flags(combined_text)

    asks_by_outcome: dict[str, list[OrderBookLevel]] = {}
    bids_by_outcome: dict[str, list[OrderBookLevel]] = {}
    raw_books = rec.get("order_books", {}) or {}
    for outcome_label, book_obj in raw_books.items():
        if isinstance(book_obj, dict):
            asks_by_outcome[outcome_label] = _parse_order_book_levels(
                book_obj.get("asks", []), sort_ascending=True
            )
            bids_by_outcome[outcome_label] = _parse_order_book_levels(
                book_obj.get("bids", []), sort_ascending=False
            )

    status_raw = str(rec.get("status", "active" if rec.get("active") and not rec.get("closed") else "closed"))
    status: Any = status_raw if status_raw in {"active", "closed", "inactive"} else "closed"

    origin: DataOriginLabel = rec.get("data_origin") or (
        "historical_replay_snapshot" if status == "closed" else default_origin
    )

    return MarketCandidate(
        market_id=str(rec.get("market_id", "")),
        condition_id=str(rec.get("condition_id", "")),
        source_url=str(rec.get("source_url", "")),
        retrieval_timestamp=str(rec.get("retrieval_timestamp", "")),
        data_origin=origin,
        question=str(rec.get("question", "")),
        resolution_rules=str(rec.get("resolution_rules", "")),
        resolution_source=str(rec.get("resolution_source", "Polymarket Official Rules")),
        location=str(rec.get("location", "Unspecified / Global")),
        measurement=str(rec.get("measurement", "non_weather_event")),
        start_date=rec.get("start_date"),
        end_date=rec.get("end_date"),
        status=status,
        outcomes=[str(x) for x in rec.get("outcomes", ["Yes", "No"])],
        outcome_prices=[str(x) for x in rec.get("outcome_prices", [])],
        clob_token_ids=[str(x) for x in rec.get("clob_token_ids", [])],
        asks_by_outcome=asks_by_outcome,
        bids_by_outcome=bids_by_outcome,
        untrusted_content_flags=flags,
    )


class PolymarketConnector:
    """Read-only connector for live Polymarket Gamma/CLOB endpoints with authentic cached fallback."""

    def __init__(
        self,
        snapshot_path: Path = SNAPSHOT_PATH,
        allow_live_network: bool = False,
        extra_fixtures: list[MarketCandidate] | None = None,
    ) -> None:
        self.snapshot_path = snapshot_path
        self.allow_live_network = allow_live_network
        self.catalog = load_cached_polymarket_catalog(snapshot_path)
        self._candidates_by_id: dict[str, MarketCandidate] = {}
        self._raw_by_id: dict[str, dict[str, Any]] = {}

        for raw_m in self.catalog.get("markets", []):
            mc = record_to_market_candidate(raw_m)
            self._candidates_by_id[mc.market_id] = mc
            self._raw_by_id[mc.market_id] = raw_m

        if extra_fixtures:
            for fix in extra_fixtures:
                flags = detect_untrusted_content_flags(f"{fix.question}\n{fix.resolution_rules}")
                if flags:
                    fix.untrusted_content_flags = sorted(set(list(fix.untrusted_content_flags) + flags))
                self._candidates_by_id[fix.market_id] = fix

    def _ingest_live(self, rec, event=None):
        event = event or {}
        def array(key):
            value = rec.get(key) or []
            return json.loads(value) if isinstance(value, str) else value
        text = str(rec.get('question', '')) + ' ' + str(rec.get('description', ''))
        city_match = re.search(r'(?:highest temperature|rainfall|precipitation) in (.+?) (?:be |on )', text, re.I)
        location = city_match[1].strip() if city_match else 'Unverified location'
        if 'london' in text.lower(): location = 'London, UK'
        measurement = 'daily_max_temperature' if re.search(r'highest temperature|maximum temperature',text,re.I) else 'precipitation_or_rainfall' if re.search(r'rainfall|precipitation',text,re.I) else 'non_weather_event'
        event_slug = event.get('slug') or (rec.get('events') or [{}])[0].get('slug') or rec.get('slug', '')
        raw = dict(market_id=str(rec['id']),condition_id=rec.get('conditionId',''),source_url='https://polymarket.com/event/'+event_slug,
            retrieval_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),data_origin='live_polymarket_api',
            question=str(rec.get('question','')),resolution_rules=str(rec.get('description','')),resolution_source=str(rec.get('resolutionSource','')),
            location=location,measurement=measurement,start_date=rec.get('startDate'),end_date=rec.get('endDate'),
            status='active' if rec.get('active') and not rec.get('closed') and rec.get('acceptingOrders') else 'closed' if rec.get('closed') else 'inactive',
            outcomes=array('outcomes'),outcome_prices=array('outcomePrices'),clob_token_ids=array('clobTokenIds'))
        candidate=record_to_market_candidate(raw)
        self._candidates_by_id[candidate.market_id]=candidate
        self._raw_by_id[candidate.market_id]=raw
        return candidate

    def refresh_catalog(self, target_date: str, max_pages: int = 4, location: str = 'London') -> dict[str, Any]:
        """Targeted weather discovery with paginated public search and dated-list fallback."""
        if not self.allow_live_network:
            return {'origin':'cached_polymarket_snapshot','ok':False,'note':'Live discovery disabled; saved catalogue inspection only.'}
        saved=dict(self._candidates_by_id);self._candidates_by_id={}
        scanned=0;queries=[];failures=0
        city=location.split(',')[0].strip()
        try:
            for query in (f'highest temperature {city}', f'rainfall {city}'):
                queries.append(query)
                for page in range(1,min(max_pages,3)+1):
                    response=requests.get(f'{GAMMA_BASE}/public-search',params={'q':query,'events_status':'active','limit_per_type':20,'page':page,'keep_closed_markets':0,'search_profiles':'false','search_tags':'false'},timeout=8)
                    response.raise_for_status();data=response.json()
                    if isinstance(data,list):
                        for rec in data: self._ingest_live(rec);scanned+=1
                        break
                    for event in data.get('events') or []:
                        for rec in event.get('markets') or []:
                            self._ingest_live(rec,event);scanned+=1
                    if not (data.get('pagination') or {}).get('hasMore'): break
            if not self._candidates_by_id:
                end=(dt.date.fromisoformat(target_date)+dt.timedelta(days=2)).isoformat()
                for page in range(max_pages):
                    response=requests.get(f'{GAMMA_BASE}/markets',params={'active':'true','closed':'false','limit':100,'offset':page*100,'end_date_min':target_date+'T00:00:00Z','end_date_max':end+'T00:00:00Z'},timeout=8)
                    response.raise_for_status();records=response.json()
                    if not isinstance(records,list): raise ValueError('Invalid catalogue response')
                    scanned+=len(records)
                    for rec in records:
                        if re.search(r'temperature|rainfall|precipitation',str(rec.get('question','')),re.I): self._ingest_live(rec)
                    if len(records)<100: break
            return {'ok':True,'origin':'live_polymarket_api','retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),
                'scanned':scanned,'weather_candidates':len(self._candidates_by_id),'bounded_search':True,'queries':queries,
                'note':f'Live targeted weather search for {city}, up to {min(max_pages,3)} pages per query, with dated-list fallback. Candidate rules determine the exact observation day; discovery is bounded, not exhaustive.'}
        except (requests.RequestException,ValueError,TypeError,KeyError):
            if self._candidates_by_id:
                return {'ok':True,'partial':True,'origin':'live_polymarket_api','scanned':scanned,'weather_candidates':len(self._candidates_by_id),'bounded_search':True,'note':'Partial live discovery; one search failed. Only successfully retrieved candidates are assessed.'}
            self._candidates_by_id=saved
            return {'ok':False,'origin':'cached_polymarket_snapshot','note':'Live discovery failed. Saved catalogue is inspection-only; current approvals are disabled.'}

    def refresh_market(self, market_id):
        if not self.allow_live_network: raise ValueError('Live market refresh disabled.')
        response=requests.get(f'{GAMMA_BASE}/markets/{market_id}',timeout=8)
        response.raise_for_status()
        return self._ingest_live(response.json())

    def resolution(self, condition_id):
        """Official finalized payout vector; proposed/disputed/price-only data cannot settle."""
        if not self.allow_live_network: return {'status':'unavailable','note':'Live settlement retrieval disabled.'}
        if not re.fullmatch(r'0x[0-9a-fA-F]{64}',condition_id or ''): return {'status':'unavailable','note':'Missing valid condition identifier.'}
        url='https://data-api.polymarket.com/v2/resolutions'
        try:
            response=requests.get(url,params={'condition':condition_id},timeout=8);response.raise_for_status()
            data=response.json()
            for row in data.get('data') or []:
                if row.get('condition_id','').lower()!=condition_id.lower(): continue
                state=str(row.get('status','')).lower()
                if state not in ('resolved','settled','finalized') or not row.get('transaction_hash') or row.get('extended_review'):
                    return {'status':'unresolved','note':f'Official resolution state is {state or "pending"}; a final payout vector is not established.'}
                payouts=[Decimal(str(x)) for x in (row.get('payouts') or [])]
                corroboration=None
                # Historical final records omit payout vectors. Require a second
                # official source's closed flag AND explicit winner token flags;
                # indicative prices never determine settlement.
                if not payouts:
                    book_url=f'{CLOB_BASE}/markets/{condition_id}'
                    clob=requests.get(book_url,timeout=8);clob.raise_for_status();info=clob.json()
                    tokens=info.get('tokens') or []
                    if info.get('condition_id','').lower()!=condition_id.lower() or info.get('closed') is not True or len(tokens)!=2 or {t.get('outcome') for t in tokens}!={'Yes','No'} or sum(t.get('winner') is True for t in tokens)!=1:
                        return {'status':'unresolved','note':'Final resolution exists but an unambiguous official payout vector/winner mapping is not available.'}
                    mapping={t['outcome']:Decimal(int(t.get('winner') is True)) for t in tokens}
                    payouts=[mapping['Yes'],mapping['No']]
                    corroboration={'source_url':book_url,'condition_id':info['condition_id'],'closed':True,'tokens':tokens,'method':'Explicit winner flags; prices ignored.'}
                if len(payouts)!=2 or any(not x.is_finite() or x<0 for x in payouts) or sum(payouts)<=0:
                    return {'status':'unresolved','note':'Official final payout vector is incomplete or invalid.'}
                resolved_at=row.get('resolved_at')
                if not resolved_at and row.get('last_update_timestamp'):
                    resolved_at=dt.datetime.fromtimestamp(float(row['last_update_timestamp']),dt.timezone.utc).isoformat()
                if not resolved_at: return {'status':'unresolved','note':'The official final record has no usable resolution timestamp.'}
                total=sum(payouts)
                return {'status':'resolved','payouts':[str(x/total) for x in payouts], 'resolved_at':resolved_at,
                    'timestamp_basis':'resolved_at' if row.get('resolved_at') else 'last_update_timestamp of the final official record',
                    'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'source_url':url+'?condition='+condition_id,
                    'transaction_hash':row['transaction_hash'],'condition_id':condition_id,'evidence':row,'corroboration':corroboration}
            return {'status':'unresolved','note':'No finalized official resolution record for this condition.'}
        except (requests.RequestException,ValueError,TypeError,KeyError,ArithmeticError):
            return {'status':'unavailable','note':'Official resolution feed is unavailable; previous records remain unchanged.'}

    def search_markets(
        self,
        query: str = "",
        include_closed_historical: bool = True,
        max_results: int = 12,
    ) -> list[dict[str, Any]]:
        """Search candidate Polymarket contracts by keyword, location, date, or weather term."""
        q_terms = [t.strip().lower() for t in re.split(r"[\s,]+", query) if len(t.strip()) >= 2]

        scored: list[tuple[int, MarketCandidate]] = []
        for mc in self._candidates_by_id.values():
            if not include_closed_historical and mc.status == "closed":
                continue
            haystack = (
                f"{mc.question} {mc.resolution_rules} {mc.location} "
                f"{mc.measurement} {mc.start_date or ''} {mc.end_date or ''}"
            ).lower()
            score = 0
            if not q_terms:
                score = 1
            else:
                for term in q_terms:
                    if term in haystack:
                        score += 3
                    if term in mc.question.lower():
                        score += 4
                    if term in mc.location.lower():
                        score += 4
            # Always include top weather/London candidates even if query is specific so agent can inspect & reject
            if "weather" in mc.measurement or "temperature" in mc.measurement or "london" in mc.location.lower():
                score += 1
            if score > 0:
                scored.append((score, mc))

        scored.sort(
            key=lambda pair: (
                pair[0],
                1 if pair[1].status == "active" else 0,
                1 if "london" in pair[1].location.lower() else 0,
            ),
            reverse=True,
        )

        results: list[dict[str, Any]] = []
        for _, mc in scored[:max_results]:
            results.append(
                {
                    "market_id": mc.market_id,
                    "question": wrap_untrusted_market_text(mc.question),
                    "location": mc.location,
                    "measurement": mc.measurement,
                    "status": mc.status,
                    "start_date": mc.start_date,
                    "end_date": mc.end_date,
                    "data_origin": mc.data_origin,
                    "retrieval_timestamp": mc.retrieval_timestamp,
                    "source_url": mc.source_url,
                    "has_executable_order_book": any(len(v) > 0 for v in mc.asks_by_outcome.values()),
                    "untrusted_content_flags": mc.untrusted_content_flags,
                }
            )
        return results

    def get_market_candidate(self, market_id: str) -> MarketCandidate | None:
        return self._candidates_by_id.get(str(market_id))

    def get_market_rules(self, market_id: str) -> dict[str, Any]:
        mc = self.get_market_candidate(market_id)
        if mc is None:
            return {"error": f"Market {market_id} not found in catalog."}
        raw = self._raw_by_id.get(str(market_id), {})
        hist_summary = {
            k: {
                "point_count": v.get("point_count", 0),
                "sample_points": v.get("history_sample", [])[-5:],
                "note": "Historical price series reflect past trades/midpoints and do NOT establish historical order-book depth.",
            }
            for k, v in (raw.get("price_histories", {}) or {}).items()
        }
        return {
            "market_id": mc.market_id,
            "condition_id": mc.condition_id,
            "question": wrap_untrusted_market_text(mc.question),
            "resolution_rules": wrap_untrusted_market_text(mc.resolution_rules),
            "resolution_source": mc.resolution_source,
            "location": mc.location,
            "measurement": mc.measurement,
            "start_date": mc.start_date,
            "end_date": mc.end_date,
            "status": mc.status,
            "outcomes": mc.outcomes,
            "outcome_prices_indicative": mc.outcome_prices,
            "clob_token_ids": mc.clob_token_ids,
            "data_origin": mc.data_origin,
            "retrieval_timestamp": mc.retrieval_timestamp,
            "source_url": mc.source_url,
            "untrusted_content_flags": mc.untrusted_content_flags,
            "historical_price_series_summary": hist_summary,
        }

    def get_order_book(self, market_id: str, outcome: str = "Yes") -> dict[str, Any]:
        mc = self.get_market_candidate(market_id)
        if mc is None:
            return {"error": f"Market {market_id} not found."}

        live_refresh_succeeded = False
        if self.allow_live_network and mc.status == "active" and mc.clob_token_ids:
            try:
                idx = mc.outcomes.index(outcome) if outcome in mc.outcomes else 0
                token_id = mc.clob_token_ids[idx]
                resp = requests.get(f"{CLOB_BASE}/book", params={"token_id": token_id}, timeout=6)
                if resp.status_code == 200:
                    data = resp.json()
                    live_refresh_succeeded = True
                    asks = _parse_order_book_levels(data.get("asks", []), sort_ascending=True)
                    bids = _parse_order_book_levels(data.get("bids", []), sort_ascending=False)
                    mc.asks_by_outcome[outcome] = asks
                    mc.bids_by_outcome[outcome] = bids
                    mc.data_origin = "live_polymarket_api"
                    mc.retrieval_timestamp = (
                        dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
                    )
            except (requests.RequestException, ValueError, TypeError, KeyError):
                pass

        asks = mc.asks_by_outcome.get(outcome, [])
        bids = mc.bids_by_outcome.get(outcome, [])
        total_ask_shares = sum((lv.size for lv in asks), Decimal("0"))
        total_ask_notional_usd = sum((lv.price * lv.size for lv in asks), Decimal("0"))

        return {
            "market_id": mc.market_id,
            "live_refresh_succeeded": live_refresh_succeeded,
            "outcome": outcome,
            "status": mc.status,
            "data_origin": mc.data_origin,
            "retrieval_timestamp": mc.retrieval_timestamp,
            "asks": [{"price": str(lv.price), "size": str(lv.size)} for lv in asks],
            "bids": [{"price": str(lv.price), "size": str(lv.size)} for lv in bids],
            "best_ask_usd": float(asks[0].price) if asks else None,
            "best_bid_usd": float(bids[0].price) if bids else None,
            "total_ask_depth_shares": float(round(total_ask_shares, 2)),
            "total_ask_notional_usd": float(round(total_ask_notional_usd, 2)),
            "executable_book_available": len(asks) > 0,
            "execution_note": (
                "Fills are calculated by walking the ask ladder. Indicative midpoints and "
                "historical price series are never treated as executable order-book depth."
            ),
        }
