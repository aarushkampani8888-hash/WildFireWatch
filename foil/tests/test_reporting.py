import base64
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend import reporting

@pytest.fixture
def client(monkeypatch,tmp_path):
    monkeypatch.setenv('REPORT_DB',str(tmp_path/'reports.sqlite'))
    monkeypatch.delenv('FIRMS_MAP_KEY',raising=False)
    reporting.HOTSPOTS=[]
    with TestClient(app) as client:yield client

def payload(**changes):
    return {'image':'data:image/png;base64,AAAA','latitude':39.805,'longitude':-121.46,'observed_at':'2021-07-22T18:35:00Z','demo':False,**changes}

def test_report_pipeline_persists_and_reviews(client):
    finding={'smoke_detected':True,'confidence':.62,'boxes':[],'source':'test detector','reason':'Possible smoke'}
    with patch('backend.reporting.detect_local',return_value=finding):
        with client.websocket_connect('/ws',headers={'origin':'http://127.0.0.1:8000'}) as ws:
            ws.receive_json()
            r=client.post('/api/reports',json=payload(demo=True));assert r.status_code==200
            report=r.json();events=[ws.receive_json() for _ in range(5)]
    assert [e['stage'] for e in events[:-1]]==['Intake','Sentinel','Correlator','Review']
    assert events[-1]['type']=='report_ready'
    assert report['matches'][0]['demo'] and report['matches'][0]['source']=='Staged thermal anomaly'
    assert report['location_role']=='observer, not ignition'
    assert 'image' not in client.get('/api/reports').json()[0]
    assert client.get('/api/reports/'+report['id']).json()['image']==report['image']
    result=client.post('/api/reports/'+report['id']+'/review',json={'decision':'needs_information','notes':'Check viewing direction'})
    assert result.json()['status']=='needs_information'
    assert client.get('/api/reports/'+report['id']).json()['review']['notes']=='Check viewing direction'

def test_real_report_never_matches_staged_hotspot(client):
    with patch('backend.reporting.detect_local',return_value={'smoke_detected':False,'confidence':0,'boxes':[]}):
        r=client.post('/api/reports',json=payload()).json()
    assert r['matches']==[] and r['status']=='pending'

def test_human_fire_confirmation_works_without_a_pin_and_validates_optional_area(client,monkeypatch):
    import httpx
    from backend import landscape_risk
    with patch('backend.reporting.detect_local',return_value={'smoke_detected':True,'confidence':.8,'boxes':[]}):
        report=client.post('/api/reports',json=payload()).json()
    confirmed_without_pin=client.post(f"/api/reports/{report['id']}/review",json={
        'decision':'confirmed_fire','decision_latitude':39.81,'decision_longitude':-121.45})
    assert confirmed_without_pin.status_code==200
    assert confirmed_without_pin.json()['status']=='confirmed_fire'
    assert confirmed_without_pin.json()['review']['incident_latitude'] is None
    assert confirmed_without_pin.json()['review']['decision_latitude']==39.81
    assert confirmed_without_pin.json()['review']['decision_longitude']==-121.45
    assert client.post(f"/api/reports/{report['id']}/review",json={
        'decision':'escalated','decision_latitude':39.81}).status_code==422

    with patch('backend.reporting.detect_local',return_value={'smoke_detected':True,'confidence':.8,'boxes':[]}):
        report=client.post('/api/reports',json=payload()).json()
    partial=client.post(f"/api/reports/{report['id']}/review",json={
        'decision':'confirmed_fire','incident_latitude':39.805,
    })
    assert partial.status_code==422

    real=httpx.AsyncClient
    def boundary(request):
        assert request.url.host=='tigerweb.geo.census.gov'
        assert request.url.params['geometry']=='-121.46,39.805'
        return httpx.Response(200,json={'features':[{'attributes':{'STATE':'06'}}]})
    monkeypatch.setattr(landscape_risk.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(boundary),**kw))
    confirmed=client.post(f"/api/reports/{report['id']}/review",json={
        'decision':'confirmed_fire','incident_latitude':39.805,'incident_longitude':-121.46,
    })
    assert confirmed.status_code==200
    assert confirmed.json()['status']=='confirmed_fire'
    assert confirmed.json()['review']['incident_latitude']==39.805

