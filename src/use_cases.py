"""Training, reviewed-quote paper approvals and official paper settlement."""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
import json
import sqlite3
import uuid

from src.application_store import Conflict
from src import business_model
from src.inference import compare_weather_scenarios_for_date, get_reference_weather_for_date
from src.paper_execution import utc_now_iso
from src.polymarket_client import PolymarketConnector


class ExtendedUseCases:
    def comparison(self, date, weather, profile, dataset, model_mode='auto', reference_weather=None):
        if reference_weather is not None:
            reference_weather=dict(reference_weather)
            reference_weather.setdefault('precipitation_mm',reference_weather.get('rain_mm',0))
            reference_weather.setdefault('temp_min_c',reference_weather['temp_max_c']-6)
            reference_weather.setdefault('temp_mean_c',(reference_weather['temp_max_c']+reference_weather['temp_min_c'])/2)
        model=self.store.model(include_pipeline=True)
        usable=model and model['accepted'] and model['fingerprint']==business_model.fingerprint(profile,dataset)
        if model_mode=='auto' and usable:
            result=business_model.compare(model,date,weather,reference_weather)
            result['model_note']=model['note']
            return result
        if model_mode=='auto' and dataset['origin']!='synthetic_sample':
            raise Conflict('Train and evaluate this imported sales history before business-specific weather analysis. At least 180 matched daily records are required; a chronological holdout must beat the weekday baseline. You can explicitly select the synthetic demonstration model separately.')
        if not ('london' in profile['location_name'].lower() and 51.28<=profile['latitude']<=51.70 and -.52<=profile['longitude']<=.35):
            raise Conflict('The sample model only covers London. Train a local model on imported sales for this location.')
        result=compare_weather_scenarios_for_date(date,weather,reference_weather=reference_weather,indoor_capacity=profile['indoor_capacity'],outdoor_capacity=profile['outdoor_capacity'],opening_hours=profile['opening_hours']).model_dump(mode='json')
        result['reference_weather']=reference_weather or get_reference_weather_for_date(date)
        result['model_note']='Synthetic pub demonstration model, not a validated forecast for this business. Imported sales are not used by this demonstration; use training and evaluation for business-specific estimates.'
        return result

    def start_training(self):
        with self.store.transaction() as c:
            profile=self.store.state('profile',None,c);dataset=self.store.state('dataset',None,c)
            if not profile or not dataset: raise Conflict('Save a business and select sales data before training.')
            if c.execute("SELECT 1 FROM training_jobs WHERE state='running'").fetchone(): raise Conflict('Training is already running.')
            if dataset['row_count']<180: raise Conflict(f'Training needs at least 180 daily sales records; this import contains {dataset["row_count"]}.')
            job='train_'+uuid.uuid4().hex[:12]
            payload={'stage':'queued','fingerprint':business_model.fingerprint(profile,dataset),'note':'Historical-weather retrieval and chronological evaluation have not completed yet.'}
            c.execute('INSERT INTO training_jobs VALUES (?,?,?,?)',(job,'running',utc_now_iso(),json.dumps(payload)))
            self.store.put(c,'training_job',job)
            self.store.audit(c,'model_training_started',{'job_id':job,'sales_days':dataset['row_count']})
        return job

    def run_training(self, job_id):
        from src.application import live_enabled
        try:
            job=self.store.training_job(job_id)
            profile=self.store.state('profile');dataset=self.store.state('dataset')
            history=business_model.historical_weather(profile,dataset['start_date'],dataset['end_date'],self.store.state('training_weather'),live_enabled())
            with self.store.transaction() as c:
                self.store.put(c,'training_weather',history)
                c.execute('UPDATE training_jobs SET payload=? WHERE id=?',(json.dumps({**job['payload'],'stage':'evaluating','matched_weather_days':len(history['rows'])}),job_id))
            metadata,pipeline=business_model.train_pipeline(profile,dataset,history)
            with self.store.transaction() as c:
                current_profile=self.store.state('profile',None,c);current_dataset=self.store.state('dataset',None,c)
                if not current_profile or not current_dataset or job['payload']['fingerprint']!=business_model.fingerprint(current_profile,current_dataset):
                    raise Conflict('Business or sales changed during training. Run training again for the current selection.')
                c.execute('INSERT INTO business_models VALUES (?,?,?,?,?)',(metadata['id'],metadata['fingerprint'],metadata['created_at'],json.dumps(metadata,allow_nan=False),sqlite3.Binary(pipeline)))
                if metadata['accepted']:
                    complete=self.store.state('setup_complete',False,c)
                    self.store.invalidate(c,'A newly evaluated business model replaced dependent analysis. Reassess pending proposals.')
                    self.store.put(c,'setup_complete',complete)
                    self.store.put(c,'current_model',metadata['id'])
                c.execute("UPDATE training_jobs SET state='complete',payload=? WHERE id=?",(json.dumps({'stage':'complete','model':metadata,'fingerprint':metadata['fingerprint']}),job_id))
                self.store.audit(c,'model_training_completed',{'job_id':job_id,'model_id':metadata['id'],'holdout_pass':metadata['accepted'],'test_mae_gbp':metadata['test_mae_gbp'],'baseline_mae_gbp':metadata['baseline_test_mae_gbp']})
                self.store.notify(c,'model','Business model evaluation completed: '+('holdout passed; ready for analysis.' if metadata['accepted'] else 'holdout did not beat the weekday baseline; model not activated.'),job_id)
        except Exception as exc:
            message=str(exc) if isinstance(exc,Conflict) else 'Training failed during weather retrieval or evaluation. Your sales and previous model are preserved.'
            with self.store.transaction() as c:
                c.execute("UPDATE training_jobs SET state='failed',payload=? WHERE id=?",(json.dumps({'stage':'failed','error':message}),job_id))
                self.store.audit(c,'model_training_failed',{'job_id':job_id,'error':message})
                self.store.notify(c,'model',message,job_id)

    def approve(self, proposal_id, approval):
        # This records a simulated fill at the immutable quote the operator saw.
        # Discovery checks live rules/depth when creating that proposal; approval
        # checks its binding, expiry and current portfolio limits atomically.
        # No live repricing, exchange request or replacement quote is needed.
        return self.store.decide(proposal_id,approval)

    def refresh_settlements(self):
        from src.application import live_enabled
        connector=PolymarketConnector(allow_live_network=live_enabled())
        checked=[];resolved=0
        with self.store._connect() as c:
            positions=[dict(r) for r in c.execute("SELECT p.*,x.market_payload FROM paper_positions p JOIN proposal_context x USING(proposal_id) WHERE p.actual_resolved_outcome NOT IN ('Yes','No','INVALID')")]
        for p in positions:
            if p['data_origin']=='synthetic_test_fixture':
                checked.append({'position_id':p['position_id'],'status':'unresolved','note':'Synthetic fixture has no actual exchange outcome.'});continue
            market=json.loads(p['market_payload']);evidence=connector.resolution(market.get('condition_id'))
            if evidence['status']=='resolved':
                outcomes=market['outcomes'];payouts=[Decimal(v) for v in evidence['payouts']]
                if p['outcome_selected'] not in outcomes or len(outcomes)!=len(payouts):
                    checked.append({'position_id':p['position_id'],'status':'unavailable','note':'Outcome mapping does not match the approved market.'});continue
                share=payouts[outcomes.index(p['outcome_selected'])]
                gbp=(share*Decimal(p['paper_quantity'])/Decimal(str(p['fx_rate_usd_per_gbp']))).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
                winner=outcomes[payouts.index(Decimal(1))] if Decimal(1) in payouts else 'INVALID'
                resolved+=int(self.store.record_settlement(p['position_id'],evidence,float(gbp),winner))
            checked.append({'position_id':p['position_id'],**{k:v for k,v in evidence.items() if k!='evidence'}})
        note=f'Checked {len(positions)} unresolved paper positions; {resolved} new official paper outcomes recorded. No real payouts or redemptions occurred.'
        with self.store.transaction() as c:
            self.store.audit(c,'settlement_refresh_checked',{'result':note,'checks':checked})
            self.store.put(c,'settlement_check',{'checked_at':utc_now_iso(),'note':note,'checks':checked})
        return {'positions':self.snapshot()['positions'],'note':note,'checks':checked,'newly_resolved':resolved}
