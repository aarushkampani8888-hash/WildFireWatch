import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from backend import live_camera as camera


def test_current_frame_analysis_rate_limit_and_no_duplicate_inference():
    async def run():
        monitor = camera.CameraMonitor()
        modified = datetime.now(timezone.utc).isoformat()
        with patch.object(camera, 'fetch_frame', new=AsyncMock(return_value=(b'jpeg',modified,1))) as fetch, \
             patch.object(camera, 'detect_local', return_value={'smoke_detected':False,'confidence':.07,'boxes':[]}) as detector:
            await monitor.sample()
            assert monitor.latest['finding']['confidence']==.07
            await monitor.sample()
            assert fetch.await_count==1 and detector.call_count==1
            monitor.last_attempt -= 61
            await monitor.sample()
            assert fetch.await_count==2 and detector.call_count==1
            assert monitor.history[0]['outcome']=='unchanged'
    asyncio.run(run())


def test_positive_frames_create_real_report_with_cooldown(monkeypatch,tmp_path):
    monkeypatch.setenv('REPORT_DB',str(tmp_path/'reports.sqlite'))
    async def run():
        monitor=camera.CameraMonitor()
        modified=datetime.now(timezone.utc).isoformat()
        finding={'smoke_detected':True,'confidence':.7,'boxes':[]}
        with patch.object(camera,'fetch_frame',new=AsyncMock(side_effect=[(b'one',modified,1),(b'two',modified,1)])), \
             patch.object(camera,'detect_local',return_value=finding):
            await monitor.sample()
            from backend.reporting import read
            report=read(monitor.latest['report_id'])
            assert not report['demo'] and report['finding']==finding
            assert report['provenance']['kind']=='public_camera'
            assert report['latitude']==camera.CAMERA['latitude']
            assert [e['agent'] for e in report['events']]==['Intake','Sentinel','Correlator','Review']
            monitor.last_attempt-=61
            await monitor.sample()
            assert monitor.latest['report_id'] is None
            assert 'cooldown' in monitor.message
    asyncio.run(run())


@pytest.mark.parametrize('age',[600,-120])
def test_stale_future_and_invalid_provider_images_rejected(monkeypatch,age):
    real=httpx.AsyncClient
    def response(request):
        assert str(request.url)==camera.CAMERA['url']
        return httpx.Response(200,content=b'jpeg',headers={'content-type':'image/jpeg',
            'last-modified':(datetime.now(timezone.utc)-timedelta(seconds=age)).strftime('%a, %d %b %Y %H:%M:%S GMT')})
    monkeypatch.setattr(camera.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(response),**kw))
    with pytest.raises(ValueError,match='stale'):asyncio.run(camera.fetch_frame())


def test_fetch_failure_is_visible_without_model_substitution():
    async def run():
        monitor=camera.CameraMonitor()
        with patch.object(camera,'fetch_frame',new=AsyncMock(side_effect=ValueError('stale frame'))), \
             patch.object(camera,'detect_local') as detector:
            await monitor.sample()
            assert monitor.latest is None and monitor.history[0]['outcome']=='error'
            detector.assert_not_called()
        await monitor.start()
        assert monitor.state()['running']
        await monitor.stop()
        assert not monitor.state()['running']
    asyncio.run(run())


def test_camera_selection_resets_evidence_and_rejects_unknown_source():
    async def run():
        monitor=camera.CameraMonitor()
        monitor.latest={'image':'old-camera-image'}
        monitor.digest='old-digest';monitor.last_attempt=123;monitor.last_alert=124
        monitor.history=[{'outcome':'old-camera'}]
        result=await monitor.select('bh-e-mobo-c')
        assert result['camera']['latitude']==33.33462
        assert result['latest'] is None and result['history']==[]
        assert monitor.digest is None and monitor.last_attempt is None and monitor.last_alert is None
        assert not result['running'] and len(result['cameras'])==4
        from fastapi import HTTPException
        with pytest.raises(HTTPException):await monitor.select('https://example.com/private')
        assert monitor.camera['id']=='bh-e-mobo-c'
    asyncio.run(run())


def test_selected_feed_is_fetched_with_its_own_metadata(monkeypatch):
    real=httpx.AsyncClient
    selected=camera.CAMERAS[2]
    def response(request):
        assert str(request.url)==selected['url']
        return httpx.Response(200,content=b'jpeg',headers={'content-type':'image/jpeg',
            'last-modified':datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')})
    monkeypatch.setattr(camera.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(response),**kw))
    raw,_,_=asyncio.run(camera.fetch_frame(selected))
    assert raw==b'jpeg'

def test_temporal_metadata_persists_when_candidate_clears(monkeypatch,tmp_path):
    monkeypatch.setenv('REPORT_DB',str(tmp_path/'reports.sqlite'))
    async def run():
        monitor=camera.CameraMonitor()
        t=datetime.now(timezone.utc)
        positive={'smoke_detected':True,'confidence':.7,'boxes':[{'score':.7,'xyxy_normalized':[.1,.1,.2,.2]}]}
        clear={'smoke_detected':False,'confidence':.1,'boxes':[]}
        with patch.object(camera,'fetch_frame',new=AsyncMock(side_effect=[(b'one',t.isoformat(),1),(b'two',(t+timedelta(seconds=60)).isoformat(),1)])),patch.object(camera,'detect_local',side_effect=[positive,clear]):
            await monitor.sample();report_id=monitor.latest['report_id'];monitor.last_attempt-=61;await monitor.sample()
        from backend.reporting import read
        result=read(report_id)['temporal']
        assert len(result['frames'])==2 and result['against']
        assert len(monitor.frames)==2
        assert monitor.latest['report_id'] is None
    asyncio.run(run())