def test_thermal_anomaly_can_be_added_once_to_inbox(client):
    data={'observation_id':'firms-test-1','latitude':39.82,'longitude':-121.44,
        'observed_at':'2021-07-22T18:30:00Z','source':'NASA FIRMS / VIIRS NOAA-20',
        'satellite':'NOAA-20','confidence':'nominal'}
    first=client.post('/api/satellite/review',json=data)
    second=client.post('/api/satellite/review',json=data)
    assert first.status_code==second.status_code==200
    assert first.json()['id']==second.json()['id']
    assert first.json()['kind']=='thermal_observation'
    assert first.json()['status']=='pending'
    inbox=client.get('/api/reports').json()
    assert sum(row['id']==first.json()['id'] for row in inbox)==1

def test_plotted_map_point_creates_actionable_inbox_case(client,monkeypatch):
    from backend import landscape_risk
    monkeypatch.setattr(landscape_risk,'verify_california',AsyncMock())
    monkeypatch.setattr(reporting,'_start_geographic_assessment',lambda *_args:None)
    created=client.post('/api/map-point-reports',json={
        'latitude':39.82,'longitude':-121.44,
        'notes':'Created from the map popup; no image evidence.'})
    assert created.status_code==200,created.text
    report=created.json()
    assert report['kind']=='map_point_observation'
    assert report['status']=='pending'
    assert report['finding']['confidence'] is None
    assert 'image' not in report
    confirmed=client.post(f"/api/reports/{report['id']}/review",json={
        'decision':'confirmed_fire','incident_latitude':39.82,'incident_longitude':-121.44})
    assert confirmed.status_code==200,confirmed.text
    assert confirmed.json()['status']=='confirmed_fire'
    assert confirmed.json()['review']['incident_longitude']==-121.44

def test_plot_and_confirm_is_one_atomic_inbox_action_without_area_pin(client,monkeypatch):
    from backend import landscape_risk
    monkeypatch.setattr(landscape_risk,'verify_california',AsyncMock())
    monkeypatch.setattr(reporting,'_start_geographic_assessment',lambda *_args:None)
    created=client.post('/api/map-point-reports',json={
        'latitude':39.82,'longitude':-121.44,
        'notes':'Created from a plotted point.',
        'action':'confirmed_fire',
        'decision_notes':'Operator confirmed at the plotted point; boundary can be added later.'})
    assert created.status_code==200,created.text
    report=created.json()
    assert report['status']=='confirmed_fire'
    assert report['review']['decision']=='confirmed_fire'
    assert report['review']['incident_latitude'] is None
    assert report['review']['incident_longitude'] is None
    assert report['review']['decision_latitude']==39.82
    assert report['review']['decision_longitude']==-121.44
    inbox=client.get('/api/reports').json()
    assert any(row['id']==report['id'] and row['status']=='confirmed_fire' for row in inbox)

def test_plot_and_escalate_is_one_atomic_inbox_action(client,monkeypatch):
    from backend import landscape_risk
    monkeypatch.setattr(landscape_risk,'verify_california',AsyncMock())
    monkeypatch.setattr(reporting,'_start_geographic_assessment',lambda *_args:None)
    created=client.post('/api/map-point-reports',json={
        'latitude':39.82,'longitude':-121.44,'action':'escalated',
        'decision_notes':'Review this location.'})
    assert created.status_code==200,created.text
    assert created.json()['status']=='escalated'
    assert created.json()['review']['decision']=='escalated'

def test_firms_csv_filter_and_time_match(client):
    csv='latitude,longitude,acq_date,acq_time,confidence\n39.82,-121.44,2021-07-22,1830,n\n20,-100,2021-07-22,0000,n\n39.82,-121.44,2020-07-22,1830,n\n'
    assert len(client.post('/api/satellite/import',json={'csv':csv}).json()['observations'])==2
    with patch('backend.reporting.detect_local',return_value={'smoke_detected':True,'confidence':.7,'boxes':[]}):
        result=client.post('/api/reports',json=payload()).json()
    assert len(result['matches'])==1 and not result['matches'][0]['demo']
    assert result['matches'][0]['time_difference_hours']==pytest.approx(5/60,abs=.005)
    assert client.post('/api/satellite/import',json={'csv':'x,y\n1,2'}).status_code==422

