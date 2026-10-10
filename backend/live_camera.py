"""One bounded public research snapshot feed. No arbitrary URL fetching."""
import asyncio
import base64
import contextlib
import hashlib
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.local_vision import detect_local
from backend.reporting import Submission, process

router = APIRouter()
CAMERA = {
    'id': 'pi-e-mobo-c', 'name': 'Los Pinos East · San Diego County',
    'latitude': 32.73467, 'longitude': -116.57775, 'direction': 90,
    'url': 'https://cdn.hpwren.ucsd.edu/RT/pi-e-mobo-c.jpg',
    'page': 'https://www.hpwren.ucsd.edu/cameras/',
    'credit': 'HPWREN · UC San Diego · NSF / ALERTCalifornia',
    'terms': 'https://www.hpwren.ucsd.edu/cc.html',
}
CAMERAS = [CAMERA] + [dict(CAMERA, id=cid, name=name, latitude=lat, longitude=lon,
    url=f'https://cdn.hpwren.ucsd.edu/RT/{cid}.jpg') for cid,name,lat,lon in [
    ('bh-e-mobo-c','Boucher Hill · Palomar Mountain',33.33462,-116.91938),
    ('lp-e-mobo-c','Lyons Peak · east of Jamul',32.70153,-116.76457),
    ('mlo-e-mobo-c','Mount Laguna Observatory',32.83989,-116.42658),
]]
INTERVAL = 60
MAX_AGE = 300
COOLDOWN = 300


def stamp():
    return datetime.now(timezone.utc).isoformat()


async def fetch_frame(camera=None):
    camera = camera or CAMERA
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        async with client.stream('GET', camera['url'], headers={
            'User-Agent': 'WildfireWatch-research-prototype/0.3',
            'Cache-Control': 'no-cache',
        }) as response:
            response.raise_for_status()
            if not response.headers.get('content-type', '').startswith('image/jpeg'):
                raise ValueError('Camera returned a non-JPEG response')
            modified = parsedate_to_datetime(response.headers['last-modified'])
            if modified.tzinfo is None:raise ValueError('Camera timestamp has no timezone')
            age = time.time() - modified.timestamp()
            if age < -60 or age > MAX_AGE:
                raise ValueError('Provider image is stale or has an invalid timestamp; inference skipped')
            raw = bytearray()
            async for chunk in response.aiter_bytes():
                raw.extend(chunk)
                if len(raw) > 5_000_000:raise ValueError('Camera image exceeds 5 MB')
    return bytes(raw), modified.isoformat(), round(max(0, age), 1)


