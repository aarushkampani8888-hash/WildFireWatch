"""Local inference. Load only a trusted, locally trained checkpoint."""
import base64,io,os
from functools import lru_cache
from pathlib import Path
DEFAULT=Path(__file__).resolve().parents[1]/'models/smoke-classifier.pt'
def available():
    from backend.local_detector import available as detector_available
    if os.environ.get('LOCAL_SMOKE_DETECTOR'):return detector_available()
    return detector_available() or Path((os.environ.get('LOCAL_SMOKE_MODEL') or str(DEFAULT))).is_file()
@lru_cache(maxsize=1)
def load_model(path):
    import torch
    from torchvision.models import mobilenet_v3_small,MobileNet_V3_Small_Weights
    torch.set_num_threads(4)
    checkpoint=torch.load(path,map_location='cpu',weights_only=True)
    model=mobilenet_v3_small(weights=None);model.classifier=torch.nn.Sequential(torch.nn.LayerNorm(576),torch.nn.Linear(576,128),torch.nn.ReLU(),torch.nn.Dropout(.2),torch.nn.Linear(128,1));model.load_state_dict(checkpoint['state_dict']);model.eval()
    return model,MobileNet_V3_Small_Weights.DEFAULT.transforms(),checkpoint['threshold']
def detect_local(image):
    from backend.local_detector import available as detector_available,detect
    if os.environ.get('LOCAL_SMOKE_DETECTOR') and not detector_available():raise ValueError('Configured local detector checkpoint is unavailable.')
    if detector_available():return detect(image)
    import torch
    from PIL import Image,UnidentifiedImageError
    if not isinstance(image,str) or not image.startswith(('data:image/jpeg;base64,','data:image/png;base64,','data:image/webp;base64,')):raise ValueError('Unsupported image format.')
    try:
        raw=base64.b64decode(image.split(',',1)[1],validate=True)
        if len(raw)>5_000_000:raise ValueError('Image exceeds 5 MB.')
        with Image.open(io.BytesIO(raw)) as im:
            if im.width*im.height>25_000_000:raise ValueError('Image exceeds 25 megapixels.')
            model,transform,threshold=load_model((os.environ.get('LOCAL_SMOKE_MODEL') or str(DEFAULT)));tensor=transform(im.convert('RGB')).unsqueeze(0)
    except (UnidentifiedImageError, OSError):raise ValueError('Invalid image.') from None
    with torch.inference_mode():score=float(torch.sigmoid(model(tensor).squeeze()))
    return {'smoke_detected':score>=threshold,'confidence':score,'reason':f'Local image classifier smoke score {score:.3f}; uncalibrated, human review required.','source':'local MobileNetV3 / uncalibrated','model_threshold':threshold}
