"""Start a single-worker hosted dashboard using an explicit deployment origin."""
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
import uvicorn

def configured_origins():
    origins = [v.strip() for v in os.environ.get('ALLOWED_ORIGINS', '').split(',') if v.strip()]
    for name in ('PUBLIC_ORIGIN', 'RENDER_EXTERNAL_URL'):
        value = os.environ.get(name, '').strip()
        if not value:
            continue
        parsed = urlsplit(value)
        if parsed.scheme not in ('https', 'http') or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError(f'{name} must be an HTTP(S) origin')
        origins.append(f'{parsed.scheme}://{parsed.netloc}')
    return list(dict.fromkeys(origins))

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    checkpoint = Path('models/smoke-detector.pt')
    if not checkpoint.is_file():
        raise RuntimeError('Trained detector checkpoint is missing from deployment')
    origins = configured_origins()
    if origins:
        os.environ['ALLOWED_ORIGINS'] = ','.join(origins)
    uvicorn.run('backend.app:app', host=os.environ.get('HOST', '0.0.0.0'), port=int(os.environ.get('PORT', '7860')), workers=1, proxy_headers=True)
