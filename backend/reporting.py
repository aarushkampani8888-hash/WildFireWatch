"""Local photo/video reporting and satellite corroboration prototype."""
import asyncio, csv, hashlib, io, json, math, os, re, sqlite3, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, TypedDict
import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict
from langgraph.graph import StateGraph, START, END
from backend.local_vision import detect_local
from backend.external_review import review_images as external_review_images

ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = Path(os.environ.get('REPORT_VIDEO_DIR', ROOT/'data/report-videos'))
router = APIRouter()
external_review_lock = asyncio.Lock()
HOTSPOTS = []

class LandscapePoint(BaseModel):
    latitude:float=Field(ge=-90,le=90)
    longitude:float=Field(ge=-180,le=180)

DEMO_HOTSPOTS = [{'id':'demo-thermal-1','latitude':39.82,'longitude':-121.44,
    'observed_at':'2021-07-22T18:30:00Z','source':'Staged thermal anomaly',
    'confidence':'scenario','demo':True,'note':'Invented hotspot for workflow replay; not a NASA detection.'}]

def db():
    path = Path(os.environ.get('REPORT_DB', ROOT/'data/reports.sqlite'))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    return conn

def save(report):
    with db() as conn:
        conn.execute('INSERT OR REPLACE INTO reports VALUES (?, ?)', (report['id'],json.dumps(report)))

def read(report_id):
    with db() as conn: row=conn.execute('SELECT payload FROM reports WHERE id=?',(report_id,)).fetchone()
    if not row:raise HTTPException(404,'Report not found')
    return json.loads(row[0])

def summary(report):
    result={k:v for k,v in report.items() if k not in ('image','video_storage_key')}
    if report.get('video_evidence'):
        result['video_evidence']={**report['video_evidence'],'frames':[
            {k:v for k,v in frame.items() if k!='image'}
            for frame in report['video_evidence']['frames']]}
    return result

def distance(a,b):
    lat1,lat2=map(math.radians,(a['latitude'],b['latitude']))
    dlat=lat2-lat1;dlon=math.radians(b['longitude']-a['longitude'])
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371*2*math.asin(min(1,math.sqrt(h)))