class CameraMonitor:
    def __init__(self):
        self.camera = CAMERA
        self.task = None
        self.lock = asyncio.Lock()
        self.last_attempt = None
        self.digest = None
        self.last_alert = None
        self.active_report_id = None
        self.latest = None
        self.history = []
        self.frames = []
        self.message = 'Not started. Fetch one frame or start one-minute monitoring.'

    def state(self):
        return {'camera': self.camera, 'cameras': CAMERAS, 'running': bool(self.task and not self.task.done()),
                'interval_seconds': INTERVAL, 'latest': self.latest,
                'history': self.history, 'sequence_count':len(self.frames), 'temporal':self.temporal(), 'message': self.message,
                'next_fetch_in_seconds': max(0, round(INTERVAL - (time.monotonic() - self.last_attempt)))
                if self.last_attempt is not None else 0}

    def temporal(self):
        from backend.investigation import temporal
        return temporal(self.history)

    async def broadcast(self):
        from backend.app import hub
        await hub.publish({'type': 'camera_update', 'camera': self.state()})

    async def sample(self):
        async with self.lock:
            now = time.monotonic()
            if self.last_attempt is not None and now - self.last_attempt < INTERVAL:
                return self.state()
            self.last_attempt = now
            try:
                raw, modified, age = await fetch_frame(self.camera)
                digest = hashlib.sha256(raw).hexdigest()
                if digest == self.digest:
                    self.message = 'Provider image unchanged. No repeated inference or duplicate alert.'
                    self.history.insert(0, {'checked_at': stamp(), 'outcome': 'unchanged', 'provider_updated_at': modified})
                else:
                    image = 'data:image/jpeg;base64,' + base64.b64encode(raw).decode()
                    finding = await asyncio.to_thread(detect_local, image)
                    latest = {'image': image, 'finding': finding, 'fetched_at': stamp(),
                              'provider_updated_at': modified, 'provider_age_seconds_at_fetch': age,
                              'sha256': digest, 'report_id': None}
                    # Preserve the provider image unchanged; inferred boxes are a separate overlay.
                    if finding['smoke_detected']:
                        if self.last_alert is None or now - self.last_alert >= COOLDOWN:
                            report = await process(Submission(image=image, latitude=self.camera['latitude'],
                                longitude=self.camera['longitude'], direction=self.camera['direction'],
                                observed_at=datetime.fromisoformat(modified),
                                notes='Public camera smoke candidate. Camera position is not fire location. '
                                      'Observation time uses provider object update time; inspect the embedded capture timestamp.'),
                                finding=finding, provenance={'kind': 'public_camera', **self.camera,
                                    'provider_updated_at': modified, 'fetched_at': latest['fetched_at']})
                            latest['report_id'] = report['id']
                            self.active_report_id = report['id']
                            self.last_alert = now
                            self.message = 'Smoke candidate added to the operator inbox. Human review required.'
                        else:
                            self.message = 'Smoke candidate detected; duplicate-alert cooldown active (5 minutes).'
                    else:
                        self.message = 'Frame analyzed. No smoke above threshold; this does not establish safety.'
                    self.frames = ([{k:v for k,v in latest.items() if k != 'sha256'}] + [f for f in self.frames if f['provider_updated_at'] != modified])[:6]
                    self.latest = latest
                    self.digest = digest
                    self.history.insert(0, {k:v for k,v in latest.items() if k not in ('image','sha256')})
            except asyncio.CancelledError:
                raise
            except Exception as error:
                # Never substitute a demonstration image or hide a provider failure.
                self.message = str(error) if isinstance(error, ValueError) else 'Camera fetch or local inference failed. No substitute frame used.'
                self.history.insert(0, {'checked_at': stamp(), 'outcome': 'error', 'message': self.message})
            self.history = self.history[:30]
            if self.latest and self.active_report_id:
                from backend.reporting import read, save
                r=read(self.active_report_id)
                if abs((datetime.fromisoformat(self.latest['provider_updated_at'])-datetime.fromisoformat(r['observed_at'])).total_seconds())<=600:
                    r['temporal']=self.temporal();save(r)
            await self.broadcast()
            return self.state()

    async def loop(self):
        try:
            while True:
                await self.sample()
                await asyncio.sleep(INTERVAL)
        finally:
            await self.broadcast()

    async def start(self):
        if not self.task or self.task.done():self.task = asyncio.create_task(self.loop())
        await self.broadcast()
        return self.state()

    async def stop(self):
        task, self.task = self.task, None
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):await task
        await self.broadcast()
        return self.state()

    async def select(self, camera_id):
        selected = next((c for c in CAMERAS if c['id'] == camera_id), None)
        if selected is None:raise HTTPException(422,'Unknown camera. Choose a supported research feed.')
        if selected['id'] == self.camera['id']:return self.state()
        await self.stop()
        async with self.lock:
            self.camera = selected
            self.last_attempt = self.digest = self.last_alert = self.latest = None
            self.history = []
            self.frames = []
            self.active_report_id = None
            self.message = 'Camera selected. Analyze a frame or start monitoring.'
        await self.broadcast()
        return self.state()


monitor = CameraMonitor()

class CameraSelection(BaseModel):
    camera_id: str

@router.post('/api/camera/select')
async def select_camera(data:CameraSelection):return await monitor.select(data.camera_id)


@router.get('/api/camera')
async def camera_state():return monitor.state()


@router.post('/api/camera/sample')
async def sample():return await monitor.sample()


@router.post('/api/camera/start')
async def start():return await monitor.start()


@router.post('/api/camera/stop')
async def stop():return await monitor.stop()

@router.get('/api/camera/sequence')
def camera_sequence():return {'camera_id':monitor.camera['id'],'frames':monitor.frames}
