"""Reproducible image-level smoke-presence comparison; no threshold fitting."""
import argparse, collections, hashlib, json, math, time
from pathlib import Path
import numpy as np
from PIL import Image
import onnxruntime as ort
ROOT=Path(__file__).resolve().parents[1]
def select(n):
    records=[r for r in json.loads((ROOT/'data/combined-smoke/manifest.json').read_text()) if r['split']=='test']
    groups=collections.defaultdict(list)
    for r in records:groups[(r['dataset'],r['smoke'])].append(r)
    counts={k:int(n*len(v)/len(records)) for k,v in groups.items()}
    for k in sorted(groups,key=lambda k:-(n*len(groups[k])/len(records)-counts[k]))[:n-sum(counts.values())]:counts[k]+=1
    out=[]
    for k,rs in sorted(groups.items()):
        rs.sort(key=lambda r:hashlib.sha256(('provider-eval-2026-v1:'+r['sha256']).encode()).hexdigest())
        out.extend(rs[:counts[k]])
    return out

def letterbox(path):
    with Image.open(path) as im:
        im=im.convert('RGB');w,h=im.size;scale=min(1024/w,1024/h);im=im.resize((round(w*scale),round(h*scale)),Image.Resampling.BILINEAR)
        canvas=Image.new('RGB',(1024,1024),(114,114,114));canvas.paste(im,((1024-im.width)//2,(1024-im.height)//2))
        return np.asarray(canvas,dtype=np.float32).transpose(2,0,1)[None]/255

def wilson(success,n):
    if not n:return None
    z=1.96;p=success/n;den=1+z*z/n;center=(p+z*z/(2*n))/den;radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [round(center-radius,4),round(center+radius,4)]

def metrics(rows,name,threshold):
    tp=fp=tn=fn=0
    for r in rows:
        yes=r['scores'][name]>=threshold
        if r['smoke']:
            if yes:tp+=1
            else:fn+=1
        elif yes:fp+=1
        else:tn+=1
    return {'tp':tp,'fp':fp,'tn':tn,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,'false_positive_rate':fp/(fp+tn) if fp+tn else None,'recall_ci95':wilson(tp,tp+fn),'fpr_ci95':wilson(fp,fp+tn)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--sample-size',type=int,default=512);args=ap.parse_args()
    target=ROOT/'data/provider-evaluation';target.mkdir(exist_ok=True);records=select(args.sample_size)
    (target/'selected-images.json').write_text(json.dumps([{k:r[k] for k in ('sha256','dataset','smoke','image','group')} for r in records],indent=2))
    import torch
    torch.set_num_threads(2)
    from ultralytics import YOLO
    original=YOLO(str(ROOT/'models/smoke-detector.pt'))
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    paths={'pyronear_v8':ROOT/'data/provider-candidates/yolov8s/yolov8s.onnx','pyronear_v11':ROOT/'data/provider-candidates/yolo11s_quick-quokka_v8.0.0/export/best.onnx'}
    sessions={name:ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider']) for name,path in paths.items()}
    for s in sessions.values():s.disable_fallback()
    rows=[];start=time.monotonic()
    with (target/'predictions.jsonl').open('w') as f:
        for i,r in enumerate(records):
            scores={};latency={};t=time.monotonic()
            result=original.predict(r['image'],imgsz=512,conf=.001,device='cpu',verbose=False)[0]
            scores['ours']=max((float(b.conf[0]) for b in result.boxes if int(b.cls[0])==0),default=0.);latency['ours']=time.monotonic()-t
            x=letterbox(r['image'])
            for name,s in sessions.items():
                t=time.monotonic();out=s.run(None,{s.get_inputs()[0].name:x})[0]
                if out.shape[1]!=5:raise RuntimeError(f'Unexpected output {out.shape}')
                scores[name]=float(out[0,4,:].max());latency[name]=time.monotonic()-t
            row={'sha256':r['sha256'],'dataset':r['dataset'],'smoke':r['smoke'],'image':r['image'],'scores':scores,'seconds':latency};rows.append(row);f.write(json.dumps(row)+'\n');f.flush()
            if (i+1)%16==0:print(f'{i+1}/{len(records)} images; elapsed {time.monotonic()-start:.0f}s',flush=True)
    thresholds={'ours':.25,'pyronear_v8':.2,'pyronear_v11':.2}
    report={'sample_size':len(rows),'test_population':5240,'seed':'provider-eval-2026-v1','selection':'proportional stratification by source and smoke presence; SHA256 ordering','thresholds':thresholds,'metrics':{},'seconds':{},'threshold_sensitivity':{},'limitations':['Image-level presence, not bounding-box localization or video/event detection','Test overlap with Pyronear training is unknown','Small sample screening, not full 5240-image evaluation','Quick Quokka export class is named item; treated as smoke according to model card','Model-card Apache-2.0 versus embedded Ultralytics AGPL-3.0 notices require license review','CPU timing on local Mac, not Railway; original 512px versus provider 1024px inputs','Threshold sensitivity is descriptive, not threshold optimization']}
    for scope in ['all','dfire','pyro-sdis-v2']:
        subset=rows if scope=='all' else [r for r in rows if r['dataset']==scope]
        report['metrics'][scope]={name:metrics(subset,name,t) for name,t in thresholds.items()}
    for name in thresholds:
        durations=[r['seconds'][name] for r in rows][1:]
        report['seconds'][name]={'median':float(np.median(durations)),'p95':float(np.quantile(durations,.95))}
        report['threshold_sensitivity'][name]={str(t):metrics(rows,name,t) for t in [.05,.1,.2,.25,.5]}
    (target/'results.json').write_text(json.dumps(report,indent=2));print('COMPLETE',json.dumps(report['metrics']['all']),flush=True)
if __name__=='__main__':main()
