"""Per-business training with historical-weather joins and chronological evaluation.

Pipeline artifacts are generated only by this server and stored in SQLite, never
accepted from an upload. No random train/test split and no future revenue lags.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import io
import json
import uuid
from zoneinfo import ZoneInfo
import joblib
import numpy as np
import pandas as pd
import requests
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.application_store import Conflict
from src.paper_execution import utc_now_iso

WEATHER=['temp_max_c','temp_min_c','rain_mm','wind_max_kmh','sunshine_hours']
NUMERIC=WEATHER+['sin_year','cos_year']
FEATURES=['weekday']+NUMERIC


def fingerprint(profile, dataset):
    return hashlib.sha256(json.dumps({'profile':profile,'sales':dataset.get('sha256') or dataset['rows']},sort_keys=True).encode()).hexdigest()


def historical_weather(profile, start, end, cached=None, allow_live=True):
    coords={k:profile[k] for k in ('latitude','longitude')}
    # ERA5 archive publication lags; exclude recent days instead of using a
    # forecast as historical training evidence.
    end=min(end,(dt.datetime.now(ZoneInfo('Europe/London')).date()-dt.timedelta(days=5)).isoformat())
    if end<start: raise Conflict('Historical weather is not yet published for these dates. Upload older sales records.')
    if cached and cached.get('coordinates')==coords and cached.get('start_date','9999')<=start and cached.get('end_date','')>=end:
        return {**cached,'cache_used':True}
    if not allow_live: raise Conflict('Historical weather is unavailable offline for this location/date range. Fetch it with network access, then retry.')
    url='https://archive-api.open-meteo.com/v1/archive'
    try:
        response=requests.get(url,params={**coords,'start_date':start,'end_date':end,'timezone':'Europe/London',
            'daily':'temperature_2m_max,temperature_2m_min,rain_sum,wind_speed_10m_max,sunshine_duration','wind_speed_unit':'kmh'},timeout=30)
        response.raise_for_status();raw=response.json()['daily'];rows=[]
        for i,date in enumerate(raw['time']):
            values=[raw[k][i] for k in ('temperature_2m_max','temperature_2m_min','rain_sum','wind_speed_10m_max','sunshine_duration')]
            if any(v is None or not np.isfinite(float(v)) for v in values): continue
            rows.append({'date':date,**dict(zip(WEATHER,[float(v) for v in values[:4]]+[float(values[4])/3600]))})
        if not rows: raise ValueError()
        return {'origin':'historical_reanalysis','source':'Open-Meteo historical archive (gridded reanalysis; not an airport gauge)',
            'source_url':url,'coordinates':coords,'timezone':'Europe/London','start_date':start,'end_date':end,
            'retrieved_at':utc_now_iso(),'units':{'temperature':'°C','rain':'mm','wind':'km/h','sunshine':'h'},'rows':rows}
    except (requests.RequestException,ValueError,KeyError,TypeError,IndexError) as exc:
        raise Conflict('Could not retrieve complete historical weather. The import is preserved; retry training when the archive is available.') from exc


def frame(rows):
    df=pd.DataFrame(rows).copy();dates=pd.to_datetime(df['date'])
    df['weekday']=dates.dt.dayofweek
    df['sin_year']=np.sin(2*np.pi*dates.dt.dayofyear/365.25)
    df['cos_year']=np.cos(2*np.pi*dates.dt.dayofyear/365.25)
    return df


def train_pipeline(profile, dataset, history):
    sales=pd.DataFrame(dataset['rows']);weather=pd.DataFrame(history['rows'])
    joined=sales.merge(weather,on='date',how='inner',validate='one_to_one').sort_values('date').reset_index(drop=True)
    n=len(joined)
    if n<180: raise Conflict(f'Training needs at least 180 daily sales records matched to published historical weather; {n} matched. Missing dates are not filled with zero revenue.')
    if (pd.Timestamp(joined.date.iloc[-1])-pd.Timestamp(joined.date.iloc[0])).days<179:
        raise Conflict('Training requires at least 180 days of calendar coverage.')
    if joined['revenue_gbp'].std()<1: raise Conflict('Sales have insufficient variation to estimate weather exposure.')
    x=frame(joined.to_dict('records'));y=joined.revenue_gbp.to_numpy(dtype=float)
    a,b=int(n*.6),int(n*.8)
    means=joined.iloc[:a].assign(weekday=x.weekday.iloc[:a]).groupby('weekday').revenue_gbp.mean().to_dict()
    global_mean=float(y[:a].mean())
    baseline=np.array([means.get(int(d),global_mean) for d in x.weekday])
    preprocess=lambda:ColumnTransformer([('weekday',OneHotEncoder(handle_unknown='ignore',sparse_output=False),['weekday']),('numeric',StandardScaler(),NUMERIC)])
    options={
        'ridge':make_pipeline(preprocess(),Ridge(alpha=10)),
        'hist_gradient_boosting':make_pipeline(preprocess(),HistGradientBoostingRegressor(max_iter=140,max_depth=3,min_samples_leaf=15,l2_regularization=5,random_state=42)),
    }
    scores={}
    for name,model in options.items():
        model.fit(x[FEATURES].iloc[:a],y[:a]);scores[name]=float(mean_absolute_error(y[a:b],np.maximum(0,model.predict(x[FEATURES].iloc[a:b]))))
    selected=min(scores,key=scores.get);model=options[selected]
    validation_prediction=np.maximum(0,model.predict(x[FEATURES].iloc[a:b]))
    prediction=np.maximum(0,model.predict(x[FEATURES].iloc[b:]))
    mae=float(mean_absolute_error(y[b:],prediction));base=float(mean_absolute_error(y[b:],baseline[b:]))
    improvement=(base-mae)/base*100 if base>0 else 0
    accepted=base>0 and improvement>=5
    residual=y[a:b]-validation_prediction
    refs={}
    for month in range(1,13):
        selected_rows=joined.iloc[:a][(pd.to_datetime(joined.date.iloc[:a]).dt.month==month)&(joined.rain_mm.iloc[:a]<1)]
        if selected_rows.empty: selected_rows=joined.iloc[:a][joined.rain_mm.iloc[:a]<1]
        if selected_rows.empty: selected_rows=joined.iloc[:a]
        refs[str(month)]={key:float(selected_rows[key].median()) for key in WEATHER}
        refs[str(month)]['rain_mm']=0.
    model_id='business_model_'+uuid.uuid4().hex[:16]
    buf=io.BytesIO();joblib.dump(model,buf)
    metadata={'id':model_id,'fingerprint':fingerprint(profile,dataset),'created_at':utc_now_iso(),
        'accepted':accepted,'status':'holdout_pass' if accepted else 'holdout_failed','origin':dataset['origin'],
        'algorithm':selected,'validation_mae_by_model':scores,'training_rows':a,'validation_rows':b-a,'test_rows':n-b,
        'matched_rows':n,'unmatched_sales_rows':len(sales)-n,'training_start':joined.date.iloc[0],'training_end':joined.date.iloc[a-1],
        'validation_start':joined.date.iloc[a],'validation_end':joined.date.iloc[b-1],'test_start':joined.date.iloc[b],'test_end':joined.date.iloc[-1],
        'test_mae_gbp':round(mae,2),'baseline_test_mae_gbp':round(base,2),'improvement_pct':round(improvement,2),
        'test_r2':float(r2_score(y[b:],prediction)) if np.var(y[b:])>0 else None,'selection_rule':'Choose lowest validation MAE; activate only if untouched chronological holdout MAE beats training-only weekday baseline by ≥5%.',
        'weekday_means':{str(k):float(v) for k,v in means.items()},'global_mean':global_mean,
        'residual_q_low':float(np.quantile(residual,.1)),'residual_q_high':float(np.quantile(residual,.9)),
        'reference_weather':refs,'weather_bounds':{key:[float(joined.iloc[:a][key].min()),float(joined.iloc[:a][key].max())] for key in WEATHER},
        'weather_provenance':{k:v for k,v in history.items() if k!='rows'},
        'test_predictions':[{'date':str(joined.date.iloc[i]),'actual_revenue_gbp':round(float(y[i]),2),'predicted_revenue_gbp':round(float(prediction[i-b]),2),'baseline_revenue_gbp':round(float(baseline[i]),2)} for i in range(b,n)],
        'note':('Synthetic sample records; this is still a demonstration model.' if dataset['origin']=='synthetic_sample' else 'Trained on user-supplied records; authenticity is unverified. Chronological holdout performance is internal evaluation, not proof of causality or external validation.')+' Revenue is not margin or cashflow. Predictions outside training weather/calendar coverage are uncertain.'}
    return metadata,buf.getvalue()


def compare(model, target_date, weather, reference_override=None):
    pipeline=joblib.load(io.BytesIO(model['pipeline_bytes']))
    reference=reference_override or model['reference_weather'][str(dt.date.fromisoformat(target_date).month)]
    def predict(values):
        row={**values,'date':target_date}
        row.setdefault('temp_min_c',row['temp_max_c']-6)
        estimate=max(0,float(pipeline.predict(frame([row])[FEATURES])[0]))
        reasons=[f'{k}={row[k]:g} outside training range {bounds}' for k,bounds in model['weather_bounds'].items() if not bounds[0]<=row[k]<=bounds[1]]
        return {'date':target_date,'predictor_used':model['algorithm'],'model_version':model['id'],
            'predicted_revenue_gbp':round(estimate,2),'predicted_revenue_pence':round(estimate*100),
            'baseline_weekday_revenue_gbp':model['weekday_means'].get(str(dt.date.fromisoformat(target_date).weekday()),model['global_mean']),
            'prediction_interval_80_low_gbp':round(max(0,estimate+model['residual_q_low']),2),'prediction_interval_80_high_gbp':round(max(0,estimate+model['residual_q_high']),2),
            'interval_method':'10th/90th residual quantiles from chronological validation split; not a guaranteed coverage interval.',
            'is_out_of_training_range':bool(reasons),'out_of_range_reasons':reasons,'prediction_mode':'conditional_on_weather_scenario','synthetic_data_warning':model['note']}
    selected,ref=predict(weather),predict(reference)
    difference=round(selected['predicted_revenue_gbp']-ref['predicted_revenue_gbp'],2)
    return {'date':target_date,'scenario_label':'Selected weather','reference_label':'Training-derived dry reference',
        'scenario_predicted_revenue_gbp':selected['predicted_revenue_gbp'],'reference_predicted_revenue_gbp':ref['predicted_revenue_gbp'],
        'estimated_difference_gbp':difference,'estimated_downside_loss_gbp':max(0,-difference),'estimated_downside_loss_pence':round(max(0,-difference)*100),
        'scenario_prediction':selected,'reference_prediction':ref,'framing_note':'Observational conditional revenue comparison, not a proven causal loss.',
        'reference_weather':reference,'assumptions':[model['note'],f'Internal chronological holdout MAE £{model["test_mae_gbp"]:.2f}; weekday baseline £{model["baseline_test_mae_gbp"]:.2f}.',
            *(['Outside fitted weather range: '+'; '.join(selected['out_of_range_reasons'])] if selected['is_out_of_training_range'] else []),
            'Same calendar date, business and model in both scenarios. No future sales lags or future weather were used for training.',
            'Reference is the training-split median dry weather for this month (or training dry-day fallback).']}
