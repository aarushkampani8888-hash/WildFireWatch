"""WGS84 GeoJSON for an explicitly synthetic sector near Paradise, CA."""
import math
from engine import NODES,EDGES,inside
ORIGIN=(-121.69,39.72)
def geographic(point):
    return [ORIGIN[0]+point[0]/(111.32*math.cos(math.radians(ORIGIN[1]))),ORIGIN[1]-point[1]/110.574]
def local(point):
    return [(point[0]-ORIGIN[0])*111.32*math.cos(math.radians(ORIGIN[1])),(ORIGIN[1]-point[1])*110.574]
def feature(geometry_type,coords,**props):
    return {'type':'Feature','geometry':{'type':geometry_type,'coordinates':coords},'properties':props}
def geojson(result):
    features=[]
    for p in result['projections']:
        features.append(feature('Polygon',[[geographic(pt) for pt in p['points'][:-1]]+[geographic(p['points'][0])]],kind='perimeter',minutes=p['minutes'],selected=p['minutes']==result['horizon'],model='illustrative ellipse'))
    excluded={e['edge']:e['reason'] for e in result['route']['excluded']}
    for a,b,_ in EDGES:
        features.append(feature('LineString',[geographic(NODES[a]),geographic(NODES[b])],kind='road',name=a+'-'+b,excluded=a+'-'+b in excluded,reason=excluded.get(a+'-'+b,'')))
    for name,point in NODES.items():features.append(feature('Point',geographic(point),kind='node',name=name))
    features.append(feature('Point',geographic((6,5)),kind='ignition',name='Assumed scenario ignition'))
    route=result['route']
    if route.get('geometry'): features.append(feature('LineString',route['geometry'],kind='route',source=route.get('source','Mapbox')))
    elif route['path']:features.append(feature('LineString',[geographic(NODES[n]) for n in route['path']],kind='route',source='synthetic graph'))
    return {'type':'FeatureCollection','features':features}
def intersects_route(coordinates,projection):
    # Approximate each segment at <=10 meter intervals. Not an operational guarantee.
    for start,end in zip(coordinates,coordinates[1:]):
        a,b=local(start),local(end); steps=max(1,math.ceil(math.dist(a,b)/.01))
        if steps>20000: return True
        if any(inside((a[0]+(b[0]-a[0])*i/steps,a[1]+(b[1]-a[1])*i/steps),projection) for i in range(steps+1)):return True
    return False
