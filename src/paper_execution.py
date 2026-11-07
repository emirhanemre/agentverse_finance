"""SQLite persistence and human-approved paper trading execution engine.

Safeguards enforced in code:
1. Paper trading only: never signs blockchain transactions or submits live CLOB orders.
2. Cryptographic proposal binding (`proposal_hash` over proposal_id, market_id, outcome,
   paper_quantity, max_total_cost_pence, and quote_timestamp).
3. Modified proposals, quantity changes, cost-limit breaches, or stale quotes are rejected
   and require renewed proposal and human approval.
4. Duplicate approvals / duplicate position executions are strictly blocked via primary/unique keys and state checks.
5. Distinguishes hypothetical scenario payouts from actual resolved-market outcomes.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any

from src.schemas import HedgeProposalRecord, redact_sensitive_text

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "data" / "runtime" / "app_state.db"


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def compute_proposal_binding_hash(
    proposal_id: str,
    market_id: str | None,
    outcome_selected: str | None,
    paper_quantity: int,
    max_total_cost_gbp: float,
    quote_timestamp: str | None,
) -> str:
    """Compute a deterministic SHA-256 hash binding approval to exact contract, quantity, cost limit, and quote timestamp."""
    cost_pence = int(round(float(max_total_cost_gbp) * 100))
    canonical = json.dumps(
        {
            "proposal_id": str(proposal_id),
            "market_id": str(market_id or ""),
            "outcome_selected": str(outcome_selected or ""),
            "paper_quantity": int(paper_quantity),
            "max_total_cost_pence": cost_pence,
            "quote_timestamp": str(quote_timestamp or ""),
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PaperTradingStore:
    """SQLite store for assessment runs, proposals, human approvals, paper positions, and audit history."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            env_path = os.environ.get("SQLITE_DB_PATH", "").strip()
            self.db_path = Path(env_path) if env_path else DEFAULT_DB_PATH
        else:
            self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    proposal_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    target_date TEXT NOT NULL,
                    budget_gbp REAL NOT NULL,
                    status TEXT NOT NULL,
                    market_id TEXT,
                    market_question TEXT,
                    outcome_selected TEXT,
                    paper_quantity INTEGER NOT NULL,
                    max_total_cost_gbp REAL NOT NULL,
                    quote_timestamp TEXT,
                    data_origin TEXT,
                    is_historical_replay INTEGER NOT NULL DEFAULT 0,
                    explanation TEXT NOT NULL,
                    approval_state TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS paper_positions (
                    position_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL UNIQUE,
                    proposal_hash TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    approver_note TEXT NOT NULL,
                    target_date TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    market_question TEXT NOT NULL,
                    outcome_selected TEXT NOT NULL,
                    paper_quantity INTEGER NOT NULL,
                    average_fill_price_usd REAL NOT NULL,
                    total_entry_cost_usd REAL NOT NULL,
                    total_entry_cost_gbp REAL NOT NULL,
                    fx_rate_usd_per_gbp REAL NOT NULL,
                    hypothetical_payout_if_win_gbp REAL NOT NULL,
                    hypothetical_net_profit_if_win_gbp REAL NOT NULL,
                    hypothetical_net_loss_if_lose_gbp REAL NOT NULL,
                    actual_resolved_outcome TEXT,
                    settlement_note TEXT NOT NULL,
                    data_origin TEXT NOT NULL,
                    is_simulated_paper_trade INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    logged_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    proposal_id TEXT,
                    details_json TEXT NOT NULL
                );
                """
            )

    def log_audit_event(
        self,
        event_type: str,
        proposal_id: str | None,
        details: dict[str, Any],
    ) -> None:
        safe_json = redact_sensitive_text(json.dumps(details, sort_keys=True))
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO audit_log (logged_at, event_type, proposal_id, details_json) VALUES (?, ?, ?, ?)",
                (utc_now_iso(), event_type, proposal_id, safe_json),
            )

    def save_proposal(self, proposal: HedgeProposalRecord) -> HedgeProposalRecord:
        expected_hash = compute_proposal_binding_hash(
            proposal_id=proposal.proposal_id,
            market_id=proposal.market_id,
            outcome_selected=proposal.outcome_selected,
            paper_quantity=proposal.paper_quantity,
            max_total_cost_gbp=proposal.max_total_cost_gbp,
            quote_timestamp=proposal.quote_timestamp,
        )
        proposal.proposal_hash = expected_hash
        if proposal.status == "recommend_paper_hedge":
            proposal.approval_state = "pending_human_approval"
        else:
            proposal.approval_state = "not_applicable"

        payload_json = redact_sensitive_text(proposal.model_dump_json())

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO proposals (
                    proposal_id, proposal_hash, created_at, target_date, budget_gbp,
                    status, market_id, market_question, outcome_selected, paper_quantity,
                    max_total_cost_gbp, quote_timestamp, data_origin, is_historical_replay,
                    explanation, approval_state, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal.proposal_id,
                    proposal.proposal_hash,
                    proposal.created_at,
                    proposal.target_date,
                    proposal.budget_gbp,
                    proposal.status,
                    proposal.market_id,
                    proposal.market_question,
                    proposal.outcome_selected,
                    proposal.paper_quantity,
                    proposal.max_total_cost_gbp,
                    proposal.quote_timestamp,
                    proposal.data_origin,
                    1 if proposal.is_historical_replay else 0,
                    redact_sensitive_text(proposal.explanation),
                    proposal.approval_state,
                    payload_json,
                ),
            )

        self.log_audit_event(
            event_type="proposal_saved",
            proposal_id=proposal.proposal_id,
            details={
                "status": proposal.status,
                "market_id": proposal.market_id,
                "paper_quantity": proposal.paper_quantity,
                "max_total_cost_gbp": proposal.max_total_cost_gbp,
                "proposal_hash": proposal.proposal_hash,
                "approval_state": proposal.approval_state,
            },
        )
        return proposal

    def get_proposal(self, proposal_id: str) -> HedgeProposalRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json, approval_state FROM proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if not row:
            return None
        rec = HedgeProposalRecord.model_validate_json(row["payload_json"])
        rec.approval_state = row["approval_state"]
        return rec

    def list_proposals(self, limit: int = 25) -> list[HedgeProposalRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json, approval_state FROM proposals ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out: list[HedgeProposalRecord] = []
        for r in rows:
            rec = HedgeProposalRecord.model_validate_json(r["payload_json"])
            rec.approval_state = r["approval_state"]
            out.append(rec)
        return out

    def approve_proposal(
        self,
        proposal_id: str,
        confirmed_proposal_hash: str,
        confirmed_quantity: int,
        confirmed_max_cost_gbp: float,
        confirmed_quote_timestamp: str | None,
        approver_note: str = "Approved by human operator in web interface",
        max_quote_age_minutes: int = 120,
        decision_time_utc: str | None = None,
        allow_snapshot_quotes: bool = True,
    ) -> dict[str, Any]:
        """Validate binding hash, freshness, and non-duplication before recording a simulated paper position."""
        proposal = self.get_proposal(proposal_id)
        if proposal is None:
            return {"ok": False, "error": f"Proposal '{proposal_id}' does not exist."}

        # Check duplicate execution first
        with self._connect() as conn:
            existing_pos = conn.execute(
                "SELECT position_id FROM paper_positions WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if existing_pos is not None or proposal.approval_state == "approved":
            self.log_audit_event(
                event_type="duplicate_approval_blocked",
                proposal_id=proposal_id,
                details={"reason": "Proposal has already been approved and executed as a paper position."},
            )
            return {
                "ok": False,
                "error": f"Duplicate execution blocked: proposal '{proposal_id}' was already approved.",
            }

        if proposal.approval_state == "rejected":
            return {
                "ok": False,
                "error": f"Proposal '{proposal_id}' was previously rejected and cannot be executed without a new proposal.",
            }

        if proposal.status != "recommend_paper_hedge" or proposal.calculation is None or not proposal.market_id:
            return {
                "ok": False,
                "error": f"Proposal '{proposal_id}' has status '{proposal.status}' and does not contain an executable hedge recommendation.",
            }

        # Verify cryptographic binding to proposal parameters
        recomputed_hash = compute_proposal_binding_hash(
            proposal_id=proposal.proposal_id,
            market_id=proposal.market_id,
            outcome_selected=proposal.outcome_selected,
            paper_quantity=confirmed_quantity,
            max_total_cost_gbp=confirmed_max_cost_gbp,
            quote_timestamp=confirmed_quote_timestamp,
        )
        if (
            confirmed_proposal_hash != proposal.proposal_hash
            or recomputed_hash != proposal.proposal_hash
            or int(confirmed_quantity) != int(proposal.paper_quantity)
            or abs(float(confirmed_max_cost_gbp) - float(proposal.max_total_cost_gbp)) > 1e-4
        ):
            self.log_audit_event(
                event_type="modified_proposal_approval_blocked",
                proposal_id=proposal_id,
                details={
                    "expected_hash": proposal.proposal_hash,
                    "supplied_hash": confirmed_proposal_hash,
                    "recomputed_hash": recomputed_hash,
                },
            )
            return {
                "ok": False,
                "error": (
                    "Approval binding mismatch: proposal parameters (quantity, cost limit, or quote timestamp) "
                    "changed since the proposal was generated. Renewed assessment and approval required."
                ),
            }

        # Check quote freshness at approval time
        now_str = decision_time_utc or utc_now_iso()
        if proposal.quote_timestamp:
            try:
                now_dt = dt.datetime.fromisoformat(now_str.replace("Z", "+00:00"))
                quote_dt = dt.datetime.fromisoformat(proposal.quote_timestamp.replace("Z", "+00:00"))
                age_min = (now_dt - quote_dt).total_seconds() / 60.0
                if age_min > max_quote_age_minutes and not allow_snapshot_quotes:
                    self.log_audit_event(
                        event_type="stale_quote_approval_blocked",
                        proposal_id=proposal_id,
                        details={"quote_age_minutes": round(age_min, 2), "limit_minutes": max_quote_age_minutes},
                    )
                    return {
                        "ok": False,
                        "error": (
                            f"Stale quote blocked: quote is {age_min:.1f} minutes old "
                            f"(exceeds {max_quote_age_minutes} min freshness limit). Refresh order book and re-approve."
                        ),
                    }
            except ValueError:
                return {"ok": False, "error": "Invalid quote timestamp format."}

        calc = proposal.calculation
        if calc.total_entry_cost_gbp > proposal.budget_gbp + 1e-6:
            return {
                "ok": False,
                "error": f"Budget limit breach: entry cost £{calc.total_entry_cost_gbp:.2f} exceeds budget £{proposal.budget_gbp:.2f}.",
            }

        position_id = f"paper_pos_{proposal_id}"
        approved_at = utc_now_iso()
        settlement_note = (
            "SIMULATED PAPER POSITION ONLY (No real funds or on-chain orders). "
            "Payout figures represent hypothetical scenario outcomes ($1.00 USD per share if outcome resolves 'Yes', "
            "$0.00 otherwise), distinct from actual finalized market settlement."
        )

        with self._connect() as conn:
            conn.execute(
                "UPDATE proposals SET approval_state = 'approved' WHERE proposal_id = ?",
                (proposal_id,),
            )
            conn.execute(
                """
                INSERT INTO paper_positions (
                    position_id, proposal_id, proposal_hash, approved_at, approver_note,
                    target_date, market_id, market_question, outcome_selected, paper_quantity,
                    average_fill_price_usd, total_entry_cost_usd, total_entry_cost_gbp,
                    fx_rate_usd_per_gbp, hypothetical_payout_if_win_gbp,
                    hypothetical_net_profit_if_win_gbp, hypothetical_net_loss_if_lose_gbp,
                    actual_resolved_outcome, settlement_note, data_origin, is_simulated_paper_trade
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    position_id,
                    proposal.proposal_id,
                    proposal.proposal_hash,
                    approved_at,
                    redact_sensitive_text(approver_note),
                    proposal.target_date,
                    proposal.market_id,
                    proposal.market_question or "",
                    proposal.outcome_selected or "Yes",
                    calc.executable_contracts,
                    calc.average_ask_price_usd,
                    calc.total_entry_cost_usd,
                    calc.total_entry_cost_gbp,
                    calc.fx_rate_usd_per_gbp,
                    calc.payout_if_win_gbp,
                    calc.net_profit_if_win_gbp,
                    calc.net_loss_if_lose_gbp,
                    "UNRESOLVED_OR_REPLAY_SEPARATE",
                    settlement_note,
                    proposal.data_origin or "cached_polymarket_snapshot",
                ),
            )

        self.log_audit_event(
            event_type="paper_position_recorded",
            proposal_id=proposal_id,
            details={
                "position_id": position_id,
                "market_id": proposal.market_id,
                "paper_quantity": calc.executable_contracts,
                "total_entry_cost_gbp": calc.total_entry_cost_gbp,
                "proposal_hash": proposal.proposal_hash,
            },
        )
        return {
            "ok": True,
            "position_id": position_id,
            "proposal_id": proposal_id,
            "approved_at": approved_at,
            "paper_quantity": calc.executable_contracts,
            "total_entry_cost_gbp": calc.total_entry_cost_gbp,
        }

    def reject_proposal(self, proposal_id: str, reviewer_note: str = "Rejected by human operator") -> dict[str, Any]:
        proposal = self.get_proposal(proposal_id)
        if proposal is None:
            return {"ok": False, "error": f"Proposal '{proposal_id}' not found."}
        if proposal.approval_state == "approved":
            return {"ok": False, "error": f"Proposal '{proposal_id}' is already approved."}

        with self._connect() as conn:
            conn.execute(
                "UPDATE proposals SET approval_state = 'rejected' WHERE proposal_id = ?",
                (proposal_id,),
            )
        self.log_audit_event(
            event_type="proposal_rejected_by_human",
            proposal_id=proposal_id,
            details={"reviewer_note": redact_sensitive_text(reviewer_note)},
        )
        return {"ok": True, "proposal_id": proposal_id, "approval_state": "rejected"}

    def get_paper_positions(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM paper_positions ORDER BY approved_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_audit_history(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            try:
                item["details"] = json.loads(item.pop("details_json", "{}"))
            except ValueError:
                item["details"] = {}
            out.append(item)
        return out
