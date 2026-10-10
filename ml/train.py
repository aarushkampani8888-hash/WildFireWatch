"""Train an event-separated smoke classifier from AI For Mankind challenge1."""
import argparse,hashlib,io,json,random,tarfile,time
from pathlib import Path
import torch
from PIL import Image
from torchvision.models import mobilenet_v3_small,MobileNet_V3_Small_Weights

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--archive',default='data/smoke-public.zip');ap.add_argument('--epochs',type=int,default=150);a=ap.parse_args()
    torch.manual_seed(42);random.seed(42);torch.set_num_threads(4)
    weights=MobileNet_V3_Small_Weights.DEFAULT;transform=weights.transforms();model=mobilenet_v3_small(weights=weights).eval()
    # Frozen ImageNet backbone; train a small binary head on real labeled frames.
    backbone=torch.nn.Sequential(model.features,model.avgpool,torch.nn.Flatten())
    records=[];seen=set();Path('data/frames').mkdir(parents=True,exist_ok=True)
    with tarfile.open(a.archive) as archive:
        for member in archive:
            parts=member.name.split('/')
            if len(parts)!=5 or parts[1]!='reference' or parts[2] not in ('smoke','no_smoke') or parts[-1].startswith('.') or not parts[-1].lower().endswith(('.jpg','.png','.jpeg')):continue
            raw=archive.extractfile(member).read();digest=hashlib.sha256(raw).hexdigest()
            if digest in seen:continue
            seen.add(digest);path=Path('data/frames')/(digest+'.jpg')
            with Image.open(io.BytesIO(raw)) as im: im.convert('RGB').resize((384,216)).save(path,quality=92)
            # Group by fire date/event name, excluding camera suffixes.
            group='-'.join(parts[3].split('-')[:2])
            records.append({'path':str(path),'label':int(parts[2]=='smoke'),'group':group,'sha256':digest,'original':member.name})
    groups=sorted({r['group'] for r in records});random.shuffle(groups);n=len(groups);split={g:('test' if i<int(n*.2) else 'validation' if i<int(n*.4) else 'train') for i,g in enumerate(groups)}
    for r in records:r['split']=split[r['group']]
    Path('data/manifest.json').write_text(json.dumps(records,indent=2));print(f'{len(records)} unique images, {n} event groups',flush=True)
    tensors=[]
    for r in records:
        with Image.open(r['path']) as im:tensors.append(transform(im.convert('RGB')))
    feats=[]
    with torch.inference_mode():
        for i in range(0,len(tensors),32):
            feats.append(backbone(torch.stack(tensors[i:i+32])).clone());print(f'features {min(i+32,len(tensors))}/{len(tensors)}',flush=True)
    x=torch.cat(feats).detach();torch.save(x,'data/features.pt');y=torch.tensor([r['label'] for r in records],dtype=torch.float32)
    masks={s:torch.tensor([r['split']==s for r in records]) for s in ('train','validation','test')}
    for s,m in masks.items():
        if set(y[m].tolist())!={0.,1.}:raise ValueError(f'{s} requires both classes; revise event split')
    head=torch.nn.Sequential(torch.nn.LayerNorm(576),torch.nn.Linear(576,128),torch.nn.ReLU(),torch.nn.Dropout(.2),torch.nn.Linear(128,1));optim=torch.optim.AdamW(head.parameters(),lr=.001,weight_decay=.01);best=float('inf');best_state=None
    tr=masks['train'];positive_weight=(1-y[tr]).sum()/y[tr].sum();loss_fn=torch.nn.BCEWithLogitsLoss(pos_weight=positive_weight)
    for epoch in range(a.epochs):
        head.train();optim.zero_grad();loss=loss_fn(head(x[tr]).squeeze(1),y[tr]);loss.backward();optim.step()
        head.eval()
        with torch.no_grad():v=torch.nn.functional.binary_cross_entropy_with_logits(head(x[masks['validation']]).squeeze(1),y[masks['validation']]).item()
        if v<best:best=v;best_state={k:t.detach().clone() for k,t in head.state_dict().items()}
    head.load_state_dict(best_state);head.eval()
    def metrics(mask,threshold):
        with torch.no_grad():p=torch.sigmoid(head(x[mask]).squeeze(1));truth=y[mask].bool();pred=p>=threshold
        tp=int((pred&truth).sum());tn=int((~pred&~truth).sum());fp=int((pred&~truth).sum());fn=int((~pred&truth).sum())
        return {'n':int(mask.sum()),'tp':tp,'tn':tn,'fp':fp,'fn':fn,'accuracy':(tp+tn)/int(mask.sum()),'precision':tp/max(1,tp+fp),'recall':tp/max(1,tp+fn),'false_positive_rate':fp/max(1,fp+tn)}
    # Choose a threshold using validation only; test is evaluated once afterward.
    candidates=[i/100 for i in range(5,96)];threshold=max(candidates,key=lambda t:(metrics(masks['validation'],t)['recall']+1-metrics(masks['validation'],t)['false_positive_rate']))
    report={'architecture':'Frozen ImageNet MobileNetV3-small + trained normalized MLP binary head','seed':42,'dataset':'AI For Mankind / HPWREN challenge1 smoke vs no_smoke','source':'https://github.com/aiformankind/wildfire-smoke-dataset','license_note':'Publisher requests credit; dataset licensing scope must be confirmed before commercial redistribution. Related annotated datasets CC BY-NC-SA 4.0.','split':'event name/date grouped 60/20/20; cameras may recur across events','threshold':threshold,'epochs':a.epochs,'validation_loss':best,'groups':{s:[g for g in groups if split[g]==s] for s in masks},'metrics':{}}
    report['metrics']={s:metrics(m,threshold) for s,m in masks.items()};report['limitations']=['Uncalibrated scores','No independent geographic/camera holdout','No operational fire-detection validation','Image classification only; no smoke localization']
    model.classifier=head;model.eval();Path('models').mkdir(exist_ok=True)
    torch.save({'state_dict':model.state_dict(),'threshold':threshold,'report':report},'models/smoke-classifier.pt')
    Path('models/model-card.json').write_text(json.dumps(report,indent=2));print(json.dumps(report['metrics'],indent=2),flush=True)
if __name__=='__main__':main()
