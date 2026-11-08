"""Weather paper-trading use cases, independent of HTTP and Nick's presentation."""
from __future__ import annotations

import csv
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
import re
import uuid
from zoneinfo import ZoneInfo

from src.agent import infer_exposure_driver
from src.api_schemas import AnalysisInput
from src.application_store import ApplicationStore, Conflict
from src.business_data import load_pub_dataset
from src.financial_calc import evaluate_candidate_hedge
from src.forecast import retrieve_forecast
from src.inference import compare_weather_scenarios_for_date
from src.paper_execution import utc_now_iso
from src.polymarket_client import PolymarketConnector
from src.risk_controls import check_contract_and_hedge_risk
from src.schemas import HedgeProposalRecord, MarketCandidate, OrderBookLevel
from src.use_cases import ExtendedUseCases
from src.monitoring import MonitoringUseCases
from src.contracts import parse_contract, payoff_direction, event_date
from src.api_schemas import SettingsInput

MODEL_NOTE = ('The sample model is trained on synthetic pub revenue and historical London weather; it is not a validated forecast for this business. '
    'Imported sales can be joined to historical weather and trained/evaluated separately. '
    'All scenario estimates are conditional associations, not proven causal losses. Revenue is not profit margin or cashflow.')


def live_enabled():
    return os.getenv('POLYMARKET_OFFLINE_ONLY', 'false').lower() not in ('true', '1')


def dataset_summary(rows, origin, filename, digest=None):
    monthly = {}
    total = Decimal('0')
    for row in rows:
        money = Decimal(str(row['revenue_gbp']))
        total += money
        month = row['date'][:7]
        monthly[month] = monthly.get(month, Decimal('0')) + money
    return {'origin': origin, 'filename': filename, 'sha256': digest,
        'selected_at': utc_now_iso(), 'row_count': len(rows), 'currency': 'GBP',
        'start_date': rows[0]['date'], 'end_date': rows[-1]['date'],
        'total_revenue_gbp': float(total.quantize(Decimal('.01'))),
        'monthly': [{'month': k, 'revenue_gbp': float(v)} for k, v in sorted(monthly.items())],
        'note': 'Synthetic sample revenue, not real business records.' if origin == 'synthetic_sample' else 'User-supplied sales records; source authenticity is unverified. Import does not train or validate a revenue model.',
        'rows': rows}


def import_sales(text, filename):
    try:
        reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')), strict=True)
        if not reader.fieldnames or set(reader.fieldnames) != {'date', 'revenue_gbp', 'currency'}:
            raise ValueError('CSV must have exactly these columns: date,revenue_gbp,currency. Use daily totals, one row per date.')
        rows, seen = [], set()
        for line, row in enumerate(reader, 2):
            if line > 10001:
                raise ValueError('Maximum 10,000 daily records per import.')
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'Row {line}: wrong number of columns.')
            date = row['date'].strip()
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
                raise ValueError(f'Row {line}: use an ISO date YYYY-MM-DD.')
            try:
                parsed = dt.date.fromisoformat(date)
            except ValueError:
                raise ValueError(f'Row {line}: invalid calendar date.')
            if parsed > dt.datetime.now(ZoneInfo('Europe/London')).date():
                raise ValueError(f'Row {line}: sales records cannot be future dates.')
            if date in seen:
                raise ValueError(f'Row {line}: duplicate date {date}. Combine to one daily total.')
            if row['currency'].strip() != 'GBP':
                raise ValueError(f'Row {line}: currency must be GBP; convert other currencies before import.')
            try:
                amount = Decimal(row['revenue_gbp'].strip())
                if not amount.is_finite() or amount < 0 or amount > 10000000 or amount != amount.quantize(Decimal('.01')):
                    raise InvalidOperation()
            except InvalidOperation:
                raise ValueError(f'Row {line}: revenue_gbp must be a finite, nonnegative amount with at most two decimal places, up to 10,000,000.')
            seen.add(date)
            rows.append({'date': date, 'revenue_gbp': float(amount)})
        if not rows:
            raise ValueError('CSV has no sales records. Include at least one daily total.')
        rows.sort(key=lambda r: r['date'])
        return dataset_summary(rows, 'user_import', filename, hashlib.sha256(text.encode()).hexdigest())
    except csv.Error as exc:
        raise ValueError(f'Invalid CSV: {exc}') from exc


