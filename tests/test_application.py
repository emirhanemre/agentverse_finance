"""Local application integration tests. All records are isolated temporary databases.

External-provider tests mock only the transport and never claim live verification.
"""
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import json
from unittest.mock import patch

import pytest
import requests
from fastapi.testclient import TestClient

from src.api import create_app
from src.api_schemas import ApprovalInput
from src.application import import_sales
from src.application_store import Conflict
from src.forecast import retrieve_forecast
from src.polymarket_client import PolymarketConnector

PROFILE = dict(pubName='Integration Test Pub', postcode='SE22 8HD', owner='Local Test Operator',
    email='operator@example.com', location_name='London, UK', latitude=51.45, longitude=-.07,
    indoor_capacity=90, outdoor_capacity=70, opening_hours=11, currency='GBP')


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('POLYMARKET_OFFLINE_ONLY', 'true')
    with TestClient(create_app(tmp_path / 'application.db')) as client:
        yield client


def setup(client):
    assert client.put('/api/profile', json=PROFILE).status_code == 200
    assert client.post('/api/sources/sample').status_code == 200


def analyse(client, **kwargs):
    data = dict(target_date=(dt.datetime.now(dt.timezone.utc).date()+dt.timedelta(days=2)).isoformat(), market_mode='test_suitable')
    data.update(kwargs)
    r = client.post('/api/analyses', json=data)
    assert r.status_code == 202, r.text
    result = client.get('/api/analyses/' + r.json()['id']).json()
    assert result['state'] != 'running'
    return result


def proposal(client):
    return client.get('/api/state').json()['proposals'][0]


def approval(p):
    return dict(confirmed_proposal_hash=p['proposal_hash'], confirmed_quantity=p['paper_quantity'],
        confirmed_max_cost_gbp=p['max_total_cost_gbp'], confirmed_quote_timestamp=p['quote_timestamp'], acknowledge_paper_risk=True)


def test_profile_persists_and_invalidates_dependent_results(client):
    setup(client)
    analyse(client)
    p = proposal(client)
    updated = {**PROFILE, 'pubName':'Renamed Pub', 'latitude':51.5}
    assert client.put('/api/profile', json=updated).status_code == 200
    state = client.get('/api/state').json()
    assert state['profile'] == updated
    assert state['dataset'] is None
    assert state['analysis'] is None
    assert client.post(f"/api/proposals/{p['proposal_id']}/approve",json=approval(p)).status_code == 409
    restarted = create_app(client.app.state.store.db_path)
    with TestClient(restarted) as other:
        assert other.get('/api/state').json()['profile'] == updated


def test_valid_sales_import_and_descriptive_summary(client):
    setup(client)
    r = client.post('/api/sources/import', json={'filename':'actual.csv','csv':'date,revenue_gbp,currency\n2026-01-02,123.45,GBP\n2026-01-01,10.55,GBP\n'})
    assert r.status_code == 200
    dataset = r.json()['dataset']
    assert dataset['origin'] == 'user_import'
    assert dataset['row_count'] == 2
    assert dataset['total_revenue_gbp'] == 134
    assert dataset['monthly'] == [{'month':'2026-01','revenue_gbp':134}]
    assert 'does not train' in dataset['note']
    assert 'rows' not in dataset


@pytest.mark.parametrize('content,reason', [
    ('date,sales,currency\n2026-01-01,1,GBP','columns'),
    ('date,revenue_gbp,currency\n2026-02-30,1,GBP','calendar'),
    ('date,revenue_gbp,currency\n2026-1-01,1,GBP','ISO'),
    ('date,revenue_gbp,currency\n2099-01-01,1,GBP','future'),
    ('date,revenue_gbp,currency\n2026-01-01,-1,GBP','nonnegative'),
    ('date,revenue_gbp,currency\n2026-01-01,NaN,GBP','finite'),
    ('date,revenue_gbp,currency\n2026-01-01,Infinity,GBP','finite'),
    ('date,revenue_gbp,currency\n2026-01-01,1.111,GBP','decimal'),
    ('date,revenue_gbp,currency\n2026-01-01,10,USD','GBP'),
    ('date,revenue_gbp,currency\n2026-01-01,10,GBP\n2026-01-01,11,GBP','duplicate'),
    ('date,revenue_gbp,currency\n','no sales'),
    ('date,revenue_gbp,currency\n2026-01-01,1,GBP,extra','columns'),
])
def test_invalid_import_is_actionable_and_preserves_selection(client, content, reason):
    setup(client)
    previous = client.get('/api/state').json()['dataset']
    result = client.post('/api/sources/import', json={'filename':'bad.csv','csv':content})
    assert result.status_code == 422
    assert reason.lower() in result.json()['detail'].lower()
    assert client.get('/api/state').json()['dataset'] == previous


