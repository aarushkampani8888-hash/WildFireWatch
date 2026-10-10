"""Reproduce head training from cached features; select by validation loss."""
import json,torch
from pathlib import Path
from torchvision.models import mobilenet_v3_small,MobileNet_V3_Small_Weights

def main():
    torch.manual_seed(42);torch.set_num_threads(4)
    model=mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT)
    x=torch.load('data/features.pt',weights_only=True);records=json.loads(Path('data/manifest.json').read_text());y=torch.tensor([r['label'] for r in records],dtype=torch.float32)
    masks={s:torch.tensor([r['split']==s for r in records]) for s in ('train','validation','test')}
    head=torch.nn.Sequential(torch.nn.LayerNorm(576),torch.nn.Linear(576,128),torch.nn.ReLU(),torch.nn.Dropout(.2),torch.nn.Linear(128,1));optim=torch.optim.AdamW(head.parameters(),lr=.001,weight_decay=.01)
    tr=masks['train'];loss_fn=torch.nn.BCEWithLogitsLoss(pos_weight=(1-y[tr]).sum()/y[tr].sum());best=float('inf');state=None
    for epoch in range(300):
        head.train();optim.zero_grad();loss=loss_fn(head(x[tr]).squeeze(1),y[tr]);loss.backward();optim.step();head.eval()
        with torch.no_grad():v=float(torch.nn.functional.binary_cross_entropy_with_logits(head(x[masks['validation']]).squeeze(1),y[masks['validation']]))
        if v<best:best=v;state={k:t.detach().clone() for k,t in head.state_dict().items()};selected_epoch=epoch+1
    head.load_state_dict(state);head.eval()
    def metrics(mask,t):
        with torch.no_grad():p=torch.sigmoid(head(x[mask]).squeeze(1));truth=y[mask].bool();pred=p>=t
        tp=int((pred&truth).sum());tn=int((~pred&~truth).sum());fp=int((pred&~truth).sum());fn=int((~pred&truth).sum())
        return {'n':int(mask.sum()),'tp':tp,'tn':tn,'fp':fp,'fn':fn,'accuracy':(tp+tn)/int(mask.sum()),'precision':tp/max(1,tp+fp),'recall':tp/max(1,tp+fn),'false_positive_rate':fp/max(1,fp+tn)}
    threshold=max([i/100 for i in range(5,96)],key=lambda t:metrics(masks['validation'],t)['recall']-metrics(masks['validation'],t)['false_positive_rate'])
    prior=json.loads(Path('models/model-card.json').read_text());Path('models/finetune-card.json').write_text(json.dumps(prior,indent=2));report={k:v for k,v in prior.items() if k not in ('history','dashboard_threshold_metrics')}
    report.update(architecture='Frozen ImageNet MobileNetV3-small + trained normalized MLP head',validation_loss=best,epochs=300,selected_epoch=selected_epoch,threshold=threshold,selection_reason='Lower validation loss than fine-tuned candidate',readiness='experimental; poor held-out smoke recall')
    report['metrics']={s:metrics(m,threshold) for s,m in masks.items()};report['dashboard_threshold_metrics']={s:metrics(m,.8) for s,m in masks.items()}
    model.classifier=head;model.eval();torch.save({'state_dict':model.state_dict(),'threshold':threshold,'report':report},'models/smoke-classifier.pt');Path('models/model-card.json').write_text(json.dumps(report,indent=2));print(json.dumps(report['metrics'],indent=2))
if __name__=='__main__':main()
