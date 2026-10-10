"""Inference for the trusted local smoke detector trained on Pyro-SDIS and D-Fire."""
import base64,io,os,threading
from functools import lru_cache
from pathlib import Path
INFERENCE_LOCK=threading.Lock()
DEFAULT=Path(__file__).resolve().parents[1]/'models/smoke-detector.pt'
def detector_path():return os.environ.get('LOCAL_SMOKE_DETECTOR') or str(DEFAULT)
def available():return Path(detector_path()).is_file()
@lru_cache(maxsize=1)
def load(path):
    os.environ.setdefault("YOLO_CONFIG_DIR",str(DEFAULT.parents[1]/"data/ultralytics"))
    import torch
    torch.set_num_threads(4)
    os.environ.setdefault("YOLO_AUTOINSTALL","false")
    from ultralytics import YOLO
    return YOLO(path)
def detect(image):
    from PIL import Image,UnidentifiedImageError
    if not isinstance(image,str) or not image.startswith(('data:image/jpeg;base64,','data:image/png;base64,','data:image/webp;base64,')):raise ValueError('Unsupported image format.')
    raw=base64.b64decode(image.split(',',1)[1],validate=True)
    if len(raw)>5_000_000:raise ValueError('Image exceeds 5 MB.')
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.width*im.height>25_000_000:raise ValueError('Image exceeds 25 megapixels.')
            rgb=im.convert('RGB')
    except (UnidentifiedImageError,OSError,ImportError):raise ValueError('Invalid image.') from None
    # CPU inference keeps the local API available without GPU privileges.
    with INFERENCE_LOCK:
        result=load(detector_path()).predict(rgb,imgsz=512,conf=.05,device='cpu',verbose=False)[0]
    boxes=[]
    for box in result.boxes:
        if int(box.cls[0])!=0:continue
        boxes.append({'xyxy_normalized':[round(float(v),6) for v in box.xyxyn[0]],'score':round(float(box.conf[0]),6)})
    score=max((b['score'] for b in boxes),default=0.)
    return {'smoke_detected':score>=.25,'confidence':score,'reason':f'Local smoke detector found {len([b for b in boxes if b["score"]>=.25])} candidate regions; uncalibrated score {score:.3f}, human review required.','source':'local YOLO11n / Pyro-SDIS + D-Fire / experimental','model_threshold':.25,'boxes':boxes}
