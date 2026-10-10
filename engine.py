"""Transparent scenario engine. All geometry uses a synthetic kilometer grid."""
import math, heapq, time, uuid
NODES={'community':(3,6),'junction':(5,6),'ridge':(6,4),'east':(9,4),'south':(5,9),'shelter':(10,9),'west':(1,8)}
EDGES=[('community','junction',3),('junction','ridge',3),('ridge','east',4),('east','shelter',5),('junction','south',4),('south','shelter',6),('community','west',3),('west','south',6)]
def projection(wind,humidity,direction,minutes):
    # Illustrative ellipse, NOT a calibrated fire behavior model.
    a=.25+minutes/60*(.5+wind*.045)*(1-humidity*.006)
    b=.2+minutes/60*.35
    theta=math.radians((direction+180)%360)
    dx,dy=math.sin(theta),-math.cos(theta)
    center=(6+dx*a*.55,5+dy*a*.55)
    points=[]
    for i in range(65):
        t=i*math.tau/64
        points.append([center[0]+dx*a*math.cos(t)-dy*b*math.sin(t),center[1]+dy*a*math.cos(t)+dx*b*math.sin(t)])
    return {'minutes':minutes,'points':points,'center':center,'a':a,'b':b,'direction':direction}
def inside(point,p):
    theta=math.radians((p['direction']+180)%360); dx,dy=math.sin(theta),-math.cos(theta)
    x,y=point[0]-p['center'][0],point[1]-p['center'][1]
    return ((x*dx+y*dy)/p['a'])**2+((-x*dy+y*dx)/p['b'])**2<=1

def routes(p,congestion=1,closures=()):
    graph={n:[] for n in NODES}; excluded=[]
    for a,b,cost in EDGES:
        # Sample entire road segment conservatively against the selected horizon.
        hit=any(inside((NODES[a][0]+(NODES[b][0]-NODES[a][0])*i/100,NODES[a][1]+(NODES[b][1]-NODES[a][1])*i/100),p) for i in range(101))
        key=a+'-'+b
        if hit or key in closures: excluded.append({'edge':key,'reason':'projected hazard' if hit else 'operator closure'}); continue
        weight=cost*(congestion if 'south' in (a,b) else 1)
        graph[a].append((b,weight)); graph[b].append((a,weight))
    q=[(0,'community',['community'])]; seen=set()
    while q:
        cost,n,path=heapq.heappop(q)
        if n in seen: continue
        seen.add(n)
        if n=='shelter': return {'path':path,'minutes':round(cost,1),'excluded':excluded,'status':'candidate'}
        for nxt,w in graph[n]:
            if nxt not in seen: heapq.heappush(q,(cost+w,nxt,path+[nxt]))
    return {'path':[],'minutes':None,'excluded':excluded,'status':'no_route'}

def run(data,sentinel=None):
    wind=float(data.get('wind',24)); humidity=float(data.get('humidity',22)); direction=float(data.get('direction',270)); horizon=int(data.get('horizon',60)); congestion=float(data.get('congestion',1.4))
    if not all(math.isfinite(x) for x in (wind,humidity,direction,congestion)) or not (0<=wind<=150 and 0<=humidity<=100 and 0<=direction<=360 and horizon in (30,60,120) and 1<=congestion<=4): raise ValueError('Scenario values are outside supported ranges.')
    sentinel=sentinel or {'smoke_detected':True,'confidence':.91,'reason':'Scripted smoke event in the synthetic Ridge camera scene.','source':'simulation'}
    projections=[projection(wind,humidity,direction,m) for m in (30,60,120)] if sentinel['smoke_detected'] else []
    route=routes(next(p for p in projections if p['minutes']==horizon),congestion,data.get('closures',[])) if projections else {'path':[],'minutes':None,'excluded':[],'status':'no_detection'}
    return {'id':str(uuid.uuid4())[:8],'time':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'sentinel':sentinel,'weather':{'wind':wind,'humidity':humidity,'direction':direction,'source':data.get('weather_source','scenario controls')},'projections':projections,'route':route,'nodes':NODES,'edges':EDGES,'horizon':horizon,'events':[{'agent':'Sentinel','message':sentinel['reason']},{'agent':'Propagator','message':f'Generated illustrative 30 / 60 / 120 minute envelopes.' if projections else 'No smoke detected; propagation skipped.'},{'agent':'Dispatcher','message':f"Candidate corridor: {' → '.join(route['path'])}" if route['path'] else 'No corridor generated. Human review required.'}]}
