"""Public live-data smoke test. All paper/model records use an isolated temp DB.

The sales in this test are explicitly synthetic repository records. It never
submits an exchange order, signs a transaction or accesses a provider account.
"""
import datetime as dt
import json
from pathlib import Path
import tempfile

from src.api_schemas import AnalysisInput, ApprovalInput, ProfileInput
from src.application import WeatherApplication, import_sales, sample_dataset
from src.application_store import ApplicationStore, Conflict


def run():
    evidence={'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'paper_only':True,
        'business_records':'Explicit synthetic repository revenue, not private/real business sales.'}
    with tempfile.TemporaryDirectory(prefix='pub-hedge-real-path-') as directory:
        store=ApplicationStore(Path(directory)/'isolated.db');service=WeatherApplication(store)
        profile=ProfileInput(pubName='Isolated Live Weather Test',postcode='SE22 8HD',owner='Test Operator',email='test@example.com',location_name='London, UK',latitude=51.45,longitude=-.07).model_dump()
        store.set_profile(profile);sample=sample_dataset();store.set_dataset(sample)
        forecast=service.forecast()
        evidence['forecast']={k:v for k,v in forecast.items() if k!='days'}
        tomorrow=dt.datetime.now(dt.timezone.utc).date()+dt.timedelta(days=1)
        aid=service.start_analysis(AnalysisInput(target_date=tomorrow,market_mode='live',weather_mode='manual',temp_max_c=4,rain_mm=0,budget_gbp=100))
        service.run_analysis(aid);analysis=store.analysis(aid)
        evidence['live_assessment']={'state':analysis['state'],'status':analysis['payload'].get('status'),
            'discovery':analysis['payload'].get('discovery'),'spec':analysis['payload'].get('selected_contract_spec'),
            'scenario':'Explicit manual 4°C stress scenario. Synthetic business revenue model; real contracts and books.',
            'inspected_candidates':len(analysis['payload'].get('candidates',[])), 'errors':analysis['payload'].get('error')}
        p=store.get_proposal(analysis['payload'].get('proposal_id',''))
        if p:
            evidence['live_assessment'].update(market_id=p.market_id,quote_timestamp=p.quote_timestamp,rejections=p.rejection_reasons,calculation=p.calculation.model_dump(mode='json') if p.calculation else None)
        if p and p.status=='recommend_paper_hedge':
            approval=ApprovalInput(confirmed_proposal_hash=p.proposal_hash,confirmed_quantity=p.paper_quantity,confirmed_max_cost_gbp=p.max_total_cost_gbp,confirmed_quote_timestamp=p.quote_timestamp,acknowledge_paper_risk=True)
            try: evidence['isolated_paper_approval']=service.approve(p.proposal_id,approval)
            except Conflict as exc: evidence['isolated_paper_approval']={'ok':False,'reason':str(exc)}
            evidence['settlement_refresh']=service.refresh_settlements()
        # Exercise import-to-training against genuinely retrieved historical weather.
        content='date,revenue_gbp,currency\n'+'\n'.join(f'{r["date"]},{r["revenue_gbp"]},GBP' for r in sample['rows'])
        store.set_dataset(import_sales(content,'explicit_synthetic_revenue_training_smoke.csv'))
        job=service.start_training();service.run_training(job);result=store.training_job(job)
        model=result['payload'].get('model')
        evidence['training']={'state':result['state'],'error':result['payload'].get('error'),
            'records_origin':'Repository synthetic revenue deliberately imported for integration verification.',
            'model':{k:v for k,v in (model or {}).items() if k not in ('test_predictions','reference_weather','weekday_means','weather_bounds')}}
    path=Path('docs/implementation-evidence/live-functional-check.json');path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'evidence':str(path),'forecast':evidence['forecast']['origin'],
        'live_assessment':evidence['live_assessment']['status'],'paper_approval':evidence.get('isolated_paper_approval'),
        'training':evidence['training']['state'],'model_accepted':bool(model and model['accepted'])},indent=2))


if __name__=='__main__': run()
