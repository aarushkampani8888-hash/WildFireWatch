import asyncio,time,uuid
from typing import TypedDict,Any
from langgraph.graph import StateGraph,START,END
from engine import projection,routes,NODES,EDGES
from backend.geo import geojson
from backend.integrations import detect,extract_frame,mapbox_route,weather
from backend.local_vision import detect_local
from backend.open_routes import open_route
class State(TypedDict,total=False):
    inputs:dict
    sentinel:dict
    projections:list
    route:dict
    events:list
    result:dict
async def sentinel(state):
    d=state['inputs'];start=time.monotonic()
    if d['mode']=='simulation':finding={'smoke_detected':d['smoke'],'confidence':.91 if d['smoke'] else .08,'reason':'Scripted smoke event.' if d['smoke'] else 'Scripted clear-camera event.','source':'simulation'}
    else:
        image=d.get('image') or await extract_frame();finding=await asyncio.to_thread(detect_local,image) if d['mode']=='local' else await detect(image)
    finding['flagged']=finding['smoke_detected'] and finding['confidence']>=d['threshold']
    finding['threshold']=d['threshold']
    return {'sentinel':finding,'events':[{'agent':'Sentinel','message':finding['reason'],'elapsed_ms':round((time.monotonic()-start)*1000)}]}
async def propagate(state):
    d=state['inputs'];start=time.monotonic()
    if d.get('live_weather'):d={**d,**await weather()}
    projections=[projection(d['wind'],d['humidity'],d['direction'],m) for m in (30,60,120)] if state['sentinel']['flagged'] else []
    return {'inputs':d,'projections':projections,'events':state['events']+[{'agent':'Propagator','message':'Illustrative wind-directed envelopes generated; terrain and fuel are not modeled.' if projections else 'Finding below threshold; propagation skipped.','elapsed_ms':round((time.monotonic()-start)*1000)}]}
async def dispatch(state):
    d=state['inputs'];start=time.monotonic()
    if not state['projections']:route={'path':[],'minutes':None,'excluded':[],'status':'no_detection','source':'none'}
    else:
        p=next(p for p in state['projections'] if p['minutes']==d['horizon'])
        if d['routing'] in ('mapbox','open'):
            if d['closures']:raise ValueError('Synthetic road overrides cannot be applied to real roads. Clear closures or choose synthetic routing.')
            route=await open_route(p) if d['routing']=='open' else await mapbox_route(p)
        else:route={**routes(p,d['congestion'],d['closures']),'source':'synthetic graph'}
    return {'route':route,'events':state['events']+[{'agent':'Dispatcher','message':'Candidate route ready for human review.' if route['path'] else 'No corridor generated. Human review required.','elapsed_ms':round((time.monotonic()-start)*1000)}]}
async def finish(state):
    d=state['inputs'];result={'id':str(uuid.uuid4())[:8],'time':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'sentinel':state['sentinel'],'weather':{'wind':d['wind'],'humidity':d['humidity'],'direction':d['direction'],'source':d.get('weather_source','scenario controls')},'projections':state['projections'],'route':state['route'],'nodes':NODES,'edges':EDGES,'horizon':d['horizon'],'events':state['events'],'mode':d['mode'],'review':'pending','limitations':['Assumed ignition location; frame does not geolocate smoke','Unvalidated spread model without terrain or fuel','Route candidates are not evacuation instructions']};result['geojson']=geojson(result);return {'result':result}
graph=StateGraph(State)
for name,fn in [('sentinel',sentinel),('propagator',propagate),('dispatcher',dispatch),('finish',finish)]:graph.add_node(name,fn)
graph.add_edge(START,'sentinel');graph.add_edge('sentinel','propagator');graph.add_edge('propagator','dispatcher');graph.add_edge('dispatcher','finish');graph.add_edge('finish',END)
pipeline=graph.compile()
