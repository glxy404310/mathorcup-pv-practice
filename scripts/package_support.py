"""将当前计算源码、数据与结果打包至本地 dist 目录。"""
from pathlib import Path
import zipfile,hashlib,json
r=Path(__file__).resolve().parents[1]; out=r/'paper/final'
dist=r/'dist'
dist.mkdir(exist_ok=True)
files=[]
for folder in ['src','tests','data','results','figures']:
 files += [p for p in (r/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='.DS_Store']
files += list((r/'docs').glob('*.json'))
files += list((r/'scripts').glob('*.py'))
files += [r/'paper/final/论文终稿.md',r/'docs/第一问_参考功率方案.md']
files += [r/'docs/B题 光伏电站发电功率日前预测问题.pdf',r/'docs/附件1 误差分析方法.pdf',r/'docs/data_sources.md',r/'requirements.txt',r/'requirements-lock.txt',r/'README.md']
manifest={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
with zipfile.ZipFile(dist/'支撑材料.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in files:z.write(p,p.relative_to(r))
 z.write(out/'表2_七天固定起报逐点预测.csv','表2_七天固定起报逐点预测.csv')
 z.writestr('文件哈希清单.json',json.dumps(manifest,ensure_ascii=False,indent=2))
print('archive',len(files),'source/data files')
