"""Evidence triage agents: ML findings plus explicit, auditable decision rules."""
from datetime import datetime, timezone
from statistics import median
from typing import TypedDict
from fastapi import APIRouter
from langgraph.graph import StateGraph, START, END
from backend.reporting import reports
from backend.investigation import packet
router=APIRouter()
class State(TypedDict,total=False):
    evidence:dict
    report:dict
    agents:list
    action:str
    rank:int

def sentinel(s):
    p=s['evidence']; f=p['finding']
    return {'agents':[{'name':'Sentinel','method':'Trained YOLO11n inference result','result':'Smoke candidate' if f['smoke_detected'] else 'Below detector threshold','status':'complete'}]}

def temporal_agent(s):
    rows=s['evidence']['temporal']['frames'];video=s['evidence'].get('video_evidence')
    if video:
        n,total=video['frames_flagged'],video['frames_analyzed']
        result=f'{n}/{total} sampled video frames above threshold; gaps between samples remain unknown.'
        count=total
    else:
        n=sum(f['candidate'] for f in rows);count=len(rows)
        result=f'{n}/{count} recent distinct frames above threshold' if rows else 'No temporal evidence attached to this observation'
    return {'agents':s['agents']+[{'name':'Temporal analyst','method':'Distinct sampled-frame comparison' if video else 'Timestamp deduplication and image-plane comparison','result':result,'status':'complete' if count>=2 else 'needs evidence'}]}

def corroborator(s):
    p=s['evidence'];thermal=len(p['thermal_observations']);reports=len(p.get('nearby_reports',[]))
    result=f'{reports} nearby report(s) · {thermal} thermal match(es); operator must verify they refer to the same event.' if reports or thermal else 'No nearby reports or loaded thermal observations matched the time/distance filter.'
    return {'agents':s['agents']+[{'name':'Evidence linker','method':'Report + thermal time/distance matching','result':result,'status':'matches found' if reports or thermal else 'needs evidence'}]}

def planner(s):
    r=s['report'];p=s['evidence'];age=(datetime.now(timezone.utc)-datetime.fromisoformat(r['observed_at'].replace('Z','+00:00'))).total_seconds()/60
    candidate=p['finding']['smoke_detected'];video=p.get('video_evidence');paired=len(p['temporal']['frames'])>=2 or bool(video and video['frames_analyzed']>=2);thermal=bool(p['thermal_observations']);community=bool(p.get('nearby_reports'))
    if r.get('reference'):rank=0;action='Review reference-image performance separately from live operations.'
    elif r['status'] in ('dismissed','escalated'):rank=0;action='Decision recorded. Check the saved notes before taking further action.'
    elif age>60:rank=1;action='Request a fresh observation before interpreting this as a current threat.'
    elif candidate and (thermal or community):rank=4;action='Compare the smoke candidate with nearby reports and thermal observations; verify timing and source before linking them.'
    elif candidate and paired:rank=3;action='Review the sampled frames and possible cloud/light confounders; seek an independent view.'
    elif candidate:rank=2;action='Collect another frame and inspect a nearby camera before confirming the observation.'
    else:rank=1;action='Inspect the original image; below-threshold output does not establish safety.'
    agents=s['agents']
    geographic=r.get('geographic_assessment') or {}
    data=geographic.get('data') or {}
    screening=data.get('screening') or {}
    index=screening.get('index')
    if geographic.get('status')=='available' and index is not None:
        factors=screening.get('factors') or []
        vegetation=next((f for f in factors if f.get('name')=='Mapped vegetation'),None)
        fuel_value=(vegetation or {}).get('value') or 'mapped fuel data unavailable'
        context_result=(f"Report-point context: {screening.get('label','Environmental screen')} ({index}/100; {screening.get('coverage_percent',0)}% factor coverage); "
                        f"mapped vegetation: {fuel_value}. Separate from image score and not a fire probability.")
        agents=agents+[{'name':'Geographic context','method':'California weather, terrain and mapped-fuel heuristic','result':context_result,'status':'available'}]
        # Environmental context can move a fresh report up for review, but
        # never confirms a fire or changes the image-model confidence.
        if age <= 60 and r['status'] not in ('dismissed','escalated','confirmed_fire'):
            if index >= 75 and rank < 3:
                rank=3
                action='Review this report promptly alongside its mapped fuel, terrain and current weather context; the environmental screen is not fire confirmation.'
            elif index >= 50 and rank < 2:
                rank=2
                action='Review the report with its elevated environmental context; the screening index is not fire confirmation.'
    elif geographic.get('status') in ('pending','unavailable'):
        message='Environmental context is still loading.' if geographic.get('status')=='pending' else 'Environmental context unavailable; no geographic values were inferred.'
        agents=agents+[{'name':'Geographic context','method':'California weather, terrain and mapped-fuel assessment','result':message,'status':geographic.get('status')}]
    return {'action':action,'rank':rank,'agents':agents+[{'name':'Investigation planner','method':'Explicit freshness, evidence and review-status rules','result':action,'status':'complete'}]}

