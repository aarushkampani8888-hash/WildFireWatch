from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect
from backend.app import app
from backend import auth


def test_cloud_session_protects_api_and_websocket(monkeypatch,tmp_path):
    monkeypatch.setenv('OPERATOR_PASSWORD','test-password-long-enough-for-cloud')
    monkeypatch.setenv('REPORT_DB',str(tmp_path/'reports.sqlite'))
    auth.attempts.clear()
    with TestClient(app,base_url='https://testserver') as client:
        assert client.get('/api/auth/status').json()['required']
        assert client.get('/api/reports').status_code==401
        assert client.post('/api/camera/start').status_code==401
        assert client.get('/api/health').status_code==200
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect('/ws'):pass
        assert client.post('/api/auth/login',json={'password':'wrong'}).status_code==401
        response=client.post('/api/auth/login',json={'password':'test-password-long-enough-for-cloud'})
        assert response.status_code==200 and 'HttpOnly' in response.headers['set-cookie'] and 'Secure' in response.headers['set-cookie']
        assert client.get('/api/reports').status_code==200
        with client.websocket_connect('wss://testserver/ws') as ws:assert ws.receive_json()['type']=='snapshot'
        assert client.post('/api/auth/logout').status_code==200
        assert client.get('/api/reports').status_code==401
        client.cookies.set(auth.COOKIE,'9999999999.forged.badmac')
        assert client.get('/api/reports').status_code==401


def test_login_rate_limit(monkeypatch):
    monkeypatch.setenv('OPERATOR_PASSWORD','test-password')
    auth.attempts.clear()
    with TestClient(app) as client:
        for _ in range(10):assert client.post('/api/auth/login',json={'password':'wrong'}).status_code==401
        assert client.post('/api/auth/login',json={'password':'wrong'}).status_code==429
    auth.attempts.clear()