def test_analysis_success_events_and_synthetic_labels(client):
    setup(client)
    result = analyse(client)
    assert result['state'] == 'complete'
    assert result['payload']['status'] == 'recommend_paper_hedge'
    assert len(result['events']) >= 5
    assert result['payload']['weather_provenance']['origin'] == 'manual_scenario'
    p = proposal(client)
    assert p['data_origin'] == 'synthetic_test_fixture'
    assert p['calculation']['total_entry_cost_gbp'] <= 100
    assert 'not a validated' in result['payload']['model_note']


def test_no_hedge_can_finish_and_reload_empty_dashboard(client):
    setup(client)
    result = analyse(client,market_mode='test_no_match')
    assert result['payload']['status'] == 'no_suitable_hedge'
    assert proposal(client)['rejection_reasons']
    assert client.post('/api/setup/complete').status_code == 200
    state = client.get('/api/state').json()
    assert state['setup_complete']
    assert state['positions'] == []
    assert state['summary']['pending_approvals'] == 0
    assert state['summary']['settled_payout_gbp'] is None


def test_missing_information_and_model_failure(client):
    result = analyse(client)
    assert result['payload']['status'] == 'need_information'
    setup(client)
    with patch('src.use_cases.compare_weather_scenarios_for_date',side_effect=FileNotFoundError('model missing')):
        result = analyse(client)
    assert result['state'] == 'failed'
    assert result['payload']['status'] == 'data_unavailable'
    assert client.get('/api/state').json()['analysis']['id'] == result['id']
    assert client.get('/api/positions').json() == []


def test_non_london_model_unavailable(client):
    setup(client)
    client.put('/api/profile',json={**PROFILE,'location_name':'Manchester, UK','latitude':53.48,'longitude':-2.24})
    result = analyse(client)
    assert result['payload']['status'] == 'need_information'
    assert 'Train a local model' in proposal(client)['explanation']


def test_approval_rejection_tampering_and_duplicates(client):
    setup(client)
    analyse(client)
    p = proposal(client)
    url = f"/api/proposals/{p['proposal_id']}/approve"
    for mutation in ({'confirmed_quantity':p['paper_quantity']+1},{'confirmed_max_cost_gbp':1},{'confirmed_proposal_hash':'bad'},{'confirmed_quote_timestamp':'2000-01-01T00:00:00+00:00'}):
        assert client.post(url,json={**approval(p),**mutation}).status_code == 409
    assert client.post(url,json={**approval(p),'acknowledge_paper_risk':False}).status_code == 422
    assert client.post(url,json={**approval(p),'extra':'tampering'}).status_code == 422
    assert client.post(url,json=approval(p)).status_code == 200
    assert client.post(url,json=approval(p)).status_code == 409
    state = client.get('/api/state').json()
    assert len(state['positions']) == 1
    assert state['summary']['open_positions'] == 1
    assert state['summary']['total_entry_cost_gbp'] == p['max_total_cost_gbp']
    assert state['summary']['pending_approvals'] == 0
    analyse(client,target_date=(dt.date.today()+dt.timedelta(days=3)).isoformat())
    p = proposal(client)
    assert client.post(f"/api/proposals/{p['proposal_id']}/reject",json={'note':'Not suitable for me'}).status_code == 200
    assert client.post(f"/api/proposals/{p['proposal_id']}/approve",json=approval(p)).status_code == 409


def test_stale_proposals_require_new_assessment(client):
    setup(client)
    analyse(client)
    p = proposal(client)
    with client.app.state.store.transaction() as c:
        c.execute("UPDATE proposal_context SET expires_at='2000-01-01T00:00:00+00:00'")
    r = client.post(f"/api/proposals/{p['proposal_id']}/approve",json=approval(p))
    assert r.status_code == 409
    assert 'expired' in r.json()['detail']
    assert client.get('/api/state').json()['summary']['pending_approvals'] == 0


