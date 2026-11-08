"""Public read-only provider checks. Stores metadata only, never credentials."""
import datetime as dt
import json
from pathlib import Path
from src.forecast import retrieve_forecast
from src.polymarket_client import PolymarketConnector


if __name__ == '__main__':
    date = (dt.datetime.now(dt.timezone.utc).date()+dt.timedelta(days=2)).isoformat()
    forecast = retrieve_forecast({'latitude':51.45,'longitude':-.07})
    connector = PolymarketConnector(allow_live_network=True)
    catalogue = connector.refresh_catalog(date)
    result = {'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(), 'location':'Explicit London sample coordinates',
        'forecast':{k:v for k,v in forecast.items() if k != 'days'}, 'forecast_days_received':len(forecast['days']),
        'gamma_catalogue':catalogue, 'clob':{'tested':False, 'note':'No suitable, verified live rainfall contract yet. No live order, payment or OAuth test.'}}
    candidates=list(connector._candidates_by_id.values())
    if catalogue.get('ok') and candidates:
        book=connector.get_order_book(candidates[0].market_id)
        result['clob']={k:book.get(k) for k in ('market_id','data_origin','retrieval_timestamp','executable_book_available','best_ask_usd')}
        result['clob']['tested']=True
    path=Path('docs/live-verification.json')
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(path.read_text())
