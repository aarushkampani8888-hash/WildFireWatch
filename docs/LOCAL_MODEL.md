> This document describes the older image-classifier baseline. The current experimental local default is the combined Pyro-SDIS + D-Fire object detector; see [COMBINED_DETECTOR.md](COMBINED_DETECTOR.md).

# Local smoke model and open road routing

The Sentinel can now run a locally trained MobileNetV3 smoke classifier with no OpenAI key. Select **Local trained smoke model** in the dashboard served by FastAPI. Upload a camera image or configure `CAMERA_SOURCE` (ffmpeg required for videos). The public static site does not run Python inference; these controls require the local backend.

## Reproduce training

```sh
.venv/bin/pip install -r requirements-ml.txt
mkdir -p data
.venv/bin/gdown 1aYoCF64DkC9jC7T6H5UTaxwCXrosy4io -O data/smoke-public.zip
TORCH_HOME=data/torch .venv/bin/python ml/train.py --epochs 300
TORCH_HOME=data/torch .venv/bin/python ml/finetune.py
TORCH_HOME=data/torch .venv/bin/python ml/train_cached_head.py
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8787
```

Despite the filename, the publisher archive is a gzip tar. Training reads image bytes without extracting archive paths. It removes exact duplicate images and excludes Apple resource forks. Frames are grouped by event/date, with training, validation, and test groups disjoint. Original image hashes, paths, labels, and split assignments live in `data/manifest.json`. The first stage trains a normalized MLP head on a frozen ImageNet backbone; the second fine-tunes the final four backbone blocks. Model selection uses validation loss. The model checkpoint lives in `models/smoke-classifier.pt`; inference loads only that trusted local artifact using `weights_only=True`. No API key is used.

See `models/model-card.json` for actual counts and results. Early baselines performed poorly on the held-out events; the test split has been inspected during development and cannot serve as an untouched final benchmark. Fresh camera/event evaluation is required. The retained frozen-backbone classifier had lower validation loss than the fine-tuned candidate. On 233 development test images it detected 20 of 153 smoke images (13.1% recall), missed 133, and falsely flagged 35 of 80 clear images (43.8% false positive rate). This is inadequate for reliable smoke alerts. The model-selected threshold comes from validation; the dashboard's separate flag threshold may be stricter. Scores are uncalibrated smoke scores, not guaranteed probabilities. Smoke detection does not locate ignition, and the wind ellipse remains an illustrative spread model.

Source: [AI For Mankind public dataset](https://github.com/aiformankind/wildfire-smoke-dataset), with HPWREN camera imagery. Credit AI For Mankind and HPWREN. The repository explicitly licenses its related bounding-box annotation sets CC BY-NC-SA 4.0; the classification archive's exact license scope should be confirmed before commercial redistribution. Dataset and model binaries are excluded from Git and public deployment; the local checkpoint is available for this demo.

## Key-free roads

Select **OpenStreetMap roads / no live traffic** in the locally served dashboard. The backend calls OSRM, screens candidate geometries against the projected hazard, and returns the fastest accepted candidate. Synthetic closure overrides must be cleared first. The public demo service is cached for five minutes; this is a prototype service, not a production dependency. Set `OSRM_BASE_URL` to your own OSRM instance for independent hosting. OSM attribution is required for displayed road data.

OSRM computes routes with a road network and algorithms rather than a trained image model. It does not supply live congestion. Neither this classifier nor open routing replaces validated evacuation planning. The demo's community/shelter locations remain assumed scenario coordinates, and routing can fail or return no accepted candidates.

References: [OSRM route API](https://project-osrm.org/docs/v5.24.0/api/), [demo service policy](https://github.com/Project-OSRM/osrm-backend/wiki/Demo-server).