def test_stale_quote_even_when_proposal_expiry_is_current(client):
    setup(client)
    analyse(client)
    p = proposal(client)
    # Rebind an old quote as a server-side test fixture, not a client mutation.
    from src.paper_execution import compute_proposal_binding_hash
    p['quote_timestamp'] = '2000-01-01T00:00:00+00:00'
    p['proposal_hash'] = compute_proposal_binding_hash(p['proposal_id'],p['market_id'],p['outcome_selected'],p['paper_quantity'],p['max_total_cost_gbp'],p['quote_timestamp'])
    with client.app.state.store.transaction() as c:
        c.execute('UPDATE proposals SET payload_json=?,proposal_hash=?,quote_timestamp=? WHERE proposal_id=?',(json.dumps({k:v for k,v in p.items() if k in __import__('src.schemas',fromlist=['HedgeProposalRecord']).HedgeProposalRecord.model_fields}),p['proposal_hash'],p['quote_timestamp'],p['proposal_id']))
    r = client.post(f"/api/proposals/{p['proposal_id']}/approve",json=approval(p))
    assert r.status_code == 409
    assert 'Stale' in r.json()['detail']


def test_concurrent_approvals_record_once(client):
    setup(client)
    analyse(client)
    p = proposal(client)
    store = client.app.state.store
    data = ApprovalInput.model_validate(approval(p))
    def approve():
        try:
            return store.decide(p['proposal_id'],data)['ok']
        except Conflict:
            return False
    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(lambda _:approve(),range(8))) == 1
    assert len(store.get_paper_positions()) == 1


@pytest.mark.parametrize('limit_key', ['weekly_spend_gbp','monthly_loss_gbp'])
def test_accumulated_limits_include_pending_and_positions(client, limit_key):
    setup(client)
    settings = client.get('/api/settings').json()
    settings[limit_key] = 150
    client.put('/api/settings',json=settings)
    analyse(client,budget_gbp=100)
    p = proposal(client)
    assert p['status'] == 'recommend_paper_hedge'
    analyse(client,budget_gbp=100,target_date=(dt.date.today()+dt.timedelta(days=3)).isoformat())
    assert proposal(client)['status'] == 'no_suitable_hedge'
    assert client.post(f"/api/proposals/{p['proposal_id']}/approve",json=approval(p)).status_code == 200
    analyse(client,budget_gbp=100,target_date=(dt.date.today()+dt.timedelta(days=4)).isoformat())
    assert proposal(client)['status'] == 'no_suitable_hedge'
    assert client.get('/api/state').json()['summary']['monthly_reserved_loss_gbp'] == p['max_total_cost_gbp']


def test_restart_keeps_positions_and_settings(client):
    setup(client)
    analyse(client)
    p=proposal(client)
    client.post(f"/api/proposals/{p['proposal_id']}/approve",json=approval(p))
    settings=client.get('/api/settings').json()
    with TestClient(create_app(client.app.state.store.db_path)) as restarted:
        state=restarted.get('/api/state').json()
        assert len(state['positions']) == 1
        assert state['settings'] == settings
        assert any(e['event_type']=='paper_position_recorded' for e in state['activity'])
        assert restarted.post('/api/positions/refresh').json()['positions'][0]['actual_resolved_outcome'] == 'UNRESOLVED'


def test_forecast_failure_fallbacks_are_labelled(client):
    setup(client)
    with patch('src.forecast.requests.get',side_effect=requests.ConnectionError()):
        missing=retrieve_forecast(PROFILE)
        assert missing['origin']=='unavailable' and missing['days']==[]
        cached={**missing,'origin':'current_forecast','retrieved_at':'2026-01-01T00:00:00+00:00','days':[{'date':'2026-01-01'}]}
        fallback=retrieve_forecast(PROFILE,cached)
        assert fallback['origin']=='cached_forecast'
        assert fallback['retrieved_at']==cached['retrieved_at']
        assert retrieve_forecast({**PROFILE,'latitude':52},cached)['origin']=='unavailable'
    result=analyse(client,weather_mode='forecast')
    assert result['payload']['status']=='data_unavailable'


def test_live_catalogue_discovery_and_failure_labels():
    connector=PolymarketConnector(allow_live_network=True)
    response=type('Response',(),{'raise_for_status':lambda s:None,'json':lambda s:[{
        'id':'live-test','question':'London rainfall on 2026-11-10?', 'description':'Daily rainfall >=10mm',
        'resolutionSource':'test source','active':True,'closed':False,'acceptingOrders':True,
        'outcomes':'["Yes","No"]','outcomePrices':'["0.3","0.7"]','clobTokenIds':'["1","2"]'}]})()
    with patch('src.polymarket_client.requests.get',return_value=response) as transport:
        result=connector.refresh_catalog('2026-11-10')
        assert result['ok'] and result['weather_candidates']==1 and result['scanned']==2
        assert transport.call_args.args[0].endswith('/public-search')
        assert connector.get_market_candidate('live-test') is not None
        assert not connector.get_market_candidate('live-test').asks_by_outcome
    with patch('src.polymarket_client.requests.get',side_effect=requests.ConnectionError()):
        connector=PolymarketConnector(allow_live_network=True)
        result=connector.refresh_catalog('2026-11-10')
        assert not result['ok'] and result['origin']=='cached_polymarket_snapshot'


