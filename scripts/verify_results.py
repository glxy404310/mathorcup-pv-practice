"""只读核验输入哈希、逐点预测与证据包总体指标。"""
from pathlib import Path
import numpy as np,json,hashlib,pandas as pd
r=Path(__file__).resolve().parents[1]; z=np.load(r/'results/q234/station08/证据包.npz'); m=json.loads(str(z['metadata_json'])); day=z['daylight']; actual=z['actual_mw']; records=[]
for protocol in ['forward','retrospective']:
 for name in z['model_names']:
  pred=z[f'{protocol}_{name}']; e=(pred[day]-actual[day])/20
  records.append({'protocol':protocol,'model':str(name),'nRMSE':float(np.sqrt(np.mean(e**2))),'nMAE':float(np.mean(abs(e))),'nME':float(np.mean(e)),'r':float(np.corrcoef(actual[day],pred[day])[0,1]),'CR':float((1-np.sqrt(np.mean(e**2)))*100),'QR':float(np.mean(abs(e)<.25)*100)})
checks={k:hashlib.sha256((r/k).read_bytes()).hexdigest()==v for k,v in m['input_sha256'].items()}
assert all(checks.values()),checks
assert len(set(z['target_time']))==2688 and sum(day)==1346
csv=pd.read_csv(r/'paper/final/表2_七天固定起报逐点预测.csv');assert len(csv)==2688
out={'hashes_match':checks,'n_targets':2688,'n_daylight':int(sum(day)),'independent_metrics':records,'versions':m['versions'],'audits':m['audits'],'csv_columns':list(csv.columns),'stored_metric_example':m['metrics'][:2]}
print(json.dumps({'hashes':len(checks),'targets':len(csv),'metrics':records[:2],'columns':list(csv.columns),'stored':m['metrics'][:1]},ensure_ascii=False))

maximum_difference=0.0
for record in records:
 stored=next(row for row in m['metrics'] if row['protocol']==record['protocol'] and row['model']==record['model'] and row['group_type']=='overall')
 for key in ['nRMSE','nMAE','nME','r','CR','QR']:
  maximum_difference=max(maximum_difference,abs(record[key]-stored[{'CR':'CR_pct','QR':'QR_pct'}.get(key,key)]))
assert maximum_difference<1e-12,maximum_difference
print(f'全部14项输入哈希匹配；22组模型×6项指标最大差={maximum_difference:g}')
