"""Fine-tune visual features using the existing event-separated manifest."""
import copy,json,random,time
from pathlib import Path
import torch
from PIL import Image
from torchvision.models import mobilenet_v3_small,MobileNet_V3_Small_Weights

def main():
    torch.manual_seed(42);random.seed(42);torch.set_num_threads(4)
    records=json.loads(Path('data/manifest.json').read_text());transform=MobileNet_V3_Small_Weights.DEFAULT.transforms()
    xs=[]
    for r in records:
        with Image.open(r['path']) as im:xs.append(transform(im.convert('RGB')))
    x=torch.stack(xs);y=torch.tensor([r['label'] for r in records],dtype=torch.float32)
    masks={s:torch.tensor([r['split']==s for r in records]) for s in ('train','validation','test')}
    model=mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT)
    model.classifier=torch.nn.Sequential(torch.nn.LayerNorm(576),torch.nn.Linear(576,128),torch.nn.ReLU(),torch.nn.Dropout(.2),torch.nn.Linear(128,1))
    for p in model.features.parameters():p.requires_grad=False
    for block in list(model.features.children())[-4:]:
        for p in block.parameters():p.requires_grad=True
    optim=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=.0005,weight_decay=.01)
    tr=masks['train'];loss_fn=torch.nn.BCEWithLogitsLoss(pos_weight=(1-y[tr]).sum()/y[tr].sum());best=float('inf');best_state=None;history=[]
    train_ids=tr.nonzero().flatten();val_ids=masks['validation'].nonzero().flatten()
    def scores(ids):
        model.eval()
        with torch.inference_mode():return torch.cat([torch.sigmoid(model(x[ids[i:i+32]]).squeeze(1)) for i in range(0,len(ids),32)])
    for epoch in range(10):
        start=time.monotonic();model.train()
        # Do not update batchnorm statistics in frozen early blocks.
        for block in list(model.features.children())[:-4]:block.eval()
        ids=train_ids[torch.randperm(len(train_ids))];total=0
        for i in range(0,len(ids),32):
            batch=ids[i:i+32];optim.zero_grad();loss=loss_fn(model(x[batch]).squeeze(1),y[batch]);loss.backward();optim.step();total+=float(loss.detach())*len(batch)
        pv=scores(val_ids);v=float(torch.nn.functional.binary_cross_entropy(pv,y[val_ids]));history.append({'epoch':epoch+1,'train_loss':total/len(ids),'validation_loss':v})
        if v<best:best=v;best_state=copy.deepcopy(model.state_dict())
        print(f'epoch {epoch+1}/10 loss={total/len(ids):.4f} val={v:.4f} seconds={time.monotonic()-start:.1f}',flush=True)
    model.load_state_dict(best_state);model.eval()
    def metrics(p,truth,t):
        pred=p>=t;truth=truth.bool();tp=int((pred&truth).sum());tn=int((~pred&~truth).sum());fp=int((pred&~truth).sum());fn=int((~pred&truth).sum())
        return {'n':len(truth),'tp':tp,'tn':tn,'fp':fp,'fn':fn,'accuracy':(tp+tn)/len(truth),'precision':tp/max(1,tp+fp),'recall':tp/max(1,tp+fn),'false_positive_rate':fp/max(1,fp+tn)}
    pv=scores(val_ids);threshold=max([i/100 for i in range(5,96)],key=lambda t:metrics(pv,y[val_ids],t)['recall']-metrics(pv,y[val_ids],t)['false_positive_rate'])
    report=json.loads(Path('models/model-card.json').read_text());report.update(architecture='ImageNet MobileNetV3-small; final four blocks and normalized MLP head fine-tuned',epochs=10,validation_loss=best,threshold=threshold,history=history)
    report['metrics']={s:metrics(scores(m.nonzero().flatten()),y[m],threshold) for s,m in masks.items()};report['dashboard_threshold_metrics']={s:metrics(scores(m.nonzero().flatten()),y[m],.8) for s,m in masks.items()}
    report['limitations'].append('Test events were examined during development of earlier baselines; fresh independent evaluation required')
    torch.save({'state_dict':model.state_dict(),'threshold':threshold,'report':report},'models/smoke-classifier.pt');Path('models/model-card.json').write_text(json.dumps(report,indent=2));print(json.dumps(report['metrics'],indent=2),flush=True)
if __name__=='__main__':main()
