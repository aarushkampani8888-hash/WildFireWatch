import json
from pathlib import Path
import pytest
pytest.importorskip('pyarrow')
from ml.prepare_detector import labels,camera_split

def test_smoke_mapping_and_fire_only_negative():
    assert labels('0 .5 .5 .2 .3\n1 .4 .4 .1 .2')=='0 .5 .5 .2 .3'
    assert labels('1 .5 .5 .2 .3')==''
    assert labels('')==''

def test_invalid_boxes_not_silently_used_as_negatives():
    for annotation in ('0 .5 .5 0 .1','0 .5 .5 1.1 .2','0 nan .5 .2 .2'):
        with pytest.raises(ValueError):labels(annotation)

def test_prepared_dataset_has_both_sources_and_no_exact_leakage():
    path=Path(__file__).resolve().parents[1]/'data/combined-smoke/manifest.json'
    if not path.exists():pytest.skip('Combined dataset not prepared')
    records=json.loads(path.read_text());assert len(records)==len({r['sha256'] for r in records})
    groups={s:{r['group'] for r in records if r['split']==s and r['dataset']=='pyro-sdis-v2'} for s in ('train','val','test')}
    assert groups['train'].isdisjoint(groups['val']|groups['test']);assert groups['val'].isdisjoint(groups['test'])
    for split in ('train','val','test'):
        subset=[r for r in records if r['split']==split]
        assert {r['dataset'] for r in subset}=={'pyro-sdis-v2','dfire'}
        assert {r['smoke'] for r in subset}=={True,False}
