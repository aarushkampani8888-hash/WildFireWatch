"""Render completed provider evaluation without modifying the deployed app."""
import csv,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'data/provider-evaluation'
names={'ours':'WildfireWatch trained YOLO11n','pyronear_v8':'Pyronear YOLOv8s','pyronear_v11':'Pyronear Quick Quokka YOLO11s'}
def pct(v):return 'n/a' if v is None else f'{100*v:.1f}%'
def main():
 report=json.loads((D/'results.json').read_text());rows=[json.loads(x) for x in (D/'predictions.jsonl').read_text().splitlines()];thresholds=report['thresholds']
 paired={}
 for provider in ['pyronear_v8','pyronear_v11']:
  counts={'additional_smoke_caught':0,'additional_false_alarms':0,'smoke_caught_by_ours_only':0,'smoke_caught_by_both':0,'smoke_missed_by_both':0}
  for r in rows:
   a=r['scores']['ours']>=thresholds['ours'];b=r['scores'][provider]>=thresholds[provider]
   if r['smoke']:
    key='smoke_caught_by_both' if a and b else 'additional_smoke_caught' if b else 'smoke_caught_by_ours_only' if a else 'smoke_missed_by_both';counts[key]+=1
   elif b and not a:counts['additional_false_alarms']+=1
  paired[provider]=counts
 report['paired_comparison']=paired;(D/'results.json').write_text(json.dumps(report,indent=2))
 lines=['# External smoke-model evaluation','',f'Completed comparison on {len(rows)} images sampled proportionally from the 5,240-image test split. Fixed selection seed: provider-eval-2026-v1. 282 smoke / 230 clear images. No thresholds were fitted on these test images.','',
 'This measures image-level smoke presence, not box localization, ignition position, or event detection. The images were held out from WildfireWatch training. Their overlap with Pyronear training is unknown.','']
 for scope,models in report['metrics'].items():
  lines += [f'## {scope}','','| Model | Threshold | Precision | Smoke recall | Clear-image false alarms | TP / FN / FP / TN |','|---|---:|---:|---:|---:|---|']
  for name,m in models.items():lines.append(f"| {names[name]} | {thresholds[name]} | {pct(m['precision'])} | {pct(m['recall'])} | {pct(m['false_positive_rate'])} | {m['tp']} / {m['fn']} / {m['fp']} / {m['tn']} |")
  lines.append('')
 lines+=['## Incremental second-opinion value','','Counts below describe running a provider in addition to our model, using the fixed thresholds above. They do not demonstrate calibrated uncertainty or a validated ensemble.','']
 for name,counts in paired.items():lines.append(f"- {names[name]} catches {counts['additional_smoke_caught']} smoke images our model misses, while adding {counts['additional_false_alarms']} clear-image alarms. It misses {counts['smoke_caught_by_ours_only']} smoke images our model catches.")
 lines+=['','## CPU speed','','| Model | Median seconds/image | 95th percentile |','|---|---:|---:|']
 for name,t in report['seconds'].items():lines.append(f"| {names[name]} | {t['median']:.3f} | {t['p95']:.3f} |")
 lines+=['','Timing is local CPU inference after the first image, excluding ONNX image preparation, disk reading, network, startup, and UI updates. Our model uses 512 px; providers use 1024 px. This does not establish Railway throughput.','', '## Limitations','']+[f'- {v}' for v in report['limitations']]+['- Only 12 Pyro clear images are present; its source-specific false-alarm estimate is very uncertain.','- Wilson 95% intervals in results.json assume independent images; temporal correlations and near duplicates can make those intervals too narrow.','- Downloaded model-card licenses and embedded ONNX license notices differ. Resolve distribution obligations before deploying.','- No new model is enabled in the deployed application by this evaluation.','', '## Reproduce','','```sh','.venv/bin/python -u ml/evaluate_provider_models.py --sample-size 512','.venv/bin/python ml/report_provider_evaluation.py','```','','Raw scores, source/image hashes, per-source metrics, descriptive threshold sweeps, and timings are in data/provider-evaluation. Provider revisions and download SHA-256s are in data/provider-candidates/*/provenance.json.']
 (D/'REPORT.md').write_text('\n'.join(lines)+'\n')
 with (D/'summary.csv').open('w') as f:
  w=csv.writer(f);w.writerow(['dataset','model','threshold','precision','recall','false_positive_rate','tp','fn','fp','tn'])
  for scope,models in report['metrics'].items():
   for name,m in models.items():w.writerow([scope,name,thresholds[name],m['precision'],m['recall'],m['false_positive_rate'],m['tp'],m['fn'],m['fp'],m['tn']])
 fig,axes=plt.subplots(1,2,figsize=(11,4));short=['Our trained model','Pyronear v8','Pyronear v11'];colors=['#40785e','#477cba','#b16e32']
 for ax,key,title in [(axes[0],'recall','Smoke recall'),(axes[1],'false_positive_rate','False alarms on clear images')]:
  vals=[report['metrics']['all'][n][key]*100 for n in names];ax.bar(short,vals,color=colors);ax.set_ylim(0,100 if key=='recall' else 25);ax.set_ylabel('% of images');ax.set_title(title)
  for i,v in enumerate(vals):ax.text(i,v+2,f'{v:.1f}%',ha='center')
 fig.suptitle('512-image screening at fixed thresholds · not a full test-set evaluation');fig.tight_layout();fig.savefig(D/'comparison.png',dpi=160);plt.close(fig)
 print(json.dumps({'overall':report['metrics']['all'],'paired':paired,'timing':report['seconds']},indent=2))
if __name__=='__main__':main()
