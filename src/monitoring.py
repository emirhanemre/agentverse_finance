"""Opt-in in-process weather monitoring. It can propose, never approve or trade."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import time
import uuid
from zoneinfo import ZoneInfo

from src.api_schemas import AnalysisInput
from src.application_store import Conflict
from src.paper_execution import utc_now_iso


class MonitoringUseCases:
    def monitor_tick(self, force=False):
        now=dt.datetime.now(dt.timezone.utc);tick='monitor_'+uuid.uuid4().hex[:12]
        with self.store.transaction() as c:
            settings=self.store.state('settings',{},c)
            old=self.store.state('monitoring',{},c) or {}
            if not force and not settings.get('monitor_enabled'): return {'status':'disabled','note':'Monitoring is disabled.'}
            if old.get('running') and old.get('lease_until','')>now.isoformat():
                return {**old,'note':'A monitor check is already running.'}
            if not force and old.get('next_run_at','')>now.isoformat(): return old
            current={'id':tick,'running':True,'status':'running','last_run_at':now.isoformat(),
                'lease_until':(now+dt.timedelta(minutes=5)).isoformat(),
                'next_run_at':(now+dt.timedelta(minutes=settings.get('monitor_interval_minutes',30))).isoformat()}
            self.store.put(c,'monitoring',current)
        ledger_key=None
        try:
            profile=self.store.state('profile');dataset=self.store.state('dataset')
            if not profile or not dataset: raise Conflict('Monitoring needs business details and selected sales data.')
            forecast=self.forecast()
            if forecast['origin']!='current_forecast': raise Conflict('Monitoring could not retrieve a current forecast. Cached weather was not used as current evidence.')
            self.refresh_settlements()
            today=dt.datetime.now(ZoneInfo('Europe/London')).date()
            candidates=[]
            for day in forecast['days']:
                delta=(dt.date.fromisoformat(day['date'])-today).days
                if not 1<=delta<=settings.get('monitor_horizon_days',3): continue
                weather={k:day[k] for k in ('temp_max_c','temp_min_c','temp_mean_c','rain_mm','wind_max_kmh','sunshine_hours') if k in day}
                comp=self.comparison(day['date'],weather,profile,dataset)
                candidates.append((comp['estimated_downside_loss_gbp'],day,weather))
            candidates.sort(key=lambda x:x[0],reverse=True)
            if not candidates or candidates[0][0]<=0:
                current.update(status='complete',note='Current forecast has no positive conditional revenue downside within the monitoring horizon.')
            else:
                downside,day,weather=candidates[0]
                revision=self.store.state('revision',0)
                signature=hashlib.sha256(json.dumps({'revision':revision,'date':day['date'],'weather':weather},sort_keys=True).encode()).hexdigest()
                existing=None
                with self.store._connect() as c:
                    for row in c.execute("SELECT p.approval_state,x.expires_at,a.payload FROM proposals p JOIN proposal_context x USING(proposal_id) JOIN analyses a ON a.id=x.analysis_id WHERE x.revision=?",(revision,)):
                        data=json.loads(row['payload'])
                        if data.get('monitor_signature')==signature and (row['approval_state'] in ('approved','rejected') or (row['approval_state']=='pending_human_approval' and row['expires_at']>now.isoformat())):
                            existing=row['approval_state'];break
                ledger_key=signature+'_'+str(int(time.time()//900))
                if existing:
                    current.update(status='complete',note=f'Forecast unchanged; previous proposal is {existing}. No duplicate proposal created.')
                else:
                    with self.store.transaction() as c:
                        already=c.execute('SELECT analysis_id FROM monitor_runs WHERE fingerprint=?',(ledger_key,)).fetchone()
                        if already:
                            current.update(status='complete',note='This forecast has already been assessed in the current quote window.',analysis_id=already[0])
                        else:
                            c.execute('INSERT INTO monitor_runs VALUES (?,?,NULL)',(ledger_key,utc_now_iso()))
                    if not already:
                        budget=min(settings.get('monitor_budget_gbp',100),settings['per_contract_gbp'])
                        inputs=AnalysisInput(target_date=day['date'],weather_mode='forecast',market_mode='live',budget_gbp=budget)
                        aid=self.start_analysis(inputs)
                        with self.store.transaction() as c:
                            row=c.execute('SELECT payload FROM analyses WHERE id=?',(aid,)).fetchone()
                            payload=json.loads(row[0]);payload['monitor_signature']=signature
                            c.execute('UPDATE analyses SET payload=? WHERE id=?',(json.dumps(payload),aid))
                            c.execute('UPDATE monitor_runs SET analysis_id=? WHERE fingerprint=?',(aid,ledger_key))
                        self.run_analysis(aid,forecast_override=forecast)
                        result=self.store.analysis(aid)
                        status=result['payload'].get('status','data_unavailable')
                        current.update(status='complete',analysis_id=aid,note=f'Forecast assessment completed: {status}. Human approval is required for any paper proposal.')
                        with self.store.transaction() as c:
                            self.store.notify(c,'monitor',current['note'],aid+'_monitor')
            current['forecast_retrieved_at']=forecast['retrieved_at']
        except Exception as exc:
            current.update(status='needs_information' if isinstance(exc,Conflict) else 'failed',note=str(exc) if isinstance(exc,Conflict) else 'Monitoring failed while retrieving or analysing data. Existing positions were not changed.')
            with self.store.transaction() as c:
                if ledger_key: c.execute('DELETE FROM monitor_runs WHERE fingerprint=? AND analysis_id IS NULL',(ledger_key,))
                self.store.notify(c,'monitor',current['note'],'monitor_error_'+str(self.store.state('revision',0,c))+'_'+hashlib.sha256(current['note'].encode()).hexdigest()[:12])
        finally:
            current.update(running=False,completed_at=utc_now_iso())
            with self.store.transaction() as c:
                self.store.put(c,'monitoring',current)
                self.store.audit(c,'monitor_check_completed',current)
        return current
