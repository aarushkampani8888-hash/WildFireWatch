# Smoke detector trained on Pyro-SDIS v2 and D-Fire

The combined dataset has 33,717 usable unique images: 25,065 training, 3,412 validation, and 5,240 test. Source counts are 12,378 Pyro-SDIS v2 images and 21,527 D-Fire images. Preparation excluded 26 images with invalid D-Fire boxes, removed 159 exact duplicate entries, and excluded three conflicting-label duplicate families.

Pyro-SDIS: https://huggingface.co/datasets/pyronear/pyro-sdis/tree/v2.0 (Apache-2.0). D-Fire: https://github.com/gaia-solutions-on-demand/DFireDataset (collection CC0-1.0), using its publisher-linked Kaggle mirror https://www.kaggle.com/datasets/sayedgamal99/smoke-fire-detection-yolo. Credit Pyronear and GAIA and retain the datasets' citations. Ultralytics code/model use is under AGPL-3.0; review its obligations before distributing or hosting a closed-source derivative.

Both datasets use smoke class 0. D-Fire fire class 1 is removed from annotations for this smoke-only detector; fire-only frames remain negative examples. Images preserve aspect ratio and are resized to at most 1280 pixels on the longest side. Training uses YOLO11n at 512 pixels, COCO-pretrained weights, first ten layers frozen, AdamW, seed 42, batch 16, up to 15 epochs with validation-based early stopping. No paid service or API key is required. This is transfer learning, not training a vision backbone from random initialization.

Pyro-SDIS splits are assigned by camera identifier, so the same camera cannot appear across training/validation/test. D-Fire retains its publisher mirror's existing split because camera/event metadata is unavailable. Exact duplicate image hashes are removed across both sources with test priority; conflicting annotations cause the duplicate family to be excluded. Near-duplicate leakage within D-Fire has not been fully audited, so results are a development benchmark rather than proof of field performance.

## Reproduction

Install `requirements-ml.txt`. Download Pyro-SDIS using `huggingface_hub.snapshot_download('pyronear/pyro-sdis', repo_type='dataset', revision='v2.0', local_dir='data/pyro', allow_patterns=['*.parquet','README.md','data.yaml'])`. Download D-Fire's Kaggle archive to `data/dfire/download.zip`.

```sh
.venv/bin/python ml/prepare_detector.py
YOLO_CONFIG_DIR=data/ultralytics MPLCONFIGDIR=data/matplotlib .venv/bin/python ml/train_detector.py --epochs 15 --imgsz 512 --batch 16
```

On macOS, GPU training needs access to MPS. CPU fallback is supported but slower. If the Python SSL certificate configuration is missing, set `SSL_CERT_FILE` to the installed certifi CA bundle; do not disable TLS verification. To resume a saved training epoch, add `--resume` to the same training command. Keep the prepared dataset and run directory unchanged when resuming.

Training checkpoints are in `data/detector-runs/combined-smoke/weights/`. After training and test evaluation, the selected candidate is copied to `models/smoke-detector-candidate.pt`, with metrics in `models/detector-card.json`. Evaluation includes box-level precision/recall/mAP plus image-level smoke presence at a fixed confidence threshold of 0.25, separately for each dataset. Test data is not used to choose the training checkpoint.

The runtime detector loads `models/smoke-detector.pt` only after an explicit local promotion, or the trusted checkpoint named by `LOCAL_SMOKE_DETECTOR`. Otherwise it retains the old classifier. Local detection returns normalized smoke boxes and an uncalibrated maximum confidence score. The dashboard's flag threshold is a separate control; 0.25 matches the fixed-confidence development evaluation, whereas its default 0.8 is stricter. The model still cannot geolocate ignition or validate fire-spread predictions or evacuation corridors.

For inference only, install `requirements-detector-inference.txt`; the dataset loaders are unnecessary. The static hosted demo cannot run the Python model. Use the local FastAPI dashboard for inference. Dataset files, caches, and binary checkpoints are excluded from Git and static publication.

Dataset citations: Pyronear Team, *Pyro-SDIS Dataset*, v2.0 (2026); Pedro Vinícius Almeida Borges de Venâncio, Adriano Chaves Lisboa, and Adriano Vilela Barbosa, *An automatic fire-detection system based on deep convolutional neural networks for low-power, resource-constrained devices*, Neural Computing and Applications (2022), https://doi.org/10.1007/s00521-022-07467-z.

## Completed run and held-out results

The run completed all 15 epochs in 7,809 seconds (about 2 hours 10 minutes) on an Apple M3 Pro. The best validation-selected checkpoint is activated as the **experimental local default** at `models/smoke-detector.pt`; the previous classifier and candidate checkpoint are retained. Test images were not used to select the checkpoint. The image loader was changed to bounded batches of 64 after the original full-list evaluation process exited. All 5,240 test images are accounted for.

Image-level smoke presence at confidence **0.25**:

| Test source | Images | Precision | Recall | False-positive rate |
| --- | ---: | ---: | ---: | ---: |
| Pyro-SDIS camera-disjoint | 946 | 96.0% | 53.1% | 14.4% |
| D-Fire publisher split | 4,294 | 94.8% | 86.2% | 4.4% |
| Combined | 5,240 | 95.1% | 76.8% | 4.9% |

Combined confusion counts: 2,219 true positives, 2,235 true negatives, 115 false positives, and 671 false negatives. A false-positive rate is the fraction of labeled smoke-negative images flagged, not the fraction of alerts that are wrong. Smoke-negative images can still contain fire.

Box-level test precision is 72.9%, recall 60.8%, mAP@0.5 is 66.7%, and mAP@0.5:0.95 is 38.0%. These metrics use localization overlap and differ from image-level smoke presence. Confidence scores are uncalibrated. Poor recall on unfamiliar Pyro-SDIS cameras and unaudited D-Fire near-duplicates limit real-world claims. This detector has not been validated for emergency response.

Install inference dependencies and run the backend:

```sh
.venv/bin/pip install -r requirements-detector-inference.txt
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Use the local dashboard's **Local smoke model / experimental** evidence source, upload a camera frame, and set the flag threshold to 0.25 to match this evaluation. The default dashboard threshold of 0.8 has not been measured in this report. No OpenAI key is required for local smoke inference. Live road routing remains a separate GIS operation.

To repeat evaluation without retraining:

```sh
YOLO_CONFIG_DIR=data/ultralytics MPLCONFIGDIR=data/matplotlib .venv/bin/python ml/train_detector.py --evaluate-only --imgsz 512 --batch 16
```

The model card records the checkpoint SHA-256 and dataset revision. `models/detector-preview.png` shows predetermined positive and negative test examples from both sources, including misses when they occur.
