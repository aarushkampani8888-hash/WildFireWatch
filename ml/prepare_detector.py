"""Combine pinned Pyro-SDIS v2 and the publisher-linked D-Fire mirror."""
import collections,hashlib,io,json,zipfile
from pathlib import Path
import pyarrow.parquet as pq
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/combined-smoke'

def labels(text,smoke_id=0):
    out=[]
    for line in (text or '').splitlines():
        values=line.split()
        if len(values)!=5:raise ValueError('Invalid annotation')
        cls=int(values[0]);coords=list(map(float,values[1:]))
        if any(not 0<=v<=1 for v in coords) or coords[2]<=0 or coords[3]<=0:raise ValueError('Invalid box coordinates')
        if cls==smoke_id:out.append('0 '+' '.join(values[1:]))
    return '\n'.join(out)
def camera_split(partner,camera):
    value=int(hashlib.sha256((partner+'/'+camera).encode()).hexdigest()[:8],16)%100
    return 'train' if value<80 else 'val' if value<90 else 'test'
def main():
    OUT.mkdir(parents=True,exist_ok=True);pending=[];counts=collections.Counter()
    for f in sorted((ROOT/'data/pyro/data').glob('*.parquet')):
        for batch in pq.ParquetFile(f).iter_batches(batch_size=32):
            for r in batch.to_pylist():
                raw=r['image']['bytes'];digest=hashlib.sha256(raw).hexdigest();target=OUT/'raw'/f'{digest}.jpg';target.parent.mkdir(exist_ok=True)
                if not target.exists():target.write_bytes(raw)
                pending.append({'dataset':'pyro-sdis-v2','original':r['image_name'],'sha256':digest,'labels':labels(r['annotations']),'split':camera_split(r['partner'],r['camera']),'group':r['partner']+'/'+r['camera'],'raw_path':str(target)});counts['pyro_original']+=1
    with zipfile.ZipFile(ROOT/'data/dfire/download.zip') as archive:
        names=set(archive.namelist())
        for name in sorted(names):
            if '/images/' not in name or not name.lower().endswith(('.jpg','.jpeg','.png')):continue
            labelname=str(Path(name.replace('/images/','/labels/')).with_suffix('.txt'))
            if labelname not in names:raise ValueError('Missing D-Fire label '+name)
            counts['dfire_original']+=1
            try: annotation=labels(archive.read(labelname).decode())
            except ValueError:
                counts['dfire_invalid_annotation_images_excluded']+=1;continue
            raw=archive.read(name);digest=hashlib.sha256(raw).hexdigest();target=OUT/'raw'/f'{digest}.jpg'
            if not target.exists():target.write_bytes(raw)
            pending.append({'dataset':'dfire','original':name,'sha256':digest,'labels':annotation,'split':name.split('/')[1],'group':None,'raw_path':str(target)})
    # Keep test before validation before training for duplicate families.
    priority={'test':0,'val':1,'train':2};pending.sort(key=lambda r:(priority[r['split']],r['dataset'],r['original']))
    records=[];seen={};conflicts={}
    for r in pending:
        digest=r['sha256']
        if digest in seen:
            counts['exact_duplicates_removed']+=1
            if seen[digest]['labels']!=r['labels']:conflicts[digest]=True
            continue
        seen[digest]=r;records.append(r)
    records=[r for r in records if r['sha256'] not in conflicts];counts['conflicting_label_families_removed']=len(conflicts)
    for i,r in enumerate(records):
        stem=r['dataset']+'-'+r['sha256'];ip=OUT/'images'/r['split']/(stem+'.jpg');lp=OUT/'labels'/r['split']/(stem+'.txt');ip.parent.mkdir(parents=True,exist_ok=True);lp.parent.mkdir(parents=True,exist_ok=True)
        if not ip.exists():
            with Image.open(r['raw_path']) as im:
                im=im.convert('RGB');im.thumbnail((1280,1280));im.save(ip,quality=95)
        lp.write_text(r['labels']);r['image']=str(ip);r['label_path']=str(lp);r['smoke']=bool(r['labels']);counts[r['dataset']+'_'+r['split']]+=1
        if i%2000==0:print(f'prepared {i}/{len(records)}',flush=True)
    for split in ('train','val','test'):
        subset=[r for r in records if r['split']==split]
        if not subset or not any(r['smoke'] for r in subset) or all(r['smoke'] for r in subset):raise ValueError('Each split requires smoke and negatives')
        counts[split+'_smoke']=sum(r['smoke'] for r in subset);counts[split+'_clear']=sum(not r['smoke'] for r in subset)
    records.sort(key=lambda r:r['image'])
    (OUT/'manifest.json').write_text(json.dumps(records,indent=2));(OUT/'data.yaml').write_text(f'path: {OUT}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: smoke\n')
    report={'sources':{'pyro':'https://huggingface.co/datasets/pyronear/pyro-sdis/tree/v2.0','dfire':'https://www.kaggle.com/datasets/sayedgamal99/smoke-fire-detection-yolo'},'counts':dict(counts),'split_method':'Pyro camera-group SHA256 split 80/10/10; D-Fire publisher mirror train/val/test; exact duplicates removed globally with test priority','limitations':['D-Fire lacks camera/event metadata; near-duplicate leakage not fully audited','Pyro camera counts may produce imbalanced split sizes','Resized preserving aspect ratio, max 1280 pixels']};(OUT/'preparation-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