graph=StateGraph(State)
for name,fn in [('sentinel',sentinel),('temporal',temporal_agent),('corroborator',corroborator),('planner',planner)]:graph.add_node(name,fn)
graph.add_edge(START,'sentinel');graph.add_edge('sentinel','temporal');graph.add_edge('temporal','corroborator');graph.add_edge('corroborator','planner');graph.add_edge('planner',END)
triage=graph.compile()

@router.get('/api/mission')
async def mission():
    from backend.live_camera import monitor, CAMERAS
    rows=[r for r in reports() if not r.get('demo')][:50];items=[]
    for r in rows:
        p=packet(r['id'],submissions=rows);result=await triage.ainvoke({'report':r,'evidence':p})
        items.append({'id':r['id'],'latitude':r['latitude'],'longitude':r['longitude'],'status':r['status'],'reference':r.get('reference',False),'location':r.get('provenance',{}).get('name') or ('Reference image' if r.get('reference') else f"Observer {r['latitude']:.3f}, {r['longitude']:.3f}"),'observed_at':r['observed_at'],'submitted_at':r['submitted_at'],'candidate':r['finding']['smoke_detected'],'score':r['finding']['confidence'],'geographic_assessment':r.get('geographic_assessment'),'action':result['action'],'rank':result['rank'],'agents':result['agents'],'evidence_checks':{'image':True,'temporal':len(p['temporal']['frames'])>=2 or bool(p.get('video_evidence') and p['video_evidence']['frames_analyzed']>=2),'nearby_reports':bool(p.get('nearby_reports')),'thermal':bool(p['thermal_observations']),'geography':r.get('geographic_assessment',{}).get('status')=='available','human_review':bool(r.get('review'))},'nearby_reports':p.get('nearby_reports',[]),'review':r.get('review')})
    operational=[r for r in items if not r['reference']];waiting=[r for r in operational if r['status'] in ('pending','needs_information')]
    waiting.sort(key=lambda r:(r['rank'],r['observed_at']),reverse=True)
    review_durations=[]
    for row in operational:
        review=row.get('review')
        if not review or not review.get('at') or not row.get('submitted_at'):
            continue
        try:
            submitted=datetime.fromisoformat(row['submitted_at'].replace('Z','+00:00'))
            decided=datetime.fromisoformat(review['at'].replace('Z','+00:00'))
            seconds=(decided-submitted).total_seconds()
        except (TypeError,ValueError):
            continue
        if seconds>=0:
            review_durations.append(seconds)
    return {'generated_at':datetime.now(timezone.utc).isoformat(),'queue':waiting,'reference_count':sum(r['reference'] for r in items),'decisions_recorded':sum(bool(r['review']) for r in operational),'median_review_seconds':round(median(review_durations),1) if review_durations else None,'nearby_report_matches':round(sum(len(r.get('nearby_reports',[])) for r in items)/2),'camera':{'name':monitor.camera['name'],'id':monitor.camera['id'],'latitude':monitor.camera['latitude'],'longitude':monitor.camera['longitude'],'direction':monitor.camera['direction'],'running':bool(monitor.task and not monitor.task.done()),'distinct_frames':len(monitor.frames),'latest_updated_at':monitor.latest['provider_updated_at'] if monitor.latest else None,'message':monitor.message},'cameras':CAMERAS,'selected_camera_id':monitor.camera['id'],'scope':'Four research cameras; one monitored at a time. Observer location is not ignition location. Triage ranks are explicit review rules, not fire probabilities.','community_outcome':'Nearby community reports, camera observations, and loaded thermal detections are time/distance matched for human review; a match does not confirm a shared fire.'}
