import asyncio,contextlib,json,os,secrets,time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI,WebSocket,WebSocketDisconnect,HTTPException,Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel,Field,ConfigDict
from backend.pipeline import pipeline
from backend.integrations import weather
from backend.local_vision import available as local_model_available
ROOT=Path(__file__).resolve().parents[1]
class Scenario(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    wind:float=Field(24,ge=0,le=150)
    humidity:float=Field(22,ge=0,le=100)
    direction:float=Field(270,ge=0,le=360)
    congestion:float=Field(1.4,ge=1,le=4)
    horizon:Literal[30,60,120]=60
    threshold:float=Field(.8,ge=0,le=1)
    smoke:bool=True
    mode:Literal['simulation','vision','local']='simulation'
    routing:Literal['synthetic','mapbox','open']='synthetic'
    image:str|None=Field(None,max_length=7_000_000)
    closures:list[Literal['community-junction','junction-ridge','ridge-east','east-shelter','junction-south','south-shelter','community-west','west-south']]=Field(default_factory=list,max_length=8)
    live_weather:bool=False
    weather_source:str=Field('scenario controls',max_length=200)
class Monitor(BaseModel):
    enabled:bool
    interval:int=Field(8,ge=5,le=300)
    scenario:Scenario=Field(default_factory=Scenario)
class Review(BaseModel):
    incident_id:str=Field(max_length=50)
    decision:Literal['acknowledged','rejected']
class Sensors(BaseModel):
    wind:float=Field(ge=0,le=150)
    humidity:float=Field(ge=0,le=100)
    direction:float=Field(ge=0,le=360)
    model_config=ConfigDict(allow_inf_nan=False,extra='forbid')
class Hub:
    def __init__(self):
        self.clients=set();self.latest=None;self.events=[];self.monitor=None;self.lock=asyncio.Lock();self.sensors=None;self.sequence=0
    async def publish(self,event):
        self.sequence+=1;event={**event,'sequence':self.sequence,'time':time.time()};self.events.append(event);self.events=self.events[-100:]
        for q in tuple(self.clients):
            if q.full():q.get_nowait()
            q.put_nowait(event)
    async def execute(self,scenario):
        async with self.lock:
            await self.publish({'type':'pipeline_started','mode':scenario.mode})
            inputs=scenario.model_dump()
            if self.sensors and not inputs['live_weather']:inputs.update(self.sensors)
            try:
                result=None
                async for update in pipeline.astream({'inputs':inputs},stream_mode='updates'):
                    for stage,value in update.items():
                        if stage=='finish':result=value['result']
                        else:await self.publish({'type':'agent_event','stage':stage,'event':value.get('events',[])[-1] if value.get('events') else {},'sentinel':value.get('sentinel')})
                self.latest=result;await self.publish({'type':'incident','incident':result});return result
            except asyncio.CancelledError:
                await self.publish({'type':'pipeline_cancelled'});raise
            except Exception as e:
                # Never expose provider URLs, tokens, or raw HTTP exceptions to clients.
                self.latest=None
                message=str(e) if isinstance(e,ValueError) else 'Integration failed. Check configured provider access; no simulation was substituted.'
                await self.publish({'type':'error','message':message});raise HTTPException(502,message)
    async def loop(self,config):
        await self.publish({'type':'monitor','enabled':True,'interval':config.interval})
        try:
            while True:
                try:await self.execute(config.scenario)
                except HTTPException:pass
                await asyncio.sleep(config.interval)
        finally:await self.publish({'type':'monitor','enabled':False})
hub=Hub()
@asynccontextmanager
async def lifespan(app):
    yield
    from backend.live_camera import monitor as camera_monitor
    await camera_monitor.stop()
    if hub.monitor:
        hub.monitor.cancel()
        with contextlib.suppress(asyncio.CancelledError):await hub.monitor
app=FastAPI(title='WildfireWatch',lifespan=lifespan)
from backend.auth import router as auth_router, authorized
app.include_router(auth_router)
@app.middleware('http')
async def bounded_request(request,call_next):
    try: length=int(request.headers.get('content-length','0') or '0')
    except ValueError: return JSONResponse({'detail':'Invalid content length'},400)
    max_bytes=27_000_000 if request.url.path=='/api/reports/video' else 8_000_000
    if length>max_bytes:return JSONResponse({'detail':'Video uploads are limited to 25 MB; other requests are limited to 8 MB.' if max_bytes>8_000_000 else 'Request exceeds 8 MB.'},413)
    origin=request.headers.get('origin','')
    allowed=os.environ.get('ALLOWED_ORIGINS','http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:8787,http://localhost:8787,http://127.0.0.1:5173,http://localhost:5173').split(',')
    if request.method=='POST' and origin and origin not in allowed:return JSONResponse({'detail':'Origin not allowed'},403)
    if request.url.path.startswith('/api/') and request.url.path not in ('/api/auth/status','/api/auth/login','/api/health') and not authorized(request.cookies):
        return JSONResponse({'detail':'Operator sign-in required'},401)
    response=await call_next(request)
    if request.url.path.startswith('/api/'):response.headers['Cache-Control']='no-store'
    return response
@app.get('/api/health')
async def health():return {'ready':local_model_available()}
@app.get('/api/status')
async def status():
    return {'backend':'FastAPI + LangGraph','vision_available':bool(os.environ.get('OPENAI_API_KEY')),'external_vision_available':bool(os.environ.get('OPENAI_API_KEY')),'external_vision_model':os.environ.get('OPENAI_VISION_MODEL','gpt-4.1-mini'),'local_vision_available':local_model_available(),'camera_available':bool(os.environ.get('CAMERA_SOURCE')),'mapbox_available':bool(os.environ.get('MAPBOX_ACCESS_TOKEN')),'open_routes_available':True,'mapbox_public_token':os.environ.get('MAPBOX_PUBLIC_TOKEN',''),'monitoring':bool(hub.monitor and not hub.monitor.done()),'incident':hub.latest}
@app.get('/api/weather')
async def live_weather():
    try:return await weather()
    except Exception:raise HTTPException(502,'Weather provider unavailable.')
@app.get('/api/response-resources')
async def nearby_response_resources(latitude:float,longitude:float):
    # This demo surfaces California evacuation records only; reject malformed or
    # out-of-state points rather than implying the source covers them.
    if not (-90<=latitude<=90 and -180<=longitude<=180):raise HTTPException(422,'Invalid coordinate.')
    if not (32.4<=latitude<=42.1 and -124.5<=longitude<=-114.0):raise HTTPException(422,'In-app response data is available for California points only.')
    from backend.response_resources import response_resources
    return await response_resources(latitude,longitude)
@app.post('/api/run')
async def run_scenario(scenario:Scenario):return await hub.execute(scenario)
@app.post('/api/monitor')
async def monitoring(config:Monitor):
    if hub.monitor:
        hub.monitor.cancel()
        with contextlib.suppress(asyncio.CancelledError):await hub.monitor
        hub.monitor=None
    if config.enabled:hub.monitor=asyncio.create_task(hub.loop(config))
    return {'enabled':config.enabled,'interval':config.interval}
@app.post('/api/review')
async def review(item:Review):
    async with hub.lock:
        if not hub.latest or item.incident_id!=hub.latest['id']:raise HTTPException(409,'Incident changed. Review the latest incident.')
        hub.latest={**hub.latest,'review':item.decision};await hub.publish({'type':'incident','incident':hub.latest});return hub.latest
@app.post('/api/sensors')
async def sensor_webhook(data:Sensors,request:Request):
    key=os.environ.get('SENSOR_WEBHOOK_TOKEN')
    if not key or not secrets.compare_digest(request.headers.get('authorization',''),'Bearer '+key):raise HTTPException(401,'Webhook authentication required.')
    hub.sensors={**data.model_dump(),'weather_source':'authenticated sensor webhook'}
    await hub.publish({'type':'sensor_update','weather':hub.sensors});return {'accepted':True}
@app.websocket('/ws')
async def socket(ws:WebSocket):
    if not authorized(ws.cookies):
        await ws.close(code=1008);return
    # Local single-operator prototype; prevent unrelated browser origins from attaching.
    origin=ws.headers.get('origin','');allowed=os.environ.get('ALLOWED_ORIGINS','http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:8787,http://localhost:8787,http://127.0.0.1:5173,http://localhost:5173').split(',')
    if origin and origin not in allowed:await ws.close(code=1008);return
    await ws.accept();q=asyncio.Queue(maxsize=32);hub.clients.add(q)
    await ws.send_json({'type':'snapshot','incident':hub.latest,'monitoring':bool(hub.monitor and not hub.monitor.done()),'events':hub.events[-10:]})
    async def sender():
        while True:
            event=await q.get()
            if not authorized(ws.cookies):
                await ws.close(code=1008);return
            await ws.send_json(event)
    task=asyncio.create_task(sender())
    try:
        while True:await ws.receive_text()
    except (WebSocketDisconnect,RuntimeError):pass
    finally:
        hub.clients.discard(q);task.cancel()
        with contextlib.suppress(asyncio.CancelledError):await task
from backend.reporting import router as reporting_router
app.include_router(reporting_router)
from backend.live_camera import router as camera_router
app.include_router(camera_router)
from backend.mission import router as mission_router
app.include_router(mission_router)

if (ROOT/'dist').exists():app.mount('/',StaticFiles(directory=ROOT/'dist',html=True),name='frontend')