class Submission(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    image:str=Field(max_length=7_000_000)
    latitude:float=Field(ge=32,le=42.1)
    longitude:float=Field(ge=-124.6,le=-114)
    observed_at:datetime
    direction:float|None=Field(None,ge=0,le=360)
    notes:str=Field('',max_length=1000)
    demo:bool=False
    reference:bool=False

class MapPointSubmission(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    latitude:float=Field(ge=32,le=42.1)
    longitude:float=Field(ge=-124.6,le=-114)
    notes:str=Field('',max_length=1000)
    action:Literal['confirmed_fire','escalated']|None=None
    decision_notes:str=Field('',max_length=1000)

class Decision(BaseModel):
    decision:Literal['confirmed_fire','escalated','dismissed','needs_information']
    notes:str=Field('',max_length=1000)
    incident_latitude:float|None=Field(None,ge=32,le=42.1)
    incident_longitude:float|None=Field(None,ge=-124.6,le=-114)
    decision_latitude:float|None=Field(None,ge=32,le=42.1)
    decision_longitude:float|None=Field(None,ge=-124.6,le=-114)

class ThermalReview(BaseModel):
    observation_id:str=Field(min_length=1,max_length=160)
    latitude:float=Field(ge=32,le=42.1)
    longitude:float=Field(ge=-124.6,le=-114)
    observed_at:datetime
    source:str=Field('NASA FIRMS',max_length=120)
    satellite:str=Field('unknown',max_length=80)
    confidence:str=Field('unknown',max_length=40)
    demo:bool=False

class State(TypedDict,total=False):
    report:dict

async def emit(report,stage,message):
    from backend.app import hub
    event={'agent':stage,'message':message,'time':time.time()}
    report['events'].append(event)
    await hub.publish({'type':'report_stage','report_id':report['id'],'stage':stage,'event':event})

async def intake(state):
    r=state['report'];source='Video and observer location' if r.get('video_evidence') else 'Photo and observer location';await emit(r,'Intake',f'{source} received; fire location remains unverified.')
    return {'report':r}

async def sentinel(state):
    r=state['report']
    if 'finding' not in r:r['finding']=await asyncio.to_thread(detect_local,r['image'])
    if r.get('video_evidence'):
        v=r['video_evidence'];message=f"YOLO analyzed {v['frames_analyzed']} sampled video frames; {v['frames_flagged']} exceeded the smoke threshold. Highest frame score is uncalibrated."
    else:message=f"YOLO analysis complete: {len(r['finding'].get('boxes',[]))} candidate regions. Score is uncalibrated."
    await emit(r,'Sentinel',message)
    return {'report':r}

async def correlate(state):
    r=state['report'];candidates=[] if r.get('reference') else (DEMO_HOTSPOTS if r['demo'] else HOTSPOTS)
    matches=[]
    observed=datetime.fromisoformat(r['observed_at'].replace('Z','+00:00'))
    for h in candidates:
        t=datetime.fromisoformat(h['observed_at'].replace('Z','+00:00'))
        km=distance(r,h);hours=abs((observed-t).total_seconds())/3600
        if km<=25 and hours<=24:matches.append({**h,'distance_km':round(km,2),'time_difference_hours':round(hours,2)})
    r['matches']=sorted(matches,key=lambda h:h['distance_km'])
    r['status']='pending';await emit(r,'Correlator',f'{len(matches)} observations within 25 km / 24 hours. Proximity does not establish a common fire.')
    await emit(r,'Review','Awaiting operator decision. No authority has been notified.')
    return {'report':r}

graph=StateGraph(State)
for name,fn in [('intake',intake),('sentinel',sentinel),('correlator',correlate)]:graph.add_node(name,fn)
graph.add_edge(START,'intake');graph.add_edge('intake','sentinel');graph.add_edge('sentinel','correlator');graph.add_edge('correlator',END)
report_pipeline=graph.compile()

async def process(data, *, finding=None, provenance=None, attachments=None):
    if data.observed_at.tzinfo is None:raise HTTPException(422,'Observation time must include a timezone')
    if data.observed_at.timestamp()>time.time()+300:raise HTTPException(422,'Observation cannot be in the future')
    r={**data.model_dump(mode='json'),'id':uuid.uuid4().hex[:12],'submitted_at':datetime.now(timezone.utc).isoformat(),'events':[],'status':'analyzing','location_role':'reference test coordinates, not capture location' if data.reference else 'observer, not ignition'}
    if finding is not None:r['finding']=finding
    if provenance is not None:r['provenance']=provenance
    if attachments:r.update(attachments)
    try:result=await report_pipeline.ainvoke({'report':r});r=result['report']
    except ValueError as e:raise HTTPException(422,str(e)) from None
    except Exception:raise HTTPException(503,'Local detector unavailable. No simulation was substituted.') from None
    if not data.reference:
        r['geographic_assessment']=({'status':'not_assessed','message':'Staged observations are excluded from live geographic screening.'}
                                     if data.demo else {'status':'pending'})
    save(r)
    from backend.app import hub
    await hub.publish({'type':'report_ready','report':summary(r)})
    # Environmental context is a separate screening signal. Fetch it after the
    # report is safely in the inbox so slow/unavailable public data never blocks
    # report intake or changes the image-only detector result.
    if not data.reference and not data.demo:
        _start_geographic_assessment(r['id'], r['latitude'], r['longitude'])
    return r


@router.post('/api/map-point-reports')
async def create_map_point_report(data:MapPointSubmission):
    """Create an inbox case and optional human decision from one plotted map point."""
    now=datetime.now(timezone.utc).isoformat()
    status=data.action or 'pending'
    report={
        'id':uuid.uuid4().hex[:12], 'kind':'map_point_observation',
        'latitude':data.latitude, 'longitude':data.longitude,
        'observed_at':now, 'submitted_at':now, 'image':None, 'notes':data.notes,
        'demo':False, 'reference':False,
        'location_role':'operator-plotted map point; no image evidence attached',
        'status':status,
        'finding':{'smoke_detected':False,'confidence':None,'boxes':[],
            'source':'Operator map point',
            'reason':'No image or video was attached. This is a map location for operator review, not an automated detection.'},
        'geographic_assessment':{'status':'pending'},
        'provenance':{'kind':'map_point','source':'Operator-plotted California map point'},
        'events':[{'agent':'Review','message':(
            'Operator-plotted map point added to the inbox for human review.' if not data.action else
            'Operator recorded a human fire confirmation at the plotted point.' if data.action=='confirmed_fire' else
            'Operator marked the plotted point for escalation review; no agency was notified.'),
            'time':time.time()}],
    }
    if data.action:
        report['review']={
            'decision':data.action,
            'notes':data.decision_notes,
            'incident_latitude':None,
            'incident_longitude':None,
            'decision_latitude':data.latitude,
            'decision_longitude':data.longitude,
            'at':now,
        }
    save(report)
    from backend.app import hub
    await hub.publish({'type':'report_ready','report':summary(report)})
    _start_geographic_assessment(report['id'], report['latitude'], report['longitude'])
    return summary(report)


_geographic_tasks = set()


def _start_geographic_assessment(report_id, latitude, longitude):
    task = asyncio.create_task(_assess_report_geography(report_id, latitude, longitude))
    _geographic_tasks.add(task)
    task.add_done_callback(_geographic_tasks.discard)


async def _assess_report_geography(report_id, latitude, longitude):
    try:
        from backend.landscape_risk import assess
        assessment = await assess(latitude, longitude)
        report = read(report_id)
        report['geographic_assessment'] = {
            'status': 'available',
            'assessed_at': assessment['assessed_at'],
            'data': assessment,
        }
    except Exception as error:
        report = read(report_id)
        detail = getattr(error, 'detail', None)
        report['geographic_assessment'] = {
            'status': 'unavailable',
            'message': str(detail or 'Public geographic context could not be retrieved; no values were substituted.'),
        }
    save(report)
    from backend.app import hub
    await hub.publish({'type': 'report_ready', 'report': summary(report)})

@router.get('/api/reports')
def reports():
    with db() as conn:rows=conn.execute('SELECT payload FROM reports ORDER BY rowid DESC LIMIT 100').fetchall()
    return [summary(json.loads(row[0])) for row in rows]

@router.get('/api/reports/{report_id}')
def detail(report_id:str):
    report=read(report_id);report.pop('video_storage_key',None);return report

@router.post('/api/reports/{report_id}/second-opinion')
async def second_opinion(report_id:str):
    """Run one explicit, bounded external model review for this report."""
    if not os.environ.get('OPENAI_API_KEY'):
        raise HTTPException(503,'External vision review is not configured on this backend.')
    async with external_review_lock:
        report=read(report_id)
        if report.get('external_opinion'):
            raise HTTPException(409,'An external review is already recorded for this report.')

        if report.get('video_evidence'):
            source_frames=report['video_evidence'].get('frames',[])
            if not source_frames:
                raise HTTPException(422,'No sampled video frames are available for external review.')
            # Choose the strongest local candidate, then one temporally distinct frame.
            first=max(source_frames,key=lambda frame:float(frame.get('confidence',0)))
            remainder=[frame for frame in source_frames if frame is not first]
            chosen=[first]
            if remainder:
                chosen.append(max(remainder,key=lambda frame:abs(float(frame.get('offset_seconds',0))-float(first.get('offset_seconds',0)))))
            images=[frame['image'] for frame in chosen]
            local=[bool(frame.get('smoke_detected')) for frame in chosen]
            offsets=[round(float(frame.get('offset_seconds',0)),2) for frame in chosen]
            kind='video'
        else:
            image=report.get('image')
            if not image:
                raise HTTPException(422,'No source image is available for external review.')
            images=[image]
            local=[bool(report.get('finding',{}).get('smoke_detected'))]
            offsets=[None]
            kind='photo'

        try:
            result=await external_review_images(images)
        except ValueError as error:
            raise HTTPException(422,str(error)) from None
        except Exception:
            # Never return provider payloads, URLs, or credential-related details.
            raise HTTPException(502,'External vision review failed. The local finding is unchanged.') from None

        comparisons=[]
        for index, frame in enumerate(result['frames']):
            comparisons.append({**frame,'local_smoke_detected':local[index],
                                'offset_seconds':offsets[index]})
        mismatch=any(frame['smoke_detected'] != frame['local_smoke_detected'] for frame in comparisons)
        if mismatch:
            agreement='disagreement'
            next_step='Review the original media and seek another independent observation.'
        elif any(frame['smoke_detected'] for frame in comparisons):
            agreement='both_flagged'
            next_step='Both models flagged at least one reviewed frame. Inspect it visually and corroborate with another source before escalation.'
        else:
            agreement='both_below_threshold'
            next_step='A below-threshold result does not rule out smoke; review context and additional frames.'
        report['external_opinion']={
            'provider':result['provider'],'model':result['model'],
            'requested_at':datetime.now(timezone.utc).isoformat(),
            'media_type':kind,'agreement':agreement,'frames':comparisons,
            'next_step':next_step,
            'limitations':'Advisory only. Scores are uncalibrated and are not combined into a fire probability or incident confirmation.',
        }
        await emit(report,'External reviewer',f"{result['provider']} {result['model']} reviewed {len(images)} {kind} frame(s); result: {agreement}. Human review remains required.")
        save(report)
        from backend.app import hub
        await hub.publish({'type':'report_ready','report':summary(report)})
        report.pop('video_storage_key',None)
        return report

@router.post('/api/reports')
async def submit(data:Submission):return await process(data)

@router.post('/api/reports/video')
async def submit_video(
    request:Request,
    latitude:float=Query(ge=32,le=42.1),
    longitude:float=Query(ge=-124.6,le=-114),
    observed_at:datetime=Query(...),
    direction:float|None=Query(None,ge=0,le=360),
    notes:str=Query('',max_length=1000),
    reference:bool=Query(False),
    filename:str=Query('uploaded-video',max_length=100),
):
    from backend.video_evidence import MAX_VIDEO_BYTES, MIME_EXTENSIONS, extract_frames
    content_type=request.headers.get('content-type','')
    mime=content_type.lower().split(';',1)[0].strip()
    if mime not in MIME_EXTENSIONS:
        raise HTTPException(415,'Choose an MP4, WebM, or QuickTime video.')
    if observed_at.tzinfo is None:
        raise HTTPException(422,'Observation time must include a timezone.')
    if observed_at.timestamp()>time.time()+300:
        raise HTTPException(422,'Observation cannot be in the future.')
    raw=bytearray()
    async for chunk in request.stream():
        if len(raw)+len(chunk)>MAX_VIDEO_BYTES:
            raise HTTPException(413,'Video exceeds the 25 MB upload limit.')
        raw.extend(chunk)
    try:
        duration,frames,extension=await asyncio.to_thread(extract_frames,bytes(raw),mime)
        results=[]
        for frame in frames:
            finding=await asyncio.to_thread(detect_local,frame['image'])
            results.append({**frame,'finding':finding})
    except ValueError as error:
        raise HTTPException(422,str(error)) from None
    except Exception:
        raise HTTPException(503,'Video decoding or local model inference is unavailable. No substitute analysis was used.') from None

    best=max(results,key=lambda frame:frame['finding']['confidence'])
    flagged=sum(frame['finding']['smoke_detected'] for frame in results)
    peak=best['finding']
    aggregate={**peak,'smoke_detected':flagged>0,'confidence':peak['confidence'],
        'reason':f"Smoke candidates above threshold in {flagged}/{len(results)} sampled frames; highest per-frame score {peak['confidence']:.3f} is uncalibrated. Human review required.",
        'frame_count':len(results),'positive_frame_count':flagged}
    video_evidence={'duration_seconds':duration,'frames_analyzed':len(results),'frames_flagged':flagged,
        'sampling_note':'Up to six evenly spaced, distinct frames; unsampled moments may contain smoke.',
        'frames':[{'offset_seconds':frame['offset_seconds'],'image':frame['image'],
            'smoke_detected':frame['finding']['smoke_detected'],'confidence':frame['finding']['confidence'],
            'boxes':frame['finding'].get('boxes',[])} for frame in results]}
    safe_name=filename.replace('\\','/').split('/')[-1][:100] or f'uploaded-video{extension}'
    VIDEO_DIR.mkdir(parents=True,exist_ok=True)
    key=uuid.uuid4().hex+extension
    stored=VIDEO_DIR/key
    stored.write_bytes(raw)
    try:
        report=await process(Submission(image=best['image'],latitude=latitude,longitude=longitude,
            observed_at=observed_at,direction=direction,notes=notes,demo=False,reference=reference),
            finding=aggregate,
            provenance={'kind':'uploaded_video','filename':safe_name,'content_type':{'.mp4':'video/mp4','.webm':'video/webm','.mov':'video/quicktime'}[extension],
                'duration_seconds':duration,'frame_count':len(results)},
            attachments={'video_evidence':video_evidence,'video_storage_key':key})
    except Exception:
        stored.unlink(missing_ok=True)
        raise
    report.pop('video_storage_key',None)
    return report

@router.get('/api/reports/{report_id}/video')
def original_video(report_id:str):
    report=read(report_id);key=report.get('video_storage_key')
    if not key or not re.fullmatch(r'[0-9a-f]{32}\.(?:mp4|webm|mov)',key):
        raise HTTPException(404,'Original video is unavailable for this report.')
    path=VIDEO_DIR/key
    if not path.is_file():raise HTTPException(404,'Original video file is unavailable.')
    return FileResponse(path,media_type=report.get('provenance',{}).get('content_type','application/octet-stream'))

@router.post('/api/reports/{report_id}/review')
async def review(report_id:str,data:Decision):
    if (data.decision_latitude is None) != (data.decision_longitude is None):
        raise HTTPException(422,'Provide both decision-marker coordinates, or leave both blank.')
    if data.decision=='confirmed_fire':
        if (data.incident_latitude is None) != (data.incident_longitude is None):
            raise HTTPException(422,'Provide both affected-area coordinates, or leave both blank to record confirmation without a mapped location.')
        if data.incident_latitude is not None:
            from backend.landscape_risk import verify_california
            await verify_california(data.incident_latitude,data.incident_longitude)
    r=read(report_id);r['status']=data.decision;r['review']={**data.model_dump(),'at':datetime.now(timezone.utc).isoformat()}
    save(r)
    from backend.app import hub
    await hub.publish({'type':'report_ready','report':summary(r)})
    r.pop('video_storage_key',None)
    return r

@router.get('/api/location-context')
async def location_context(latitude:float=Query(ge=32,le=42.1),longitude:float=Query(ge=-124.6,le=-114)):
    from backend.geographic_context import context
    return await context(latitude, longitude)

@router.get('/api/landscape-risk')
async def landscape_risk(latitude:float=Query(ge=32,le=42.1),longitude:float=Query(ge=-124.6,le=-114)):
    from backend.landscape_risk import assess
    return await assess(latitude, longitude)

@router.post('/api/landscape-risk/ai-brief')
async def landscape_ai_brief(point:LandscapePoint):
    from backend.landscape_risk import ai_brief
    return await ai_brief(point.latitude, point.longitude)

@router.get('/api/location-weather')
async def location_weather(latitude:float=Query(ge=32,le=42.1),longitude:float=Query(ge=-124.6,le=-114)):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response=await client.get('https://api.open-meteo.com/v1/forecast',params={'latitude':latitude,'longitude':longitude,'current':'relative_humidity_2m,wind_speed_10m,wind_direction_10m','timezone':'UTC'})
            response.raise_for_status();data=response.json()
        return {'current':data['current'],'units':data['current_units'],'latitude':latitude,'longitude':longitude,'source':'Open-Meteo','note':'Current conditions at the observer location, not historical incident weather.'}
    except Exception:raise HTTPException(503,'Weather unavailable; no scenario values substituted') from None

def parse_hotspots(text,source='Imported FIRMS CSV'):
    rows=list(csv.DictReader(io.StringIO(text)))
    if len(rows)>100000:raise ValueError('CSV contains too many rows')
    result=[]
    for row in rows:
        lat,lon=float(row['latitude']),float(row['longitude'])
        if not(32<=lat<=42.1 and -124.6<=lon<=-114):continue
        clock=row['acq_time'].zfill(4);stamp=datetime.fromisoformat(row['acq_date']+'T'+clock[:2]+':'+clock[2:]+':00+00:00')
        result.append({'id':'firms-'+uuid.uuid4().hex[:10],'latitude':lat,'longitude':lon,'observed_at':stamp.isoformat(),'source':source,'confidence':row.get('confidence','unknown'),'satellite':row.get('satellite','unknown'),'demo':False})
    return result[:1000]

class CSVImport(BaseModel):
    csv:str=Field(max_length=5_000_000)

@router.post('/api/satellite/import')
async def import_satellite(data:CSVImport):
    global HOTSPOTS
    try:HOTSPOTS=parse_hotspots(data.csv)
    except (ValueError,KeyError):raise HTTPException(422,'Expected FIRMS CSV with latitude, longitude, acq_date and acq_time') from None
    return {'observations':HOTSPOTS,'source':'User-imported FIRMS-format CSV; provenance not independently verified'}

@router.post('/api/satellite/review')
async def add_thermal_to_review(data:ThermalReview):
    """Create one idempotent inbox case for an operator-selected thermal pixel."""
    stable_id='thermal-'+hashlib.sha256(data.observation_id.encode()).hexdigest()[:20]
    try:
        existing=read(stable_id)
        return summary(existing)
    except HTTPException as error:
        if error.status_code!=404:raise
    observation={'id':data.observation_id,'latitude':data.latitude,'longitude':data.longitude,
        'observed_at':data.observed_at.isoformat(),'source':data.source,'satellite':data.satellite,
        'confidence':data.confidence,'demo':data.demo}
    report={'id':stable_id,'kind':'thermal_observation','latitude':data.latitude,'longitude':data.longitude,
        'observed_at':data.observed_at.isoformat(),'submitted_at':datetime.now(timezone.utc).isoformat(),
        'image':None,'notes':'','demo':data.demo,'reference':False,
        'location_role':'satellite thermal pixel center; not a verified perimeter or ignition location',
        'status':'pending','finding':{'smoke_detected':False,'confidence':None,'boxes':[],
            'source':'Satellite thermal observation','reason':'A thermal anomaly is a review signal, not a wildfire confirmation. Check timing, source, and independent evidence.'},
        'thermal_observation':observation,
        'geographic_assessment':{'status':'pending'} if not data.demo else {'status':'not_assessed','message':'Staged observations are excluded from live geographic screening.'},
        'provenance':{'kind':'thermal_observation','source':data.source,'satellite':data.satellite},
        'events':[{'agent':'Review','message':'Thermal anomaly added to the operator inbox for human review.','time':time.time()}]}
    save(report)
    from backend.app import hub
    await hub.publish({'type':'report_ready','report':summary(report)})
    if not data.demo:
        _start_geographic_assessment(report['id'], report['latitude'], report['longitude'])
    return summary(report)

@router.get('/api/satellite')
async def satellite(live:bool=False):
    global HOTSPOTS
    if live:
        key=os.environ.get('FIRMS_MAP_KEY')
        if not key:raise HTTPException(503,'Add a free NASA FIRMS_MAP_KEY locally, or import a NASA FIRMS CSV. No live data was substituted.')
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                r=await client.get(f'https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_NOAA20_NRT/-124.6,32,-114,42.1/1');r.raise_for_status()
            HOTSPOTS=parse_hotspots(r.text,'NASA FIRMS / VIIRS NOAA-20')
        except Exception:raise HTTPException(503,'NASA FIRMS unavailable. No live observations substituted.') from None
    return {'observations':HOTSPOTS,'configured':bool(os.environ.get('FIRMS_MAP_KEY')),'source':'NASA FIRMS API' if live else 'Loaded observations','fetched_at':datetime.now(timezone.utc).isoformat(),'demo_observations':DEMO_HOTSPOTS}

@router.get('/api/demo/{kind}')
def demo_frame(kind:Literal['smoke','cloud']):
    # Explicitly staged locations. Dataset photos do not represent this California incident.
    manifest=ROOT/'data/combined-smoke/manifest.json'
    import base64
    frame=ROOT/'demo/frames'/f'{kind}.jpg'
    if not frame.exists():raise HTTPException(404,'Bundled demo frame unavailable')
    return {'image':'data:image/jpeg;base64,'+base64.b64encode(frame.read_bytes()).decode(),'source':'D-Fire held-out photo; original capture location/time unavailable','latitude':39.805,'longitude':-121.46,'observed_at':'2021-07-22T18:35:00Z','direction':45,'demo':True,'notes':'Staged workflow replay. This photo is not evidence of a fire at the assigned demonstration location.'}

@router.get('/api/reports/{report_id}/investigation')
def investigation(report_id:str, include_image:bool=False):
    from backend.investigation import packet
    return packet(report_id, include_image)

@router.get('/api/reports/{report_id}/regional-evidence')
async def regional_evidence_for_report(report_id:str):
    report=read(report_id)
    if report.get('reference'):
        raise HTTPException(422,'Reference media coordinates are test values; live regional evidence was not queried.')
    from backend.regional_evidence import regional_evidence
    return await regional_evidence(report['latitude'],report['longitude'],report['observed_at'])
