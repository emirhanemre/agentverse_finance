"""Cost scenarios use server-side decimal arithmetic and isolated app records."""
import datetime as dt
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.operating_profit import estimate_operating_profit


COMPARISON = {
    'date':'2026-11-09',
    'scenario_predicted_revenue_gbp':1676.62,
    'reference_predicted_revenue_gbp':1943.39,
    'scenario_prediction':{'prediction_interval_80_low_gbp':1500,'prediction_interval_80_high_gbp':2000},
    'reference_prediction':{},
}


def test_profit_costs_rounding_and_interval():
    result=estimate_operating_profit(COMPARISON,{'fixed_daily_cost_gbp':1000,'variable_cost_pct':30})
    assert result['selected']['variable_cost_gbp']==502.99
    assert result['selected']['total_cost_gbp']==1502.99
    assert result['selected']['operating_profit_gbp']==173.63
    assert result['reference']['operating_profit_gbp']==360.37
    assert result['profit_difference_gbp']==-186.74
    assert result['selected']['prediction_interval_80_low_gbp']==50
    assert result['selected']['prediction_interval_80_high_gbp']==400
    assert result['origin']=='demo_cost_assumptions'
    assert 'not a cashflow forecast' in result['note']


@pytest.mark.parametrize('revenue,fixed,percent,expected,margin',[
    (0,1000,30,-1000,None),
    (100,1000,30,-930,-930),
    (100,1000,100,-1000,-1000),
    (100,0,0,100,100),
    (.05,0,10,.04,80),
])
def test_losses_zero_revenue_and_cost_boundaries(revenue,fixed,percent,expected,margin):
    comparison={**COMPARISON,'scenario_predicted_revenue_gbp':revenue,'scenario_prediction':{}}
    selected=estimate_operating_profit(comparison,{'fixed_daily_cost_gbp':fixed,'variable_cost_pct':percent})['selected']
    assert selected['operating_profit_gbp']==expected
    assert selected['operating_margin_pct']==margin


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('POLYMARKET_OFFLINE_ONLY','true')
    with TestClient(create_app(tmp_path/'costs.db')) as client:
        yield client


PROFILE=dict(pubName='Cost Scenario Test Pub',postcode='SE22 8HD',owner='Test Operator',email='test@example.com',location_name='London, UK',latitude=51.45,longitude=-.07)


def test_costs_persist_and_recalculate_without_invalidating_analysis_or_approvals(client):
    assert client.get('/api/state').json()['operating_profit'] is None
    assert client.put('/api/profile',json=PROFILE).status_code==200
    client.post('/api/sources/sample')
    date=(dt.date.today()+dt.timedelta(days=2)).isoformat()
    job=client.post('/api/analyses',json={'target_date':date,'market_mode':'test_suitable'}).json()
    before=client.get('/api/state').json()
    assert before['operating_profit'] is not None
    changed={'fixed_daily_cost_gbp':500,'variable_cost_pct':20}
    with patch('src.application.WeatherApplication.run_analysis',side_effect=AssertionError('Cost edits must not rerun the regression')):
        assert client.put('/api/operating-costs',json=changed).status_code==200
        state=client.get('/api/state').json()
    assert state['operating_profit']['assumptions']==changed
    assert state['analysis']['id']==job['id']
    assert state['revision']==before['revision']
    assert state['proposals']==before['proposals']
    expected=estimate_operating_profit(state['analysis']['payload']['comparison'],changed)
    assert state['operating_profit']==expected
    assert state['activity'][0]['event_type']=='operating_cost_assumptions_saved'
    with TestClient(create_app(client.app.state.store.db_path)) as restarted:
        assert restarted.get('/api/operating-costs').json()==changed
        assert restarted.get('/api/state').json()['operating_profit']==expected
    client.put('/api/profile',json={**PROFILE,'pubName':'Another Pub'})
    state=client.get('/api/state').json()
    assert state['operating_profit'] is None
    assert state['operating_costs']=={'fixed_daily_cost_gbp':1000,'variable_cost_pct':30}


@pytest.mark.parametrize('costs',[
    {'fixed_daily_cost_gbp':-1,'variable_cost_pct':30},
    {'fixed_daily_cost_gbp':100,'variable_cost_pct':101},
    {'fixed_daily_cost_gbp':1.001,'variable_cost_pct':30},
])
def test_invalid_costs_preserve_saved_assumptions(client,costs):
    client.put('/api/profile',json=PROFILE)
    before=client.get('/api/operating-costs').json()
    assert client.put('/api/operating-costs',json=costs).status_code==422
    assert client.get('/api/operating-costs').json()==before


def test_cost_edits_require_business(client):
    assert client.put('/api/operating-costs',json={'fixed_daily_cost_gbp':500,'variable_cost_pct':30}).status_code==409
