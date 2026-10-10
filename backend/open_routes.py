"""Key-free road candidates from OSRM; no live traffic feed."""
import asyncio,os,time
import httpx
from backend.geo import geographic,intersects_route
from engine import NODES
_cache=None
_lock=asyncio.Lock()
async def open_route(projection):
    global _cache
    base=os.environ.get('OSRM_BASE_URL','https://router.project-osrm.org').rstrip('/')
    start,end=geographic(NODES['community']),geographic(NODES['shelter'])
    points=';'.join(','.join(map(str,p)) for p in (start,end))
    async with _lock:
        if _cache and _cache[0]==base and time.monotonic()-_cache[1]<300:data=_cache[2]
        else:
            async with httpx.AsyncClient(timeout=20) as client:
                response=await client.get(base+'/route/v1/driving/'+points,params={'alternatives':'true','geometries':'geojson','overview':'full','radiuses':'1000;1000'},headers={'User-Agent':'WildfireWatch-hackathon-prototype'});response.raise_for_status();data=response.json()
            if data.get('code')!='Ok':raise ValueError('Open-road router returned no route candidates.')
            _cache=(base,time.monotonic(),data)
    excluded=[];accepted=[]
    for i,route in enumerate(data.get('routes',[])):
        if intersects_route(route['geometry']['coordinates'],projection):excluded.append({'edge':f'osrm-candidate-{i+1}','reason':'projected hazard'})
        else:accepted.append(route)
    result={'path':[],'minutes':None,'excluded':excluded,'status':'no_route','source':'OSRM / OpenStreetMap / no live traffic','candidate_count':len(data.get('routes',[])),'traffic_available':False}
    if accepted:
        best=min(accepted,key=lambda r:r['duration']);result.update(path=['community','shelter'],minutes=round(best['duration']/60,1),geometry=best['geometry']['coordinates'],status='candidate',distance_km=round(best['distance']/1000,2))
    return result
