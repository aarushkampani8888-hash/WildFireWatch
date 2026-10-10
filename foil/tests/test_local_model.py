import asyncio,base64,json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend.local_vision import available,detect_local
from backend import open_routes
ROOT=Path(__file__).resolve().parents[1]
@pytest.mark.skipif(not available(),reason='Trained model not installed')
def test_local_actual_model_and_pipeline():
    manifest=json.loads((ROOT/'data/manifest.json').read_text()) if (ROOT/'data/manifest.json').exists() else []
    if not manifest:pytest.skip('Dataset unavailable')
    image='data:image/jpeg;base64,'+base64.b64encode((ROOT/manifest[0]['path']).read_bytes()).decode()
    finding=detect_local(image);assert 0<=finding['confidence']<=1;assert type(finding['smoke_detected']) is bool
    with TestClient(app) as client:
        assert client.get('/api/status').json()['local_vision_available']
        r=client.post('/api/run',json={'mode':'local','image':image});assert r.status_code==200;assert r.json()['sentinel']['source'].startswith('local')
def test_model_rejects_invalid_image():
    with pytest.raises(ValueError):detect_local('data:image/png;base64,AAAA')
def test_open_route_blocks_hazard(monkeypatch):
    from unittest.mock import AsyncMock,patch
    from backend.geo import geographic
    from engine import projection
    coords=[geographic((6,6)),geographic((6.1,6.1))]
    data={'routes':[{'geometry':{'coordinates':coords},'duration':300,'distance':900}]}
    monkeypatch.setattr(open_routes,'_cache',('https://router.project-osrm.org',__import__('time').monotonic(),data))
    with patch('backend.open_routes.intersects_route',return_value=True):
        route=asyncio.run(open_routes.open_route(projection(24,22,270,60)))
    assert route['status']=='no_route';assert not route['path'];assert len(route['excluded'])==1;assert not route['traffic_available']


def test_event_manifest_no_exact_or_group_leakage():
    path=ROOT/'data/manifest.json'
    if not path.exists():pytest.skip('Dataset unavailable')
    records=json.loads(path.read_text());assert len({r['sha256'] for r in records})==len(records)
    groups={s:{r['group'] for r in records if r['split']==s} for s in ('train','validation','test')}
    assert groups['train'].isdisjoint(groups['validation']);assert groups['test'].isdisjoint(groups['train']|groups['validation'])
