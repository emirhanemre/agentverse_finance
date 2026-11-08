"""Real-path contract/training/settlement/monitor tests; transport fixtures are labelled tests."""
from copy import deepcopy
import datetime as dt
import json
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.contracts import parse_contract, payoff_direction
from src.polymarket_client import PolymarketConnector
from src.application import import_sales

PROFILE=dict(pubName='Weather Feature Test Pub',postcode='SE22 8HD',owner='Test Operator',email='test@example.com',location_name='London, UK',latitude=51.45,longitude=-.07)


class Response:
    status_code=200
    def __init__(self,data): self.data=data
    def raise_for_status(self): pass
    def json(self): return deepcopy(self.data)


def live_record(date=None):
    date=date or (dt.datetime.now(dt.timezone.utc).date()+dt.timedelta(days=2))
    return {'id':'live_test_weather','conditionId':'0x'+'1'*64,'slug':'test-london-temperature','question':f'Will the highest temperature in London be 6°C or below on {date.strftime("%B")} {date.day}?',
        'description':f'This market resolves to the highest temperature at London City Airport (EGLC) on {date.day} {date.strftime("%b")} \'{date.strftime("%y")}. The qualifying value uses routine METAR observations, excludes SPECI, and uses the hourly temperature remark in Celsius. Values are rounded to the nearest whole degree, with exactly half rounded up to the next higher whole degree. Observation timestamps use the station local time including daylight saving. The following-day resolution source URL is authoritative.',
        'resolutionSource':'https://aviationweather.gov/api/data/metar?ids=EGLC&date='+(date+dt.timedelta(days=1)).isoformat(),
        'endDate':date.isoformat()+'T12:00:00Z','active':True,'closed':False,'acceptingOrders':True,
        'outcomes':'["Yes","No"]','outcomePrices':'["0.32","0.68"]','clobTokenIds':'["yes_token","no_token"]'}


class Transport:
    def __init__(self, record=None):
        self.record=record or live_record();self.price='.32';self.size='10000';self.resolved=False;self.resolution_status='resolved';self.payouts=[0,1];self.review=False
    def __call__(self,url,params=None,**kwargs):
        if url.endswith('/public-search'):
            return Response({'events':[{'slug':'test-weather-event','markets':[self.record]}] if 'temperature' in params['q'] else [],'pagination':{'hasMore':False}})
        if '/markets/' in url: return Response(self.record)
        if url.endswith('/book'): return Response({'asks':[{'price':self.price,'size':self.size}],'bids':[]})
        if url.endswith('/v2/resolutions'):
            return Response({'data':[{'condition_id':self.record['conditionId'],'status':self.resolution_status,'payouts':self.payouts,'extended_review':self.review,'resolved_at':dt.datetime.now(dt.timezone.utc).isoformat(),'transaction_hash':'0x'+'a'*64}] if self.resolved else []})
        raise AssertionError('Unexpected test transport URL '+url)


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('POLYMARKET_OFFLINE_ONLY','false')
    with TestClient(create_app(tmp_path/'features.db')) as c:
        c.put('/api/profile',json=PROFILE);c.post('/api/sources/sample')
        yield c


def assessment(client,date=None,**values):
    date=date or dt.datetime.now(dt.timezone.utc).date()+dt.timedelta(days=2)
    response=client.post('/api/analyses',json={'target_date':date.isoformat(),'market_mode':'live','temp_max_c':4,'rain_mm':0,**values})
    assert response.status_code==202,response.text
    return client.get('/api/analyses/'+response.json()['id']).json()


def proposal(client): return client.get('/api/state').json()['proposals'][0]


def approval(p):
    return {'confirmed_proposal_hash':p['proposal_hash'],'confirmed_quantity':p['paper_quantity'],'confirmed_max_cost_gbp':p['max_total_cost_gbp'],'confirmed_quote_timestamp':p['quote_timestamp'],'acknowledge_paper_risk':True}


