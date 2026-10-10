import base64,json
from pathlib import Path
import pytest
pytest.importorskip("PIL")
from backend import local_detector
ROOT=Path(__file__).resolve().parents[1]
def test_invalid_detector_input_rejected():
    for data in ('https://example.com/frame.jpg','data:image/png;base64,AAAA'):
        with pytest.raises(ValueError):local_detector.detect(data)
@pytest.mark.skipif(not (ROOT/'models/smoke-detector-candidate.pt').exists() or not (ROOT/'data/combined-smoke/manifest.json').exists(),reason='Detector training pending')
def test_trained_detector_inference_has_valid_boxes(monkeypatch):
    monkeypatch.setenv('LOCAL_SMOKE_DETECTOR',str(ROOT/'models/smoke-detector-candidate.pt'))
    records=json.loads((ROOT/'data/combined-smoke/manifest.json').read_text());row=next(r for r in records if r['split']=='test' and r['smoke'])
    frame='data:image/jpeg;base64,'+base64.b64encode(Path(row['image']).read_bytes()).decode();finding=local_detector.detect(frame)
    assert 0<=finding['confidence']<=1;assert finding['source'].startswith('local YOLO11n')
    with pytest.raises(ValueError):local_detector.detect('data:image/png;base64,AAAA')
    for box in finding['boxes']:assert all(0<=v<=1 for v in box['xyxy_normalized'])


def test_explicit_missing_checkpoint_does_not_use_old_classifier(monkeypatch,tmp_path):
    from backend.local_vision import detect_local,available
    monkeypatch.setenv('LOCAL_SMOKE_DETECTOR',str(tmp_path/'missing.pt'))
    assert not available()
    with pytest.raises(ValueError,match='checkpoint is unavailable'):detect_local('data:image/png;base64,AAAA')
