"""Local-only FastAPI service. No exchange order or payment operations exist."""
from __future__ import annotations
from contextlib import asynccontextmanager
import asyncio
import contextlib
import os
from pathlib import Path
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from src.api_schemas import (AnalysisInput, ApprovalInput, ProfileInput, RejectInput, SalesImport,
    SettingsInput, StateResponse, ProfileResponse, AnalysisResponse, AnalysisStartedResponse)
from src.application import WeatherApplication, import_sales, sample_dataset
from src.application_store import ApplicationStore, Conflict


def create_app(db_path=None):
    store = ApplicationStore(db_path or os.getenv('APP_DB_PATH', 'data/runtime/weather_app.db'))
    service = WeatherApplication(store)

    @asynccontextmanager
    async def lifespan(app):
        # Jobs interrupted by a server restart must never appear to finish successfully.
        with store.transaction() as c:
            import json
            from src.paper_execution import utc_now_iso
            for row in c.execute("SELECT id,payload FROM analyses WHERE state='running'").fetchall():
                payload = json.loads(row['payload'])
                error = 'Analysis interrupted by server restart. Run the assessment again.'
                payload.update(status='data_unavailable', error=error)
                c.execute("UPDATE analyses SET state='failed',payload=? WHERE id=?", (json.dumps(payload), row['id']))
                c.execute('INSERT INTO task_events(analysis_id,created_at,label,detail) VALUES (?,?,?,?)', (row['id'],utc_now_iso(),'Analysis interrupted',error))
                store.audit(c,'analysis_failed',{'analysis_id':row['id'],'error':error})
            for row in c.execute("SELECT id FROM training_jobs WHERE state='running'").fetchall():
                c.execute("UPDATE training_jobs SET state='failed',payload=? WHERE id=?",(json.dumps({'stage':'failed','error':'Training interrupted by server restart. Retry training.'}),row['id']))
            monitoring=store.state('monitoring',{},c) or {}
            if monitoring.get('running'):
                monitoring.update(running=False,status='interrupted',note='Monitoring check interrupted by server restart.')
                store.put(c,'monitoring',monitoring)
        async def monitor_loop():
            while True:
                if store.state('settings',{}).get('monitor_enabled'):
                    await asyncio.to_thread(service.monitor_tick)
                await asyncio.sleep(5)
        monitor=asyncio.create_task(monitor_loop())
        try:
            yield
        finally:
            monitor.cancel()
            with contextlib.suppress(asyncio.CancelledError): await monitor

    app = FastAPI(title='Pub Hedge local paper API', version='1.0', lifespan=lifespan)
    app.state.store, app.state.service = store, service
    allowed_origins = ['http://localhost:3000', 'http://127.0.0.1:3000']
    if os.getenv('APP_ORIGIN'): allowed_origins.append(os.environ['APP_ORIGIN'].rstrip('/'))
    app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_methods=['GET','POST','PUT'], allow_headers=['Content-Type'])

    @app.middleware('http')
    async def local_write_guard(request: Request, call_next):
        # Avoid cross-site requests mutating an unauthenticated local database.
        origin = request.headers.get('origin')
        if request.method != 'GET' and origin and origin not in allowed_origins:
            return JSONResponse({'detail':'Untrusted origin'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(Conflict)
    async def conflict_handler(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=409)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, exc):
        # Return actionable fields without echoing imported financial records,
        # arbitrary input, non-finite numbers or upstream exception contexts.
        return JSONResponse({'detail': [{'loc': list(e['loc']), 'msg': e['msg']} for e in exc.errors()]}, status_code=422)

    @app.get('/api/health')
    def health():
        return {'ok': True, 'trading_mode': 'paper_only', 'execution_mode': 'deterministic'}

    @app.get('/api/state', response_model=StateResponse)
    def state():
        return service.snapshot()

    @app.get('/api/profile', response_model=ProfileResponse)
    def profile():
        return {'profile': store.state('profile'), 'verification': 'self_reported'}

    @app.put('/api/profile', response_model=ProfileResponse)
    def save_profile(profile: ProfileInput):
        return {'profile': store.set_profile(profile.model_dump()), 'verification': 'self_reported'}

    @app.get('/api/sources')
    def sources():
        state = service.snapshot()
        return {'providers': state['sources'], 'dataset': state['dataset']}

    @app.post('/api/sources/sample')
    def select_sample():
        if not store.state('profile'):
            raise Conflict('Save business details first.')
        store.set_dataset(sample_dataset())
        return sources()

    @app.post('/api/sources/import')
    def import_file(data: SalesImport):
        if not store.state('profile'):
            raise Conflict('Save business details first.')
        try:
            dataset = import_sales(data.csv, data.filename)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        store.set_dataset(dataset)
        return sources()

    @app.get('/api/weather')
    def weather():
        return store.state('forecast', {'origin':'unavailable', 'days':[], 'note':'Refresh the forecast or choose a manual scenario.'})

    @app.post('/api/weather/refresh')
    def refresh_weather():
        return service.forecast()

    @app.post('/api/analyses', status_code=202, response_model=AnalysisStartedResponse)
    def start(inputs: AnalysisInput, tasks: BackgroundTasks):
        aid = service.start_analysis(inputs)
        tasks.add_task(service.run_analysis, aid)
        return {'id': aid, 'state': 'running'}

    @app.get('/api/analyses/{analysis_id}', response_model=AnalysisResponse)
    def analysis(analysis_id: str):
        result = store.analysis(analysis_id)
        if not result:
            raise HTTPException(404, 'Analysis not found')
        return result

    @app.get('/api/proposals')
    def proposals():
        return service.snapshot()['proposals']

    @app.get('/api/proposals/{proposal_id}')
    def proposal(proposal_id: str):
        p = next((p for p in service.snapshot()['proposals'] if p['proposal_id'] == proposal_id), None)
        if not p:
            raise HTTPException(404, 'Proposal not found')
        return p

    @app.post('/api/proposals/{proposal_id}/approve')
    def approve(proposal_id: str, data: ApprovalInput):
        return service.approve(proposal_id, data)

    @app.post('/api/proposals/{proposal_id}/reject')
    def reject(proposal_id: str, data: RejectInput):
        return store.decide(proposal_id, note=data.note)

    @app.get('/api/positions')
    def positions():
        return service.snapshot()['positions']

    @app.post('/api/positions/refresh')
    def refresh_positions():
        return service.refresh_settlements()

    @app.post('/api/sources/{provider}/demo-connect')
    def demo_connect(provider: str):
        if provider not in ('toast','monzo','xero','companies_house'): raise HTTPException(404,'Unknown provider demo')
        from src.paper_execution import utc_now_iso
        with store.transaction() as c:
            demos=store.state('demo_sources',{},c);demos[provider]=utc_now_iso()
            store.put(c,'demo_sources',demos)
            store.audit(c,'provider_demo_connected',{'provider':provider,'mode':'visual_demo','records_imported':0})
        return {'status':'demo_connected','provider':provider,'note':'Visual demo only; no OAuth, account access or imported records.'}

    @app.post('/api/models/train',status_code=202)
    def train_model(tasks: BackgroundTasks):
        job=service.start_training();tasks.add_task(service.run_training,job)
        return {'id':job,'state':'running'}

    @app.get('/api/models/training/{job_id}')
    def training_job(job_id: str):
        result=store.training_job(job_id)
        if not result: raise HTTPException(404,'Training job not found')
        return result

    @app.get('/api/models/current')
    def current_model(): return store.model()

    @app.post('/api/monitor/check',status_code=202)
    def monitor_now(tasks: BackgroundTasks):
        tasks.add_task(service.monitor_tick,force=True)
        return {'state':'queued','note':'Monitor will retrieve the forecast and assess exposure. It cannot approve positions.'}

    @app.post('/api/notifications/{notification_id}/read')
    def read_notification(notification_id: int):
        from src.paper_execution import utc_now_iso
        with store.transaction() as c:
            c.execute('UPDATE notifications SET read_at=? WHERE id=?',(utc_now_iso(),notification_id))
        return {'ok':True}

    @app.get('/api/settings', response_model=SettingsInput)
    def settings():
        return store.state('settings')

    @app.put('/api/settings', response_model=SettingsInput)
    def save_settings(settings: SettingsInput):
        return store.set_settings(settings.model_dump())

    @app.post('/api/setup/complete')
    def finish_setup():
        if not store.state('profile'):
            raise Conflict('Save a business profile first.')
        with store.transaction() as c:
            store.put(c, 'setup_complete', True)
            store.audit(c, 'setup_completed', {'hedge_required': False})
        return {'ok': True}

    return app


load_dotenv(Path(__file__).resolve().parent.parent / '.env')
app = create_app()
