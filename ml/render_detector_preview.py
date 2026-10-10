"""Render predetermined held-out examples with ground truth and detector boxes."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from PIL import Image
from ultralytics import YOLO
ROOT=Path(__file__).resolve().parents[1]
def main():
    records=json.loads((ROOT/'data/combined-smoke/manifest.json').read_text());model=YOLO(str(ROOT/'models/smoke-detector-candidate.pt'))
    examples=[]
    for dataset in ('pyro-sdis-v2','dfire'):
        for smoke in (True,False):examples.append(next(r for r in records if r['split']=='test' and r['dataset']==dataset and r['smoke']==smoke))
    fig,axes=plt.subplots(2,2,figsize=(14,9));fig.suptitle('Held-out examples: green = labeled smoke; orange = model detections (score ≥ 0.25)',fontsize=13)
    for ax,row in zip(axes.flat,examples):
        im=Image.open(row['image']).convert('RGB');w,h=im.size;ax.imshow(im)
        for line in row['labels'].splitlines():
            _,cx,cy,bw,bh=map(float,line.split());ax.add_patch(Rectangle(((cx-bw/2)*w,(cy-bh/2)*h),bw*w,bh*h,fill=False,color='lime',linewidth=2))
        result=model.predict(im,imgsz=512,conf=.25,device='cpu',verbose=False)[0]
        for box in result.boxes:
            x1,y1,x2,y2=map(float,box.xyxy[0]);ax.add_patch(Rectangle((x1,y1),x2-x1,y2-y1,fill=False,color='darkorange',linewidth=2));ax.text(x1,y1,f'{float(box.conf[0]):.2f}',color='black',backgroundcolor='darkorange',fontsize=9)
        ax.set_title(row['dataset']+' / labeled '+('smoke' if row['smoke'] else 'no smoke')+f' / {len(result.boxes)} detections');ax.axis('off')
    fig.tight_layout();fig.savefig(ROOT/'models/detector-preview.png',dpi=130);plt.close(fig)
if __name__=='__main__':main()
