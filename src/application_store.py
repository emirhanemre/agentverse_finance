"""Application persistence and atomic paper approvals for a single local operator.

SQLite's write lock serializes profile changes, reservations, decisions and approvals.
All application mutations share this database, including the retained paper store.
"""
from __future__ import annotations

from contextlib import contextmanager
import datetime as dt
import json
import sqlite3
from typing import Any
from zoneinfo import ZoneInfo

from src.api_schemas import SettingsInput
from src.paper_execution import PaperTradingStore, compute_proposal_binding_hash, utc_now_iso
from src.schemas import HedgeProposalRecord


class Conflict(ValueError):
    pass


class ApplicationStore(PaperTradingStore):
    def _init_schema(self):
        super()._init_schema()
        with self._connect() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY, revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                    state TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS proposal_context (
                    proposal_id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    expires_at TEXT NOT NULL, market_payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, analysis_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, label TEXT NOT NULL, detail TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS business_models (
                    id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, created_at TEXT NOT NULL,
                    metadata TEXT NOT NULL, pipeline BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS training_jobs (
                    id TEXT PRIMARY KEY, state TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settlements (
                    position_id TEXT PRIMARY KEY, resolved_at TEXT NOT NULL, checked_at TEXT NOT NULL,
                    payout_gbp REAL NOT NULL, net_pnl_gbp REAL NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
                    category TEXT NOT NULL, message TEXT NOT NULL, read_at TEXT, dedup_key TEXT UNIQUE);
                CREATE TABLE IF NOT EXISTS monitor_runs (
                    fingerprint TEXT PRIMARY KEY, created_at TEXT NOT NULL, analysis_id TEXT);
            """)
            c.execute("INSERT OR IGNORE INTO app_state VALUES ('settings', ?)", (SettingsInput().model_dump_json(),))
            c.execute("INSERT OR IGNORE INTO app_state VALUES ('revision', '0')")

    @contextmanager
    def transaction(self):
        c = self._connect()
        c.execute("PRAGMA busy_timeout=15000")
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def state(self, key, default=None, conn=None):
        if conn is None:
            with self._connect() as c:
                return self.state(key, default, c)
        row = conn.execute("SELECT payload FROM app_state WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, c, key, value):
        c.execute("INSERT INTO app_state VALUES (?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload", (key, json.dumps(value, allow_nan=False)))

    def audit(self, c, event, details, proposal_id=None):
        c.execute("INSERT INTO audit_log(logged_at,event_type,proposal_id,details_json) VALUES (?,?,?,?)", (utc_now_iso(), event, proposal_id, json.dumps(details)))

    def invalidate(self, c, reason):
        self.put(c, 'revision', self.state('revision', 0, c) + 1)
        self.put(c, 'latest_analysis', None)
        self.put(c, 'active_analysis', None)
        self.put(c, 'setup_complete', False)
        c.execute("UPDATE proposals SET approval_state='rejected' WHERE approval_state='pending_human_approval'")
        self.audit(c, 'dependent_results_invalidated', {'reason': reason})

    def set_profile(self, profile):
        with self.transaction() as c:
            old = self.state('profile', None, c)
            if old != profile:
                self.put(c, 'current_model', None)
                self.put(c, 'training_job', None)
                self.put(c, 'company', None)
                self.invalidate(c, 'Business details changed. Reassess before approval.')
                if old and any(old.get(k) != profile.get(k) for k in ('latitude', 'longitude', 'location_name')):
                    self.put(c, 'forecast', None)
                if old and any(old.get(k) != profile.get(k) for k in ('pubName', 'postcode')):
                    self.put(c, 'dataset', None)
                    self.put(c, 'operating_costs', None)
                    self.put(c, 'forecast', None)
                self.put(c, 'profile', profile)
                self.audit(c, 'profile_saved', {'name': profile['pubName'], 'verification': 'self_reported'})
        return profile

    def set_dataset(self, dataset):
        with self.transaction() as c:
            self.put(c, 'current_model', None)
            self.put(c, 'training_job', None)
            self.invalidate(c, 'Sales data selection changed.')
            self.put(c, 'dataset', dataset)
            self.audit(c, 'sales_data_selected', {k:v for k,v in dataset.items() if k != 'rows'})

    def set_settings(self, settings):
        with self.transaction() as c:
            previous=self.state('settings', {}, c)
            if previous != settings:
                financial=('weekly_spend_gbp','monthly_loss_gbp','per_contract_gbp','fx_usd_per_gbp','fee_bps','max_station_distance_km')
                if any(previous.get(k)!=settings.get(k) for k in financial):
                    self.invalidate(c, 'Risk limits or simulation assumptions changed.')
                self.put(c, 'settings', settings)
                self.audit(c, 'settings_saved', settings)
        return settings

    def set_operating_costs(self, costs):
        with self.transaction() as c:
            if not self.state('profile', None, c):
                raise Conflict('Save business details before editing operating costs.')
            self.put(c, 'operating_costs', costs)
            self.audit(c, 'operating_cost_assumptions_saved', {'origin':'demo_cost_assumptions', **costs})
        return costs

    def event(self, analysis_id, label, detail):
        with self._connect() as c:
            c.execute("INSERT INTO task_events(analysis_id,created_at,label,detail) VALUES (?,?,?,?)", (analysis_id, utc_now_iso(), label, detail))

    def analysis(self, analysis_id):
        with self._connect() as c:
            row = c.execute('SELECT * FROM analyses WHERE id=?', (analysis_id,)).fetchone()
            if not row:
                return None
            events = [dict(x) for x in c.execute('SELECT * FROM task_events WHERE analysis_id=? ORDER BY id', (analysis_id,))]
        return {**dict(row), 'payload': json.loads(row['payload']), 'events': events}

    def exposure(self, c, now=None, exclude=None):
        """Spend = entry costs approved since London Monday. Loss allowance = all
        current-month entry costs plus earlier unresolved cost. No hypothetical
        payout credits this allowance. Pending, unexpired approvals
        reserve cost against both limits. These are conservative portfolio measures.
        """
        now = now or dt.datetime.now(dt.timezone.utc)
        local = now.astimezone(ZoneInfo('Europe/London'))
        week = (local - dt.timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        month = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        weekly = monthly = 0
        for p in c.execute('SELECT * FROM paper_positions'):
            cost = round(p['total_entry_cost_gbp'] * 100)
            if dt.datetime.fromisoformat(p['approved_at']) >= week:
                weekly += cost
            unresolved = p['actual_resolved_outcome'] not in ('Yes', 'No', 'INVALID')
            if unresolved:
                monthly += cost
            elif dt.datetime.fromisoformat(p['approved_at']) >= month:
                monthly += cost
            else:
                settlement = c.execute('SELECT resolved_at,net_pnl_gbp FROM settlements WHERE position_id=?', (p['position_id'],)).fetchone()
                if settlement and dt.datetime.fromisoformat(settlement['resolved_at'].replace('Z','+00:00')) >= month:
                    monthly += max(0, round(-settlement['net_pnl_gbp'] * 100))
        for p in c.execute("""SELECT p.* FROM proposals p JOIN proposal_context x USING(proposal_id)
                WHERE p.approval_state='pending_human_approval' AND x.expires_at>? AND p.proposal_id!=?""", (now.isoformat(), exclude or '')):
            cost = round(p['max_total_cost_gbp'] * 100)
            weekly += cost
            monthly += cost
        return {'weekly_reserved_gbp': weekly / 100, 'monthly_reserved_loss_gbp': monthly / 100}

    def save_assessment(self, analysis_id, revision, payload, proposal, market=None):
        with self.transaction() as c:
            if revision != self.state('revision', 0, c):
                raise Conflict('Business, data or settings changed during analysis. Run it again.')
            if proposal.status == 'recommend_paper_hedge':
                settings = self.state('settings', {}, c)
                exposure = self.exposure(c)
                cost = proposal.max_total_cost_gbp
                concentration = sum(round(r[0] * 100) for r in c.execute("SELECT total_entry_cost_gbp FROM paper_positions WHERE market_id=? AND actual_resolved_outcome NOT IN ('Yes','No','INVALID')", (proposal.market_id,)))
                concentration += sum(round(r[0] * 100) for r in c.execute("SELECT p.max_total_cost_gbp FROM proposals p JOIN proposal_context x USING(proposal_id) WHERE p.market_id=? AND p.approval_state='pending_human_approval' AND x.expires_at>?", (proposal.market_id, dt.datetime.now(dt.timezone.utc).isoformat())))
                if (exposure['weekly_reserved_gbp'] + cost > settings['weekly_spend_gbp'] + .001 or
                        exposure['monthly_reserved_loss_gbp'] + cost > settings['monthly_loss_gbp'] + .001 or
                        concentration + round(cost*100) > round(settings['per_contract_gbp']*100)):
                    proposal.status = 'no_suitable_hedge'
                    proposal.explanation = 'Accumulated positions and pending approvals exhaust the weekly spending, monthly worst-case loss or per-contract concentration limit.'
                    proposal.rejection_reasons['portfolio'] = [proposal.explanation]
            proposal.approval_state = 'pending_human_approval' if proposal.status == 'recommend_paper_hedge' else 'not_applicable'
            proposal.proposal_hash = compute_proposal_binding_hash(proposal.proposal_id, proposal.market_id, proposal.outcome_selected, proposal.paper_quantity, proposal.max_total_cost_gbp, proposal.quote_timestamp)
            # Immutable insertion; no replace/upsert can reset a human decision.
            c.execute("""INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                proposal.proposal_id, proposal.proposal_hash, proposal.created_at, proposal.target_date,
                proposal.budget_gbp, proposal.status, proposal.market_id, proposal.market_question,
                proposal.outcome_selected, proposal.paper_quantity, proposal.max_total_cost_gbp,
                proposal.quote_timestamp, proposal.data_origin, int(proposal.is_historical_replay),
                proposal.explanation, proposal.approval_state, proposal.model_dump_json()))
            expiry = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15)).isoformat()
            c.execute('INSERT INTO proposal_context VALUES (?,?,?,?,?)', (proposal.proposal_id, analysis_id, revision, expiry, market.model_dump_json() if market else '{}'))
            payload.update(status=proposal.status, proposal_id=proposal.proposal_id, expires_at=expiry)
            c.execute("UPDATE analyses SET state='complete', payload=? WHERE id=?", (json.dumps(payload), analysis_id))
            self.put(c, 'latest_analysis', analysis_id)
            self.audit(c, 'analysis_completed', {'analysis_id': analysis_id, 'status': proposal.status}, proposal.proposal_id)
            if proposal.status == 'recommend_paper_hedge':
                self.notify(c, 'approval', f'Weather paper proposal for {proposal.target_date} needs your approval (£{proposal.max_total_cost_gbp:.2f}).', proposal.proposal_id)

    def decide(self, proposal_id, approval=None, note='Rejected by human operator'):
        with self.transaction() as c:
            row = c.execute('SELECT * FROM proposals WHERE proposal_id=?', (proposal_id,)).fetchone()
            ctx = c.execute('SELECT * FROM proposal_context WHERE proposal_id=?', (proposal_id,)).fetchone()
            if not row or not ctx:
                raise Conflict('Application proposal not found.')
            p = HedgeProposalRecord.model_validate_json(row['payload_json'])
            if row['approval_state'] != 'pending_human_approval':
                raise Conflict('Proposal already decided or not executable. No duplicate paper position recorded.')
            if approval is None:
                c.execute("UPDATE proposals SET approval_state='rejected' WHERE proposal_id=?", (proposal_id,))
                self.audit(c, 'proposal_rejected_by_human', {'note': note}, proposal_id)
                return {'ok': True, 'approval_state': 'rejected'}
            now = dt.datetime.now(dt.timezone.utc)
            if ctx['revision'] != self.state('revision', 0, c) or now >= dt.datetime.fromisoformat(ctx['expires_at']):
                raise Conflict('Proposal expired or its inputs changed. Renew assessment and approval.')
            data = approval.model_dump()
            binding = compute_proposal_binding_hash(proposal_id, p.market_id, p.outcome_selected, data['confirmed_quantity'], data['confirmed_max_cost_gbp'], data['confirmed_quote_timestamp'])
            if binding != p.proposal_hash or data['confirmed_proposal_hash'] != p.proposal_hash:
                raise Conflict('Approval binding mismatch. Renew assessment for changed quantity, cost or quote.')
            try:
                quote = dt.datetime.fromisoformat(p.quote_timestamp.replace('Z', '+00:00'))
                age = (now - quote).total_seconds()
                if not 0 <= age <= 900:
                    raise ValueError()
            except (ValueError, TypeError, AttributeError):
                raise Conflict('Stale or invalid quote. Refresh analysis and approve again.')
            if p.data_origin not in ('live_polymarket_api', 'synthetic_test_fixture'):
                raise Conflict('Cached and historical markets cannot create current paper positions.')
            calc = p.calculation
            if not calc or not p.risk_check or not p.risk_check.passed or calc.executable_contracts != p.paper_quantity or abs(calc.total_entry_cost_gbp - p.max_total_cost_gbp) > .001 or calc.total_entry_cost_gbp > p.budget_gbp:
                raise Conflict('Calculation or risk binding failed. Run a new assessment.')
            settings = self.state('settings', {}, c)
            risk = self.exposure(c, now, proposal_id)
            cost = calc.total_entry_cost_gbp
            if cost > settings['per_contract_gbp'] or risk['weekly_reserved_gbp'] + cost > settings['weekly_spend_gbp'] + .001 or risk['monthly_reserved_loss_gbp'] + cost > settings['monthly_loss_gbp'] + .001:
                raise Conflict('Accumulated portfolio risk limit exceeded. Reassess with a lower budget.')
            # Concentration includes positions and other active reservations in this market.
            existing = sum(round(x[0] * 100) for x in c.execute("SELECT total_entry_cost_gbp FROM paper_positions WHERE market_id=? AND actual_resolved_outcome NOT IN ('Yes','No','INVALID')", (p.market_id,)))
            existing += sum(round(x[0]*100) for x in c.execute("SELECT p.max_total_cost_gbp FROM proposals p JOIN proposal_context x USING(proposal_id) WHERE market_id=? AND approval_state='pending_human_approval' AND expires_at>? AND p.proposal_id!=?", (p.market_id, now.isoformat(), proposal_id)))
            if existing + round(cost * 100) > round(settings['per_contract_gbp'] * 100):
                raise Conflict('Accumulated per-contract concentration limit exceeded.')
            position_id = 'paper_pos_' + proposal_id
            c.execute("""INSERT INTO paper_positions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""", (
                position_id, proposal_id, p.proposal_hash, now.isoformat(), 'Human approved in local web application',
                p.target_date, p.market_id, p.market_question, p.outcome_selected, p.paper_quantity,
                calc.average_ask_price_usd, calc.total_entry_cost_usd, cost, calc.fx_rate_usd_per_gbp,
                calc.payout_if_win_gbp, calc.net_profit_if_win_gbp, calc.net_loss_if_lose_gbp,
                'UNRESOLVED', 'Simulated fill at the reviewed assessment quote; no live execution or repricing. Hypothetical payout until official settlement.', p.data_origin))
            c.execute("UPDATE proposals SET approval_state='approved' WHERE proposal_id=?", (proposal_id,))
            self.audit(c, 'paper_position_recorded', {'position_id': position_id, 'cost_gbp': cost, 'data_origin': p.data_origin, 'fill_basis':'reviewed_assessment_quote', 'quote_timestamp':p.quote_timestamp}, proposal_id)
            return {'ok': True, 'position_id': position_id, 'approval_state': 'approved'}

    def notify(self, c, category, message, dedup_key):
        c.execute('INSERT OR IGNORE INTO notifications(created_at,category,message,dedup_key) VALUES (?,?,?,?)', (utc_now_iso(), category, message, dedup_key))

    def model(self, model_id=None, include_pipeline=False):
        model_id = model_id or self.state('current_model')
        with self._connect() as c:
            row = c.execute('SELECT * FROM business_models WHERE id=?', (model_id,)).fetchone()
        if not row: return None
        data = json.loads(row['metadata'])
        if include_pipeline: data['pipeline_bytes'] = row['pipeline']
        return data

    def training_job(self, job_id=None):
        job_id=job_id or self.state('training_job')
        with self._connect() as c:
            row=c.execute('SELECT * FROM training_jobs WHERE id=?',(job_id,)).fetchone()
        return {**dict(row),'payload':json.loads(row['payload'])} if row else None

    def record_settlement(self, position_id, evidence, payout_gbp, outcome):
        with self.transaction() as c:
            p=c.execute('SELECT * FROM paper_positions WHERE position_id=?',(position_id,)).fetchone()
            if not p: raise Conflict('Paper position not found.')
            previous=c.execute('SELECT payload FROM settlements WHERE position_id=?',(position_id,)).fetchone()
            if previous:
                if json.loads(previous[0])['payouts']!=evidence['payouts']:
                    self.notify(c,'settlement_conflict','A previously recorded official payout changed. Review the source; the original paper ledger was retained.','conflict_'+position_id)
                return False
            net=round(payout_gbp-p['total_entry_cost_gbp'],2)
            c.execute('INSERT INTO settlements VALUES (?,?,?,?,?,?)',(position_id,evidence['resolved_at'],evidence['checked_at'],payout_gbp,net,json.dumps(evidence)))
            note='Resolved paper simulation from official Polymarket payout vector. No real payout or exchange redemption occurred. '+evidence['source_url']
            c.execute('UPDATE paper_positions SET actual_resolved_outcome=?,settlement_note=? WHERE position_id=?',(outcome,note,position_id))
            self.audit(c,'paper_position_resolved',{'position_id':position_id,'paper_payout_gbp':payout_gbp,'paper_net_pnl_gbp':net,'source':evidence['source_url']},p['proposal_id'])
            self.notify(c,'settlement',f'Paper position resolved: payout £{payout_gbp:.2f}; net paper P&L £{net:.2f}. No money moved.','settlement_'+position_id)
            return True