def test_cross_site_writes_blocked_and_schema_strict(client):
    assert client.put('/api/profile',json=PROFILE,headers={'Origin':'https://untrusted.example'}).status_code==403
    assert client.put('/api/profile',content=json.dumps({**PROFILE,'latitude':float('inf')}),headers={'Content-Type':'application/json'}).status_code == 422


def test_settings_change_invalidates_pending_approval(client):
    setup(client)
    analyse(client)
    p=proposal(client)
    settings=client.get('/api/settings').json()
    settings['fx_usd_per_gbp']=1.3
    assert client.put('/api/settings',json=settings).status_code==200
    assert client.get('/api/state').json()['analysis'] is None
    assert client.post(f"/api/proposals/{p['proposal_id']}/approve",json=approval(p)).status_code==409
    settings['fx_usd_per_gbp']=1.30000001
    assert client.put('/api/settings',json=settings).status_code==422


def test_per_contract_concentration_includes_reservations(client):
    setup(client)
    settings=client.get('/api/settings').json()
    settings['per_contract_gbp']=150
    client.put('/api/settings',json=settings)
    analyse(client)
    p=proposal(client)
    assert p['status']=='recommend_paper_hedge'
    analyse(client)
    assert proposal(client)['status']=='no_suitable_hedge'
    assert 'per-contract concentration' in proposal(client)['explanation']
    assert client.post(f"/api/proposals/{p['proposal_id']}/approve",json=approval(p)).status_code==200


def test_expired_reservations_release_capacity(client):
    setup(client)
    settings=client.get('/api/settings').json()
    settings['weekly_spend_gbp']=150
    client.put('/api/settings',json=settings)
    analyse(client)
    with client.app.state.store.transaction() as c:
        c.execute("UPDATE proposal_context SET expires_at='2000-01-01T00:00:00+00:00'")
    analyse(client)
    assert proposal(client)['status']=='recommend_paper_hedge'


def test_prior_month_unresolved_cost_still_reserves_loss_allowance(client):
    setup(client)
    analyse(client)
    p=proposal(client)
    client.post(f"/api/proposals/{p['proposal_id']}/approve",json=approval(p))
    old=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=45)).isoformat()
    with client.app.state.store.transaction() as c:
        c.execute('UPDATE paper_positions SET approved_at=?',(old,))
    state=client.get('/api/state').json()
    assert state['summary']['weekly_reserved_gbp']==0
    assert state['summary']['monthly_reserved_loss_gbp']==p['max_total_cost_gbp']
    assert state['positions'][0]['business_name']==PROFILE['pubName']


def test_interrupted_analysis_recovers_as_explained_failure(client):
    from src.api_schemas import AnalysisInput
    setup(client)
    service=client.app.state.service
    aid=service.start_analysis(AnalysisInput(target_date=dt.date.today()+dt.timedelta(days=2)))
    with TestClient(create_app(client.app.state.store.db_path)) as restarted:
        result=restarted.get('/api/analyses/'+aid).json()
        assert result['state']=='failed'
        assert 'interrupted by server restart' in result['payload']['error']
        assert result['events'][-1]['label']=='Analysis interrupted'


def test_live_candidate_without_structured_rules_cannot_be_approved(client, monkeypatch):
    from src.application import test_market
    setup(client)
    monkeypatch.setenv('POLYMARKET_OFFLINE_ONLY','false')
    date=(dt.date.today()+dt.timedelta(days=2)).isoformat()
    market=test_market(PROFILE,date)
    market.data_origin='live_polymarket_api'
    market.clob_token_ids=['test-yes','test-no']
    connector=PolymarketConnector(allow_live_network=False)
    connector._candidates_by_id={market.market_id:market}
    with patch('src.application.PolymarketConnector',return_value=connector), patch.object(connector,'refresh_catalog',return_value={'ok':True,'origin':'live_polymarket_api','note':'Mocked live catalogue for this test only'}):
        result=analyse(client,market_mode='live')
    assert result['payload']['status']=='no_suitable_hedge'
    assert any('station' in r.lower() for reasons in proposal(client)['rejection_reasons'].values() for r in reasons)
