import asyncio
import httpx
import pytest
from backend import geographic_context as geo

@pytest.mark.parametrize('maps_available', [True, False])
def test_context_preserves_score_uncertainty_and_partial_failure(monkeypatch, maps_available):
    real = httpx.AsyncClient
    def response(request):
        if request.url.host == 'api.open-meteo.com':
            assert request.url.params['latitude'] == '32.73467'
            return httpx.Response(200, json={'current':{'relative_humidity_2m':20,'wind_speed_10m':25},'current_units':{},'elevation':1200})
        assert b'around%3A2000' in request.content
        return httpx.Response(200 if maps_available else 503, json={'elements':[{'tags':{'building':'yes'}},{'tags':{'natural':'scrub'}}]})
    monkeypatch.setattr(geo.httpx, 'AsyncClient', lambda **kw:real(transport=httpx.MockTransport(response), **kw))
    result = asyncio.run(geo.context(32.73467, -116.57775))
    assert result['fire_probability'] is None
    assert result['geography']['available'] is maps_available
    assert result['elevation_m'] == 1200
    assert len(result['considerations']) >= 2
    if maps_available:
        assert result['geography']['buildings'] == 1
        assert result['geography']['cover'] == ['scrub']
    else:
        assert 'buildings' not in result['geography']
