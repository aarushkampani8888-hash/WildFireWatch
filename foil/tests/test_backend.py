import asyncio,os
from unittest.mock import patch,AsyncMock
import pytest
from fastapi.testclient import TestClient
from backend.app import app,hub
from backend.geo import geographic,local,intersects_route
from engine import projection
@pytest.fixture
def client():
    hub.latest=None;hub.events=[];hub.sensors=None;hub.monitor=None
    with TestClient(app) as c:yield c

def test_pipeline_geojson(client):
    r=client.post('/api/run',json={});assert r.status_code==200
    d=r.json();assert d['geojson']['type']=='FeatureCollection';assert d['sentinel']['flagged'];assert d['route']['path']
    polygon=next(f for f in d['geojson']['features'] if f['geometry']['type']=='Polygon')
    ring=polygon['geometry']['coordinates'][0];assert ring[0]==pytest.approx(ring[-1]);assert -180<ring[0][0]<180 and -90<ring[0][1]<90

def test_negative_and_threshold_clear_old_hazard(client):
    client.post('/api/run',json={})
    for data in [{'smoke':False},{'threshold':.95}]:
        d=client.post('/api/run',json=data).json();assert not d['sentinel']['flagged'];assert not d['projections'];assert d['route']['status']=='no_detection';assert not any(f['properties']['kind'] in ('perimeter','route') for f in d['geojson']['features'])

def test_websocket_stages_and_incident(client):
    with client.websocket_connect('/ws',headers={'origin':'http://127.0.0.1:8787'}) as ws:
        assert ws.receive_json()['type']=='snapshot'
        assert client.post('/api/run',json={}).status_code==200
        updates=[ws.receive_json() for _ in range(5)]
        assert [e['type'] for e in updates]==['pipeline_started','agent_event','agent_event','agent_event','incident']
        assert [e['stage'] for e in updates[1:4]]==['sentinel','propagator','dispatcher']
        assert updates[-1]['incident']['geojson']['features']

def test_operator_review_conflict(client):
    old=client.post('/api/run',json={}).json();latest=client.post('/api/run',json={}).json()
    assert client.post('/api/review',json={'incident_id':old['id'],'decision':'acknowledged'}).status_code==409
    assert client.post('/api/review',json={'incident_id':latest['id'],'decision':'rejected'}).json()['review']=='rejected'

def test_missing_vision_fails_without_simulation(client):
    with patch.dict(os.environ,{},clear=True):
        response=client.post('/api/run',json={'mode':'vision','image':'data:image/png;base64,AAAA'})
    assert response.status_code==502;assert hub.latest is None

def test_validation(client):
    for data in [{'wind':-1},{'horizon':10},{'threshold':2},{'closures':['invented-road']},{'mode':'pretend'}]:assert client.post('/api/run',json=data).status_code==422

def test_sensor_auth(client):
    d={'wind':30,'humidity':25,'direction':90}
    with patch.dict(os.environ,{'SENSOR_WEBHOOK_TOKEN':'test-only'}):
        assert client.post('/api/sensors',json=d).status_code==401
        assert client.post('/api/sensors',json=d,headers={'authorization':'Bearer test-only'}).status_code==200
        assert client.post('/api/run',json={}).json()['weather']['source']=='authenticated sensor webhook'

def test_monitor_stop(client):
    assert client.post('/api/monitor',json={'enabled':True,'interval':5}).status_code==200
    assert client.get('/api/status').json()['monitoring']
    assert client.post('/api/monitor',json={'enabled':False}).json()['enabled'] is False
    assert not client.get('/api/status').json()['monitoring']

def test_mapbox_closure_rejected(client):
    r=client.post('/api/run',json={'routing':'mapbox','closures':['junction-south']})
    assert r.status_code==502;assert 'Synthetic road overrides' in r.json()['detail']

def test_geo_roundtrip_and_intersection():
    assert local(geographic((6,5)))==pytest.approx((6,5))
    p=projection(24,22,270,60)
    assert intersects_route([geographic((4,5)),geographic((10,5))],p)
    assert not intersects_route([geographic((1,9)),geographic((10,9))],p)

def test_browser_origin_and_body_limit(client):
    assert client.post('/api/run',json={},headers={'origin':'https://unrelated.example'}).status_code==403
    assert client.post('/api/run',content='{}',headers={'content-length':'9000000'}).status_code==413

def test_real_vision_negative_skips_routing(client):
    finding={'smoke_detected':False,'confidence':.12,'reason':'No visible smoke.','source':'test vision provider'}
    with patch('backend.pipeline.detect',new=AsyncMock(return_value=finding)):
        r=client.post('/api/run',json={'mode':'vision','image':'data:image/png;base64,AAAA'})
    assert r.status_code==200;d=r.json();assert not d['projections'];assert d['route']['status']=='no_detection';assert d['sentinel']['source']=='test vision provider'

def test_mapbox_candidates_screened(monkeypatch):
    import httpx
    from backend.integrations import mapbox_route
    from backend import integrations
    real_client=httpx.AsyncClient
    crossing=[geographic((4,5)),geographic((10,5))]
    outside=[geographic((1,9)),geographic((10,9))]
    def response(request):
        assert 'driving-traffic' in str(request.url)
        return httpx.Response(200,json={'code':'Ok','routes':[{'duration':100,'distance':1000,'geometry':{'coordinates':crossing}},{'duration':900,'distance':9000,'geometry':{'coordinates':outside}}]})
    monkeypatch.setenv('MAPBOX_ACCESS_TOKEN','test-token')
    monkeypatch.setattr(integrations.httpx,'AsyncClient',lambda **kw:real_client(transport=httpx.MockTransport(response),**kw))
    route=asyncio.run(mapbox_route(projection(24,22,270,60)))
    assert route['minutes']==15;assert len(route['excluded'])==1;assert route['geometry']==outside
