"""Prepare an explicit, credential-free upload folder for a Docker Space."""
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'Dockerfile', '.dockerignore', 'package.json', 'package-lock.json',
    'index.html', 'vite.config.js', 'requirements.txt',
    'requirements-detector-inference.txt', 'engine.py', 'deploy/start.py',
    'models/smoke-detector.pt', 'models/detector-card.json',
    'docs/COMBINED_DETECTOR.md', 'docs/DEMO_GUIDE.md',
)

def prepare(parent=None):
    parent = Path(parent or ROOT / 'data')
    parent.mkdir(parents=True, exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix='hf-space-', dir=parent))
    for relative in FILES:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    for folder in ('frontend', 'backend', 'demo'):
        shutil.copytree(ROOT / folder, target / folder, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (target / 'README.md').write_text('''---
title: WildfireWatch Command Center
emoji: 🔥
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
suggested_hardware: cpu-basic
---

Wildfire evidence review prototype with locally trained smoke detection.
The Docker container serves React, FastAPI, and the trained detector together.
No OpenAI key is needed for local smoke inference. Set the Space variable
`PUBLIC_ORIGIN` to its exact HTTPS `.hf.space` origin before using controls.

Choose “Report smoke”, upload a photo with its observer location, and submit
it for real model analysis. The operator inbox shows image boxes, nearby
thermal observations, and a saved human review decision. Use the explicitly
staged smoke/cloud examples to follow `docs/DEMO_GUIDE.md`.
The detection threshold is 0.25. The 15-epoch model was
trained on Pyro-SDIS v2 and D-Fire. On 5,240 test images, smoke-presence
precision is 95.1%, recall 76.8%, and false-positive rate 4.9%. Recall on
unfamiliar Pyro-SDIS cameras is only 53.1%. Human review is required.

This is a single-operator prototype. Reports are stored in local SQLite;
thermal observations are in memory. Ephemeral hosting storage may reset.
Keep the Space private. It is not validated for emergency response.
See `docs/COMBINED_DETECTOR.md` and `models/detector-card.json` for limitations,
dataset provenance, and licenses. Pyro-SDIS is Apache-2.0, D-Fire's collection
is CC0-1.0, and Ultralytics is AGPL-3.0.
''')
    return target

if __name__ == '__main__':
    print(prepare())
