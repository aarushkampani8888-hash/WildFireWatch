"""Observed environmental context, never a calibrated ignition probability."""
import asyncio
from datetime import datetime, timezone
import httpx
from fastapi import HTTPException

def summarize(elements):
    tags = [e.get('tags', {}) for e in elements]
    cover = sorted({t.get('natural') or t.get('landuse') for t in tags
        if t.get('natural') in {'wood','scrub','grassland','heath'} or
        t.get('landuse') in {'forest','grass','farmland','orchard','meadow'}})
    return {'available': True, 'buildings': sum('building' in t for t in tags),
        'developed': sum(t.get('landuse') in {'residential','commercial','industrial','retail'} for t in tags),
        'water': sum(t.get('natural') == 'water' or 'waterway' in t for t in tags),
        'cover': cover, 'note': 'Mapped features intersecting a 2 km observer buffer; incomplete OSM coverage and overlapping features are possible. Not an area or density estimate.'}

async def context(latitude, longitude):
    query = f'[out:json][timeout:12];(nwr(around:2000,{latitude},{longitude})[building];nwr(around:2000,{latitude},{longitude})[landuse];nwr(around:2000,{latitude},{longitude})[natural];nwr(around:2000,{latitude},{longitude})[waterway];);out tags;'
    async with httpx.AsyncClient(timeout=18, headers={"User-Agent":"WildfireWatch-research/0.2 (single-operator geographic context)"}) as client:
        results = await asyncio.gather(
            client.get('https://api.open-meteo.com/v1/forecast', params={'latitude':latitude,'longitude':longitude,'current':'temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation','timezone':'UTC'}),
            client.post('https://overpass.private.coffee/api/interpreter', data={'data':query}), return_exceptions=True)
    weather, geo = results
    if isinstance(weather, Exception) or weather.status_code != 200:
        raise HTTPException(503, 'Weather unavailable; no scenario values substituted')
    data = weather.json()
    geography = {'available':False, 'note':'Land-cover / development provider unavailable; do not infer absence of vegetation or people.'}
    if not isinstance(geo, Exception) and geo.status_code == 200:
        try:
            payload = geo.json()
            if 'remark' not in payload: geography = summarize(payload['elements'])
        except (ValueError, KeyError, TypeError): pass
    current = data['current']
    considerations = []
    if current.get('relative_humidity_2m', 100) < 30: considerations.append('Humidity below 30%: review dry conditions; this is not measured fuel moisture.')
    if current.get('wind_speed_10m', 0) >= 20: considerations.append('Wind at least 20 km/h: consider possible transport / spread if a fire is verified.')
    if geography.get('cover'): considerations.append('Mapped vegetation nearby: inspect potential fuel context.')
    if geography.get('buildings') or geography.get('developed'): considerations.append('Mapped development nearby: investigate potential community exposure after locating the hazard.')
    if not considerations: considerations.append('No listed screening flag; missing or mild context does not establish safety.')
    return {'latitude':latitude,'longitude':longitude,'current':current,'units':data['current_units'],
        'elevation_m':data.get('elevation'),'geography':geography,'considerations':considerations,
        'retrieved_at':datetime.now(timezone.utc).isoformat(), 'source':'Open-Meteo + OpenStreetMap',
        'fire_probability':None, 'note':'Current observer-area context only; no calibrated fire probability.'}