def test_supported_rule_parser_day_station_rounding_and_direction():
    market=PolymarketConnector()._ingest_live(live_record())
    spec=parse_contract(market,PROFILE)
    assert spec.date==market.end_date[:10] # not the following-day URL
    assert spec.station=='EGLC' and 0<spec.station_distance_km<30
    assert spec.matches({'temp_max_c':6.49})
    assert not spec.matches({'temp_max_c':6.5})
    assert payoff_direction(spec,{'temp_max_c':5},{'temp_max_c':11})=='Yes'
    assert payoff_direction(spec,{'temp_max_c':11},{'temp_max_c':5})=='No'
    spec.lower=spec.upper=-8
    assert spec.matches({'temp_max_c':-8.5}) # half upward, not away from zero
    market.resolution_rules=market.resolution_rules.replace('half rounded up','half rounded down')
    with pytest.raises(ValueError,match='rounding'): parse_contract(market,PROFILE)


@pytest.mark.parametrize('change,reason',[
    ({'resolution_source':'https://aviationweather.gov.attacker.example/data'},'source'),
    ({'resolution_rules':'London City Airport (EGLC) routine METAR temperature'},'local'),
    ({'resolution_rules':'EGLC and EGLL local time highest temperature'},'exactly one'),
])
def test_ambiguous_rules_fail_with_specific_reasons(change,reason):
    market=PolymarketConnector()._ingest_live(live_record()).model_copy(update=change)
    with pytest.raises(ValueError,match=reason): parse_contract(market,PROFILE)


def test_real_rule_matching_approval_and_recorded_resolution(client):
    transport=Transport()
    with patch('src.polymarket_client.requests.get',side_effect=transport):
        result=assessment(client)
        assert result['payload']['status']=='recommend_paper_hedge',result['payload']
        p=proposal(client)
        assert p['data_origin']=='live_polymarket_api' and p['contract_spec']['station']=='EGLC'
        assert 'structured rule verification; not available' not in p['explanation']
        approved=client.post(f'/api/proposals/{p["proposal_id"]}/approve',json=approval(p))
        assert approved.status_code==200,approved.text
        assert len(client.get('/api/positions').json())==1
        transport.resolved=True
        outcome=client.post('/api/positions/refresh').json()
        assert outcome['newly_resolved']==1
        state=client.get('/api/state').json()
        assert state['positions'][0]['actual_resolved_outcome']=='No'
        assert state['positions'][0]['resolution']['payout_gbp']==0
        assert state['summary']['open_positions']==0
        assert state['summary']['settled_payout_gbp']==0
        assert state['summary']['realized_paper_pnl_gbp']==-p['max_total_cost_gbp']
        assert client.post('/api/positions/refresh').json()['newly_resolved']==0


@pytest.mark.parametrize('mutation',['price','rules','status','depth','offline'])
def test_paper_approval_records_reviewed_quote_without_repricing(client,mutation,monkeypatch):
    transport=Transport()
    with patch('src.polymarket_client.requests.get',side_effect=transport) as network:
        assessment(client);p=proposal(client)
        assert p['status']=='recommend_paper_hedge'
        if mutation=='price': transport.price='.5'
        elif mutation=='rules': transport.record['description']+=' Official rule clarification.'
        elif mutation=='status': transport.record['closed']=True
        elif mutation=='depth': transport.size='1'
        else: monkeypatch.setenv('POLYMARKET_OFFLINE_ONLY','true')
        calls=network.call_count
        network.side_effect=AssertionError('Paper approval must not call the exchange')
        result=client.post(f'/api/proposals/{p["proposal_id"]}/approve',json=approval(p))
        assert result.status_code==200,result.text
        assert network.call_count==calls
        position=client.get('/api/positions').json()[0]
        assert position['paper_quantity']==p['paper_quantity']
        assert position['total_entry_cost_gbp']==p['max_total_cost_gbp']
        assert position['average_fill_price_usd']==p['calculation']['average_ask_price_usd']
        assert 'reviewed assessment quote' in position['settlement_note']
        assert client.post(f'/api/proposals/{p["proposal_id"]}/approve',json=approval(p)).status_code==409
        assert len(client.get('/api/positions').json())==1