def test_validation_and_no_provider_substitution(client):
    for p in [payload(latitude=10),payload(observed_at='2021-07-22T18:35:00'),payload(observed_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat())]:
        assert client.post('/api/reports',json=p).status_code==422
    assert client.post('/api/reports',json=payload()).status_code==422
    assert client.get('/api/satellite?live=true').status_code==503
    assert client.get('/api/satellite').json()['observations']==[]

def test_location_weather_uses_report_coordinates(client,monkeypatch):
    import httpx
    real=httpx.AsyncClient
    def response(request):
        assert request.url.params['latitude']=='34.1' and request.url.params['longitude']=='-118.2'
        return httpx.Response(200,json={'current':{'wind_speed_10m':10},'current_units':{'wind_speed_10m':'km/h'}})
    monkeypatch.setattr(reporting.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(response),**kw))
    r=client.get('/api/location-weather?latitude=34.1&longitude=-118.2')
    assert r.status_code==200 and r.json()['latitude']==34.1

def test_geographic_assessment_enriches_report_without_changing_detector(client,monkeypatch):
    from backend import landscape_risk
    from datetime import datetime, timezone
    assessment={'assessed_at':datetime.now(timezone.utc).isoformat(),
        'landscape':{'available':True,'cover':['forest','scrub']},
        'terrain':{'slope_degrees':18.2,'elevation_m':450},
        'weather':{'relative_humidity_2m':19,'wind_speed_10m':24},'alerts':[],
        'screening':{'index':72,'label':'Elevated screening conditions','coverage_percent':100,
            'factors':[{'name':'Mapped vegetation','value':'forest, scrub','available':True}]},
        'limitations':['Heuristic only; not a fire probability.']}
    monkeypatch.setattr(landscape_risk,'assess',AsyncMock(return_value=assessment))
    with patch('backend.reporting.detect_local',return_value={'smoke_detected':True,'confidence':.62,'boxes':[]}):
        report=client.post('/api/reports',json=payload()).json()
    assert report['geographic_assessment']['status']=='pending'
    report_id=report['id']
    asyncio.run(reporting._assess_report_geography(report_id,report['latitude'],report['longitude']))
    enriched=client.get(f'/api/reports/{report_id}').json()
    assert enriched['geographic_assessment']['status']=='available'
    assert enriched['geographic_assessment']['data']['landscape']['cover']==['forest','scrub']
    assert enriched['finding']['confidence']==.62

def test_geographic_assessment_failure_is_recorded_without_substitution(client,monkeypatch):
    from backend import landscape_risk
    async def unavailable(*_args):
        raise RuntimeError('provider unavailable')
    monkeypatch.setattr(landscape_risk,'assess',unavailable)
    report={'id':'geo-failure','latitude':39.805,'longitude':-121.46,'geographic_assessment':{'status':'pending'}}
    reporting.save(report)
    asyncio.run(reporting._assess_report_geography(report['id'],report['latitude'],report['longitude']))
    result=reporting.read(report['id'])['geographic_assessment']
    assert result['status']=='unavailable'
    assert 'no values were substituted' in result['message']

@pytest.mark.skipif(not (reporting.ROOT/'data/combined-smoke/manifest.json').exists(),reason='Local dataset unavailable')
def test_demo_runs_actual_detector_smoke_and_cloud(client):
    for kind,expected in [('smoke',True),('cloud',False)]:
        d=client.get('/api/demo/'+kind).json();d.pop('source')
        result=client.post('/api/reports',json=d)
        assert result.status_code==200,result.text
        r=result.json();assert r['finding']['source'].startswith('local YOLO11n')
        assert r['finding']['smoke_detected'] is expected
        assert r['demo'] and len(r['matches'])==1

def test_reference_upload_never_correlates_test_coordinates(client):
    finding={'smoke_detected':True,'confidence':.7,'boxes':[]}
    reporting.HOTSPOTS=[dict(reporting.DEMO_HOTSPOTS[0],demo=False)]
    with patch('backend.reporting.detect_local',return_value=finding):
        r=client.post('/api/reports',json=payload(reference=True)).json()
    assert r['reference'] and not r['demo'] and r['matches']==[]
    assert 'reference test' in r['location_role']
    packet=client.get('/api/reports/'+r['id']+'/investigation').json()
    assert packet['reference'] and packet['thermal_observations']==[]
    assert packet['nearby_cameras']==[]