def sample_dataset():
    data = load_pub_dataset()
    rows = [{'date': str(r.date), 'revenue_gbp': float(r.daily_revenue_gbp)} for r in data.itertuples()]
    return dataset_summary(rows, 'synthetic_sample', 'uk_pub_daily_dataset.csv')


def test_market(profile, date, suitable=True):
    """A deliberately fabricated contract, never represented as exchange discovery."""
    location = profile['location_name'] if suitable else 'New York City, US'
    return MarketCandidate(market_id=f'SYNTHETIC_TEST_RAIN_{date}_{"MATCH" if suitable else "MISMATCH"}',
        source_url='', retrieval_timestamp=utc_now_iso(), data_origin='synthetic_test_fixture',
        question=f'[SYNTHETIC TEST] {location}: daily rainfall ≥10mm on {date}?',
        resolution_rules=f'Synthetic fixture only. Fictional business-site gauge, {date} 00:00–24:00 Europe/London. Yes if rainfall >=10mm. No supported actual settlement.',
        resolution_source='Fictional business-site gauge (test fixture)', location=location,
        measurement='precipitation_or_rainfall', start_date=date, end_date=date,
        status='active', outcomes=['Yes','No'], outcome_prices=['0.32','0.68'], clob_token_ids=[],
        asks_by_outcome={'Yes': [OrderBookLevel(price=Decimal('.32'), size=Decimal('10000'))]})