@pytest.mark.parametrize('status,review',[('proposed',False),('disputed',False),('resolved',True)])
def test_nonfinal_resolution_never_books_paper_payout(client,status,review):
    transport=Transport()
    with patch('src.polymarket_client.requests.get',side_effect=transport):
        assessment(client);p=proposal(client)
        assert client.post(f'/api/proposals/{p["proposal_id"]}/approve',json=approval(p)).status_code==200
        transport.resolved=True;transport.resolution_status=status;transport.review=review
        assert client.post('/api/positions/refresh').json()['newly_resolved']==0
        assert client.get('/api/state').json()['summary']['settled_payout_gbp'] is None


def test_rain_scenario_is_not_hedged_by_temperature_market(client):
    with patch('src.polymarket_client.requests.get',side_effect=Transport()):
        result=assessment(client,temp_max_c=15,rain_mm=14)
    assert result['payload']['status']=='no_suitable_hedge'
    assert any('cannot substitute' in s for reasons in proposal(client)['rejection_reasons'].values() for s in reasons)


def test_historical_resolution_requires_explicit_winner_not_price():
    condition='0x'+'2'*64
    row={'condition_id':condition,'status':'resolved','extended_review':False,'last_update_timestamp':'1737572825','transaction_hash':'0x'+'b'*64}
    tokens=[{'outcome':'Yes','winner':False,'price':.99},{'outcome':'No','winner':True,'price':.01}]
    def transport(url,**kwargs):
        return Response({'data':[row]} if url.endswith('/resolutions') else {'condition_id':condition,'closed':True,'tokens':tokens})
    with patch('src.polymarket_client.requests.get',side_effect=transport):
        result=PolymarketConnector(allow_live_network=True).resolution(condition)
        assert result['status']=='resolved' and result['payouts']==['0','1']
        assert result['timestamp_basis'].startswith('last_update_timestamp')
        tokens[1]['winner']=False
        assert PolymarketConnector(allow_live_network=True).resolution(condition)['status']=='unresolved'


def test_supported_daily_rainfall_threshold_and_station_distance():
    record=live_record();date=record['endDate'][:10]
    record.update(question='Will London record >= 10mm of daily rainfall on '+date+'?',
        description='Daily rainfall >= 10mm at London City Airport (EGLC), local time 00:00 to 24:00 on '+date+'.',resolutionSource='https://www.metoffice.gov.uk/weather/')
    market=PolymarketConnector()._ingest_live(record)
    spec=parse_contract(market,PROFILE)
    assert spec.metric=='precipitation_or_rainfall'
    assert spec.matches({'rain_mm':10}) and not spec.matches({'rain_mm':9.99})
    with pytest.raises(ValueError,match='distance limit'):
        parse_contract(market,{**PROFILE,'latitude':53.48,'longitude':-2.24})


