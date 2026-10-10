"""Train a smoke detector on both datasets, then evaluate held-out test data."""
import argparse,csv,hashlib,json,shutil,time
from pathlib import Path
import torch
from ultralytics import YOLO,settings
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--epochs',type=int,default=15);ap.add_argument('--imgsz',type=int,default=512);ap.add_argument('--batch',type=int,default=16);ap.add_argument('--resume',action='store_true');ap.add_argument('--evaluate-only',action='store_true');a=ap.parse_args()
    torch.set_num_threads(4);settings.update({'sync':False,'wandb':False,'clearml':False,'mlflow':False,'comet':False,'tensorboard':False})
    root=ROOT/'data/detector-runs';name='combined-smoke';out=root/name
    device='mps' if torch.backends.mps.is_available() else 'cpu'
    model=None if a.evaluate_only else YOLO(str(out/'weights/last.pt') if a.resume else 'yolo11n.pt')
    started=time.time()
    def progress(trainer):
        payload={'stage':'training','epoch_completed':min(trainer.epoch+1,trainer.epochs),'epochs':trainer.epochs,'device':device,'elapsed_seconds':round(time.time()-started),'metrics':{k:float(v) for k,v in trainer.metrics.items()}}
        (ROOT/'data/detector-progress.json').write_text(json.dumps(payload,indent=2))
        print('WILDFIREWATCH_PROGRESS '+json.dumps(payload),flush=True)
    if model is not None:
        model.add_callback('on_fit_epoch_end',progress)
        model.train(data=str(ROOT/'data/combined-smoke/data.yaml'),epochs=a.epochs,imgsz=a.imgsz,batch=a.batch,device=device,workers=4,seed=42,deterministic=True,optimizer='AdamW',lr0=.001,freeze=10,patience=4,close_mosaic=3,mosaic=.5,cache=False,plots=True,project=str(root),name=name,exist_ok=True,save=True,resume=a.resume,verbose=False)
    best=out/'weights/best.pt'
    if not best.exists():raise RuntimeError('Training did not produce best checkpoint')
    candidate=YOLO(str(best));metrics=candidate.val(data=str(ROOT/'data/combined-smoke/data.yaml'),split='test',imgsz=a.imgsz,batch=a.batch,device=device,workers=4,plots=True,project=str(root),name='held-out-test',exist_ok=True)
    records=json.loads((ROOT/'data/combined-smoke/manifest.json').read_text());test_records=[r for r in records if r['split']=='test']
    presence={d:{'tp':0,'tn':0,'fp':0,'fn':0} for d in ('pyro-sdis-v2','dfire')}
    by_path={str(Path(r['image']).resolve()):r for r in test_records}
    seen_predictions=set()
    # Ultralytics eagerly decodes a list of paths; bound memory to 64 frames.
    for offset in range(0,len(test_records),64):
        chunk=test_records[offset:offset+64]
        for result in candidate.predict(source=[r['image'] for r in chunk],stream=True,imgsz=a.imgsz,conf=.25,batch=a.batch,device=device,verbose=False):
            path=str(Path(result.path).resolve());row=by_path[path];seen_predictions.add(path)
            pred=len(result.boxes)>0;truth=row['smoke'];key='tp' if pred and truth else 'fp' if pred else 'fn' if truth else 'tn';presence[row['dataset']][key]+=1
        if offset%512==0:print(f'Image presence evaluated: {len(seen_predictions)}/{len(test_records)}',flush=True)
    if len(seen_predictions)!=len(test_records):raise RuntimeError('Missing evaluation image predictions')
    presence['combined']={key:sum(v[key] for v in presence.values()) for key in ('tp','tn','fp','fn')}
    for values in presence.values():
        values.update(recall=values['tp']/max(1,values['tp']+values['fn']),precision=values['tp']/max(1,values['tp']+values['fp']),false_positive_rate=values['fp']/max(1,values['fp']+values['tn']))
    preparation=json.loads((ROOT/'data/combined-smoke/preparation-report.json').read_text())
    training_rows=list(csv.DictReader((out/'results.csv').open()))
    completed_epochs=len(training_rows)
    report={'training_seconds':float(training_rows[-1]['time']),'completed_epochs':completed_epochs,'checkpoint_sha256':hashlib.sha256(best.read_bytes()).hexdigest(),'architecture':'YOLO11n, COCO pretrained, smoke-only head; first 10 layers frozen','device':device,'requested_epochs':a.epochs,'image_size':a.imgsz,'batch_size':a.batch,'evaluation_only':a.evaluate_only,'run_elapsed_seconds':round(time.time()-started),'test_detection_metrics':{k:float(v) for k,v in metrics.results_dict.items()},'preparation':preparation,'image_presence_at_confidence_025':presence,'checkpoint_source':str(best),'readiness':'experimental; detection metrics require field validation','limitations':['Box-level detection metrics are not directly comparable to prior image-classifier recall','D-Fire camera/event provenance unavailable; near-duplicate leakage may inflate results','No operational evacuation or wildfire response validation'],'licenses':{'Pyro-SDIS':'Apache-2.0','D-Fire collection':'CC0-1.0','Ultralytics':'AGPL-3.0; review obligations before distribution/deployment'}}
    dest=ROOT/'models/smoke-detector-candidate.pt';shutil.copy2(best,dest);(ROOT/'models/detector-card.json').write_text(json.dumps(report,indent=2));(ROOT/'data/detector-progress.json').write_text(json.dumps({'stage':'complete','report':str(ROOT/'models/detector-card.json')},indent=2));print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