class WeatherApplication(ExtendedUseCases, MonitoringUseCases):
    def __init__(self, store: ApplicationStore):
        self.store = store

    def forecast(self):
        profile = self.store.state('profile')
        if not profile:
            raise Conflict('Save business details before retrieving a forecast.')
        result = retrieve_forecast(profile, self.store.state('forecast'), live_enabled())
        with self.store.transaction() as c:
            if self.store.state('profile', None, c) != profile:
                raise Conflict('Business changed during forecast retrieval. Refresh again.')
            self.store.put(c, 'forecast', result)
            self.store.audit(c, 'forecast_retrieved', {'origin': result['origin'], 'source': result['source']})
        return result

    def start_analysis(self, inputs: AnalysisInput):
        aid = 'run_' + uuid.uuid4().hex[:12]
        with self.store.transaction() as c:
            if c.execute("SELECT 1 FROM analyses WHERE state='running'").fetchone():
                raise Conflict('An analysis is already running. Wait for it to finish.')
            revision = self.store.state('revision', 0, c)
            payload = {'inputs': inputs.model_dump(mode='json'), 'execution_mode': 'Deterministic Python rules + frozen regression model', 'model_note': MODEL_NOTE}
            payload['profile_snapshot'] = self.store.state('profile', None, c)
            c.execute('INSERT INTO analyses VALUES (?,?,?,?,?)', (aid, revision, utc_now_iso(), 'running', json.dumps(payload)))
            self.store.put(c, 'active_analysis', aid)
            self.store.audit(c, 'analysis_started', {'analysis_id': aid})
        return aid

    def run_analysis(self, aid, forecast_override=None):
        record = self.store.analysis(aid)
        payload, revision = record['payload'], record['revision']
        args = AnalysisInput.model_validate(payload['inputs'])
        date = args.target_date.isoformat()
        event = lambda label, detail: self.store.event(aid, label, detail)
        proposal = HedgeProposalRecord(proposal_id='prop_' + uuid.uuid4().hex, proposal_hash='',
            created_at=utc_now_iso(), target_date=date, budget_gbp=args.budget_gbp,
            status='need_information', explanation='')
        market = None
        try:
            profile = self.store.state('profile')
            dataset = self.store.state('dataset')
            settings = self.store.state('settings')
            event('Read persisted business and sales', 'No company or licensing verification is available.')
            if not profile or not dataset:
                proposal.explanation = 'Save business details and select sample sales or import a valid CSV before analysis.'
                self.store.save_assessment(aid, revision, payload, proposal)
                return
            payload['dataset'] = {k:v for k,v in dataset.items() if k not in ('rows','monthly')}
            if date <= dt.datetime.now(ZoneInfo('Europe/London')).date().isoformat() and args.market_mode not in ('test_suitable','test_no_match'):
                proposal.explanation = 'Choose a future exposure date. Historical analysis is available only in the labelled synthetic test mode.'
                self.store.save_assessment(aid, revision, payload, proposal)
                return
            weather = {k: getattr(args, k) for k in ('temp_max_c','rain_mm','wind_max_kmh','sunshine_hours')}
            provenance = {'origin': 'manual_scenario', 'source': 'User-entered scenario', 'retrieved_at': None,
                'note': 'Explicit assumptions, not a forecast or historical observation.', 'units': {'temperature':'°C','rain':'mm','wind':'km/h','sunshine':'h'}}
            if args.weather_mode == 'forecast':
                forecast = forecast_override or self.forecast()
                day = next((x for x in forecast['days'] if x['date'] == date), None)
                if not day or forecast['origin'] != 'current_forecast':
                    proposal.status = 'data_unavailable'
                    proposal.explanation = 'A current forecast for the target date is unavailable. Review the labelled cache or explicitly choose a manual scenario.'
                    payload['weather_provenance'] = forecast
                    self.store.save_assessment(aid, revision, payload, proposal)
                    return
                weather = {k:v for k,v in day.items() if k not in ('date','precipitation_probability_max')}
                provenance = {k:v for k,v in forecast.items() if k != 'days'}
            payload.update(weather=weather, weather_provenance=provenance)
            event('Weather inputs ready', provenance['origin'] + ' · ' + date)
            try:
                comp = self.comparison(date, weather, profile, dataset, args.model_mode)
            except Conflict as exc:
                proposal.explanation = str(exc)
                self.store.save_assessment(aid, revision, payload, proposal)
                return
            payload['comparison'] = comp
            payload['model_note'] = comp['model_note']
            event('Compute conditional revenue scenarios', comp['model_note'])
            connector = PolymarketConnector(allow_live_network=args.market_mode == 'live' and live_enabled())
            if args.market_mode.startswith('test_'):
                market_fixture = test_market(profile, date, args.market_mode == 'test_suitable')
                connector._candidates_by_id = {market_fixture.market_id: market_fixture}
                discovery = {'ok': True, 'origin': 'synthetic_test_fixture', 'note': 'Isolated synthetic contract and order book; not an exchange market.'}
            elif args.market_mode == 'live':
                discovery = connector.refresh_catalog(date, location=profile['location_name'])
            else:
                discovery = {'ok': False, 'origin':'cached_polymarket_snapshot', 'note':'Explicit saved catalogue inspection; current paper approvals disabled.'}
            payload['discovery'] = discovery
            event('Discover and inspect market candidates', discovery['note'])
            rejected, inspected = {}, []
            # Bounded assessment, accurately described. No derived contract probability/EV.
            candidates = connector.search_markets(f"{profile['location_name']} {date} weather", max_results=80)
            def priority(candidate):
                try: return event_date(connector.get_market_candidate(candidate['market_id'])) != date
                except (ValueError, TypeError): return True
            candidates.sort(key=priority)
            component_comparisons = {}
            live_books = 0
            for candidate in candidates:
                mc = connector.get_market_candidate(candidate['market_id'])
                spec = None
                direction = 'Yes'
                candidate_comp = comp
                if mc.data_origin == 'live_polymarket_api' and discovery['ok']:
                    try:
                        spec = parse_contract(mc, profile, settings.get('max_station_distance_km',30))
                        if spec.date != date: raise ValueError(f'Observation date {spec.date} does not match exposure date {date}.')
                        if mc.status != 'active': raise ValueError('Market is not accepting current orders.')
                        if spec.metric == 'daily_max_temperature' and weather['rain_mm'] >= 2 and weather['temp_max_c'] >= comp['reference_weather']['temp_max_c']:
                            raise ValueError('A temperature contract cannot substitute for this rainfall-driven scenario.')
                        if spec.metric == 'precipitation_or_rainfall' and weather['rain_mm'] <= comp['reference_weather'].get('rain_mm',0):
                            raise ValueError('A rainfall contract cannot substitute for this temperature-driven scenario.')
                        metric = spec.metric
                        if metric not in component_comparisons:
                            component_reference = dict(weather)
                            keys = ('rain_mm','precipitation_mm') if metric == 'precipitation_or_rainfall' else ('temp_max_c','temp_min_c','temp_mean_c')
                            for key in keys:
                                if key in comp['reference_weather']: component_reference[key]=comp['reference_weather'][key]
                            component_comparisons[metric]=self.comparison(date,weather,profile,dataset,args.model_mode,component_reference)
                        candidate_comp=component_comparisons[metric]
                        direction=payoff_direction(spec,weather,candidate_comp['reference_weather'])
                        if candidate_comp['estimated_downside_loss_gbp'] <= 0:
                            raise ValueError('This contract metric has no adverse conditional revenue contribution when the other weather inputs are held fixed.')
                        if live_books >= 15: raise ValueError('Bounded assessment reached its 15-book limit; rerun a narrower exposure date/scenario.')
                        live_books += 1
                        mc.measurement = spec.metric
                    except (ValueError,TypeError) as exc:
                        reasons=[str(exc)];rejected[mc.market_id]=reasons
                        inspected.append({'market':mc.model_dump(mode='json'),'risk':{'passed':False,'blocking_reasons':reasons},'contract_spec':spec.to_dict() if spec else None})
                        continue
                book = connector.get_order_book(mc.market_id, direction)
                calc = evaluate_candidate_hedge(mc, direction, date, args.budget_gbp,
                    candidate_comp['scenario_predicted_revenue_gbp'], candidate_comp['reference_predicted_revenue_gbp'],
                    settings['fx_usd_per_gbp'], 'User-configured fixed paper simulation rate; not a live FX quote', settings['fee_bps'])
                risk_driver = ('temperature' if spec.metric=='daily_max_temperature' else 'rainfall') if spec else infer_exposure_driver(weather)
                risk = check_contract_and_hedge_risk(mc, calc, date, risk_driver, args.budget_gbp,
                    max_per_contract_gbp=settings['per_contract_gbp'], max_quote_age_minutes=15,
                    decision_time_utc=utc_now_iso(), allow_cached_or_replay_snapshot=False,
                    business_location=profile['location_name'],contract_event_date=spec.date if spec else None,
                    geography_verified=True if spec else None,payoff_verified=bool(spec))
                reasons = list(risk.blocking_reasons)
                if mc.data_origin not in ('synthetic_test_fixture', 'live_polymarket_api') or not discovery['ok']:
                    reasons.append('Cached/history catalogue is not current discovery or a fresh executable book.')
                if mc.data_origin == 'live_polymarket_api' and not book.get('live_refresh_succeeded'):
                    reasons.append('A current live executable order book could not be retrieved.')
                if comp['estimated_downside_loss_gbp'] <= 0:
                    reasons.append('No adverse conditional revenue downside in this scenario.')
                if mc.data_origin == 'synthetic_test_fixture' and weather['rain_mm'] < 10:
                    reasons.append('Selected rain scenario does not reach this test contract’s 10mm daily threshold.')
                if reasons:
                    risk.passed = False
                    risk.blocking_reasons = reasons
                    rejected[mc.market_id] = reasons
                if spec:
                    risk.warnings.append(spec.basis_note)
                    risk.checks_run['exact_rules_and_payoff_verified']=True
                    calc.basis_risk_summary=spec.basis_note+f' Sizing is capped to the isolated {spec.metric} contribution (£{candidate_comp["estimated_downside_loss_gbp"]:.2f}), holding the other weather inputs fixed; it does not claim to cover the whole combined weather scenario. '+calc.basis_risk_summary
                inspected.append({'market': mc.model_dump(mode='json'), 'risk': risk.model_dump(mode='json'), 'contract_spec':spec.to_dict() if spec else None})
                if not reasons and market is None:
                    market = mc
                    proposal.market_id, proposal.market_question = mc.market_id, mc.question
                    proposal.outcome_selected, proposal.paper_quantity = direction, calc.executable_contracts
                    proposal.max_total_cost_gbp, proposal.quote_timestamp = calc.total_entry_cost_gbp, mc.retrieval_timestamp
                    proposal.data_origin, proposal.calculation, proposal.risk_check = mc.data_origin, calc, risk
                    payload['selected_contract_spec'] = spec.to_dict() if spec else None
            payload['candidates'] = inspected
            proposal.rejection_reasons = rejected
            if market:
                proposal.status = 'recommend_paper_hedge'
                proposal.explanation = ('Labelled synthetic paper scenario' if market.data_origin=='synthetic_test_fixture' else 'Live-discovered weather contract for a paper position')+' passed location/station, date, measurement, rules, payoff direction, quote freshness, depth and budget checks. Payouts remain hypothetical until official resolution. Contract probability and expected value are unavailable.'
            else:
                proposal.status = 'no_suitable_hedge' if candidates or discovery['ok'] else 'data_unavailable'
                proposal.explanation = 'No suitable hedge in the inspected candidates. Review individual rejection reasons. This bounded search does not establish that no market exists elsewhere.' if proposal.status == 'no_suitable_hedge' else 'Current market data is unavailable; saved evidence cannot support a current approval. You can finish setup without a hedge.'
            event('Apply suitability and portfolio limits', proposal.explanation)
            self.store.save_assessment(aid, revision, payload, proposal, market)
            event('Persist assessment', 'Result and proposal saved. Every paper position requires a separate human approval.')
        except Exception as exc:
            # Do not expose upstream URLs, credentials or stack traces to the browser.
            message = str(exc) if isinstance(exc, Conflict) else 'Analysis failed because a required calculation or data source was unavailable. Check backend logs and retry.'
            import logging
            logging.getLogger(__name__).warning('Analysis %s failed (%s)', aid, type(exc).__name__)
            with self.store.transaction() as c:
                payload.update(status='data_unavailable', error=message)
                c.execute("UPDATE analyses SET state='failed',payload=? WHERE id=?", (json.dumps(payload), aid))
                self.store.audit(c, 'analysis_failed', {'analysis_id': aid, 'error': message})
            event('Analysis failed', message)

    def snapshot(self):
        with self.store.transaction() as c:
            state = {k: self.store.state(k, None, c) for k in ('profile','settings','revision','setup_complete','forecast','latest_analysis','active_analysis')}
            state['setup_complete'] = bool(state['setup_complete'])
            dataset = self.store.state('dataset', None, c)
            state['dataset'] = {k:v for k,v in dataset.items() if k != 'rows'} if dataset else None
            risk = self.store.exposure(c)
            contexts = {r['proposal_id']:dict(r) for r in c.execute('SELECT * FROM proposal_context')}
            positions = [dict(r) for r in c.execute('SELECT * FROM paper_positions ORDER BY approved_at DESC')]
            for position in positions:
                original = c.execute('SELECT a.payload FROM analyses a JOIN proposal_context x ON x.analysis_id=a.id WHERE x.proposal_id=?', (position['proposal_id'],)).fetchone()
                snapshot = json.loads(original['payload']).get('profile_snapshot') if original else None
                position['business_name'] = snapshot.get('pubName') if snapshot else 'Legacy paper record'
                settlement=c.execute('SELECT * FROM settlements WHERE position_id=?',(position['position_id'],)).fetchone()
                position['resolution']=({**dict(settlement),'evidence':json.loads(settlement['payload'])} if settlement else None)
                if position['resolution']: position['resolution'].pop('payload',None)
            proposals = []
            now = utc_now_iso()
            for r in c.execute('SELECT * FROM proposals WHERE proposal_id IN (SELECT proposal_id FROM proposal_context) ORDER BY created_at DESC,rowid DESC'):
                p = json.loads(r['payload_json'])
                p['approval_state'] = r['approval_state']
                ctx = contexts[r['proposal_id']]
                p['expires_at'] = ctx['expires_at']
                p['expired'] = ctx['expires_at'] <= now or ctx['revision'] != state['revision']
                analysis_row=c.execute('SELECT payload FROM analyses WHERE id=?',(ctx['analysis_id'],)).fetchone()
                details=json.loads(analysis_row[0]) if analysis_row else {}
                p['contract_spec']=details.get('selected_contract_spec')
                p['model_note']=details.get('model_note',MODEL_NOTE)
                p['source_url']=json.loads(ctx['market_payload']).get('source_url')
                proposals.append(p)
            audits = [dict(r) for r in c.execute('SELECT * FROM audit_log ORDER BY id DESC LIMIT 100')]
            for event in audits:
                event['details'] = json.loads(event.pop('details_json'))
            notifications=[dict(r) for r in c.execute('SELECT * FROM notifications ORDER BY id DESC LIMIT 50')]
            demo_sources=self.store.state('demo_sources',{},c)
            monitoring=self.store.state('monitoring',None,c)
        aid = state['active_analysis'] or state['latest_analysis']
        latest = self.store.analysis(aid) if aid else None
        pending = [p for p in proposals if p['approval_state'] == 'pending_human_approval' and not p['expired']]
        model=self.store.model()
        model_note=model['note'] if model and model['accepted'] else MODEL_NOTE
        if dataset and dataset['origin']!='synthetic_sample' and not model:
            model_note='Imported sales are ready for training and chronological evaluation. Business-specific predictions require an evaluated model; the synthetic demonstration is a separate explicit choice. Revenue is not profit or cashflow.'
        resolutions=[p['resolution'] for p in positions if p['resolution']]
        return {**state, 'analysis': latest, 'proposals': proposals, 'positions': positions, 'activity': audits,
            'business_model':model,'training_job':self.store.training_job(),'monitoring':monitoring,'notifications':notifications,
            'sources': [{'id': n.lower().replace(' ','_'), 'name': n, 'status': 'demo_connected' if n.lower().replace(' ','_') in demo_sources else 'demo_available', 'note': 'Visual connection demo only. No account access or records imported.'} for n in ('Toast','Monzo','Xero','Companies House')]+[{'id':'licensing','name':'Licensing','status':'unavailable','note':'External verification is not performed.'}],
            'summary': {**risk, 'open_positions': len([p for p in positions if p['actual_resolved_outcome'] not in ('Yes','No','INVALID')]),
                'total_entry_cost_gbp': round(sum(p['total_entry_cost_gbp'] for p in positions),2),
                'hypothetical_payout_gbp': round(sum(p['hypothetical_payout_if_win_gbp'] for p in positions if p['actual_resolved_outcome'] not in ('Yes','No','INVALID')),2),
                'pending_approvals': len(pending), 'settled_payout_gbp': round(sum(r['payout_gbp'] for r in resolutions),2) if resolutions else None,
                'realized_paper_pnl_gbp':round(sum(r['net_pnl_gbp'] for r in resolutions),2) if resolutions else None},
            'execution_mode': 'Deterministic Python rules + '+('evaluated business regression' if model and model['accepted'] else 'synthetic demonstration regression'), 'model_note': model_note}