def training_data(no_signal=False):
    rng=np.random.default_rng(42)
    dates=pd.date_range(end=dt.date.today()-dt.timedelta(days=10),periods=730)
    rows=[];weather=[]
    for date in dates:
        temp=12+8*np.sin(date.dayofyear/365.25*2*np.pi)+rng.normal(0,2)
        rain=float(rng.gamma(1,4));wind=float(rng.uniform(5,35));sun=float(rng.uniform(0,12))
        revenue=(1500+500*(date.dayofweek>=5)) if no_signal else 1600+400*(date.dayofweek>=5)+45*temp-60*rain-3*wind+20*sun+rng.normal(0,15)
        rows.append({'date':date.date().isoformat(),'revenue_gbp':round(max(0,revenue),2)})
        weather.append({'date':date.date().isoformat(),'temp_max_c':temp,'temp_min_c':temp-6,'rain_mm':rain,'wind_max_kmh':wind,'sunshine_hours':sun})
    history={'origin':'historical_test_fixture','source':'Labelled generated historical-weather test fixture','retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),'coordinates':{'latitude':51.45,'longitude':-.07},'start_date':rows[0]['date'],'end_date':rows[-1]['date'],'rows':weather}
    csv='date,revenue_gbp,currency\n'+'\n'.join(f'{r["date"]},{r["revenue_gbp"]},GBP' for r in rows)
    return csv,history


def test_import_training_holdout_and_business_specific_analysis(client):
    content,history=training_data()
    assert client.post('/api/sources/import',json={'filename':'training-test.csv','csv':content}).status_code==200
    before=assessment(client,market_mode='test_suitable',temp_max_c=15,rain_mm=14)
    assert before['payload']['status']=='need_information'
    with patch('src.business_model.historical_weather',return_value=history):
        response=client.post('/api/models/train')
    assert response.status_code==202
    job=client.get('/api/models/training/'+response.json()['id']).json()
    assert job['state']=='complete',job
    model=client.get('/api/models/current').json()
    assert model['accepted'] and model['improvement_pct']>=5
    assert model['training_end']<model['validation_start']<=model['validation_end']<model['test_start']
    assert model['training_rows']+model['validation_rows']+model['test_rows']==730
    assert 'pipeline_bytes' not in model
    result=assessment(client,market_mode='test_suitable',temp_max_c=15,rain_mm=14)
    assert result['payload']['comparison']['scenario_prediction']['model_version']==model['id']
    assert 'user-supplied' in result['payload']['model_note']
    client.post('/api/sources/import',json={'filename':'selected-again.csv','csv':content})
    state=client.get('/api/state').json()
    assert state['business_model'] is None and state['training_job'] is None
    assert client.get('/api/models/training/'+job['id']).json()['state']=='complete'


def test_model_without_holdout_improvement_is_not_activated(client):
    content,history=training_data(no_signal=True)
    client.post('/api/sources/import',json={'filename':'calendar-only.csv','csv':content})
    with patch('src.business_model.historical_weather',return_value=history):
        response=client.post('/api/models/train')
    job=client.get('/api/models/training/'+response.json()['id']).json()
    assert job['state']=='complete'
    assert not job['payload']['model']['accepted']
    assert client.get('/api/models/current').json() is None


def test_demo_connections_never_import_data_or_verify_accounts(client):
    initial=client.get('/api/state').json()
    for provider in ('toast','monzo','xero','companies_house'):
        response=client.post('/api/sources/'+provider+'/demo-connect')
        assert response.json()['status']=='demo_connected'
    state=client.get('/api/state').json()
    assert state['dataset']==initial['dataset'] and state['revision']==initial['revision']
    assert all(s['status']=='demo_connected' for s in state['sources'][:4])
    assert all('no account' in s['note'].lower() for s in state['sources'][:4])


def test_monitor_proposes_once_never_approves_and_respects_rejection(client):
    date=dt.date.today()+dt.timedelta(days=1)
    day={'date':date.isoformat(),'temp_max_c':5,'temp_min_c':-1,'temp_mean_c':2,'rain_mm':0,'precipitation_mm':0,'wind_max_kmh':26,'sunshine_hours':.5}
    forecast={'origin':'current_forecast','source':'Mocked Open-Meteo transport for monitor test','retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),'days':[day]}
    service=client.app.state.service
    with patch.object(service,'forecast',return_value=forecast),patch('src.polymarket_client.requests.get',side_effect=Transport(live_record(date))):
        first=service.monitor_tick(force=True)
        assert first['status']=='complete',first
        p=proposal(client);assert p['approval_state']=='pending_human_approval'
        assert client.get('/api/positions').json()==[]
        second=service.monitor_tick(force=True)
        assert 'No duplicate' in second['note']
        assert len(client.get('/api/proposals').json())==1
        client.post(f'/api/proposals/{p["proposal_id"]}/reject',json={'note':'Declined by test operator'})
        third=service.monitor_tick(force=True)
        assert 'rejected' in third['note']
        assert len(client.get('/api/proposals').json())==1
    state=client.get('/api/state').json()
    assert state['notifications']
    note=state['notifications'][0]['id']
    assert client.post(f'/api/notifications/{note}/read').status_code==200
    assert client.get('/api/state').json()['notifications'][0]['read_at']
