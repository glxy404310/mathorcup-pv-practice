# 光伏功率预测建模练习 · station08

当前主站为 **station08**，已有第一问分析和第2—4问条件回测。先读 [C剩余任务](C剩余任务.md)，再读 `paper/` 中两份交接稿。它们是可核查的论文素材，尚不是正式定稿；第四问的真实空间降尺度、NWP起报可用性仍待补证。

## 文件入口

| 位置 | 用途 |
| --- | --- |
| `paper/第一问_station08重跑与对比.md` | 第一问方法、结果、与station01的同日比较 |
| `paper/第2至4问_station08_C交接初稿.md` | 第2—4问方法、结果、评估口径与局限 |
| `src/`、`tests/` | 6个源代码文件、4个测试文件 |
| `data/PVOD/` | station08原始数据；station01仅用于第一问对比；完整元数据保持原样 |
| `data/processed/` | 两站已有清洗表，保留原始列和清洗标记 |
| `results/q1/` | 第一问必要汇总、逐点参考、正文表格及对比证据 |
| `results/q234/station08/` | 一个证据包和一张汇总图，预测与指标集中保存 |
| `figures/q1/` | 当前第一问正文使用的4张图 |
| `docs/` | 原题与误差附件、两站参数、数据来源、参考模型说明和个人笔记 |

## 使用与复现

已有 `.venv` 可直接运行。新机器可用 `python3 -m venv .venv`，再执行 `.venv/bin/python -m pip install -r requirements-lock.txt`。锁定版本记录了本次环境；跨平台安装仍需检查兼容性。

查看第2—4问证据、运行测试：

```bash
.venv/bin/python src/q234_forecast.py --inspect
.venv/bin/python -m unittest discover -s tests -v
```

重算第2—4问（会覆盖对应证据包、汇总图和自动生成的交接稿）：

```bash
OMP_NUM_THREADS=2 .venv/bin/python src/q234_forecast.py
```

重算station08第一问：

```bash
.venv/bin/python src/q1_check_data.py --station station08 --source data/PVOD
.venv/bin/python src/q1_clean_data.py --rules docs/q1_cleaning_rules_station08.json
.venv/bin/python src/q1_reference_power.py --assumptions docs/q1_reference_assumptions_station08.json --source data/PVOD
.venv/bin/python src/q1_characteristics.py --station station08
.venv/bin/python src/build_q1_station08_report.py
```

最后一步会校验保留的station01对比依据。第一问完整重算会再生成详细诊断表；这些是中间产物，不必全部交给C。第一问输入或代码发生变更后，应重算第2—4问以更新证据哈希。旧脚本部分默认参数仍指向station01和旧ZIP，**请使用上述显式参数**。

需要题目表2时才导出：

```bash
.venv/bin/python src/q234_forecast.py --export-table2 paper/表2.csv
```

此表是本次每周固定起报的逐点结果；正式附件的列选择、格式和题目样表匹配由C复核。

## 整理规则

2026-10-14清理了未参与当前实验的8站原始表、McClear样例、合成数据、旧报告目录、station01旧正文和图、重复摘要及可再生诊断。station01的原始/清洗数据和必要结果仍用于复现已写入正文的对比，不作为第2—4问训练数据。metadata.csv没有裁剪，避免改变输入证据。

保留 `.git` 历史和 `.venv` 运行环境；交付打包时排除它们及缓存。个人原笔记移至 `docs/第一题总结_个人笔记.md`。当前整理没有提交Git；已跟踪文件的旧版本仍可从仓库历史追溯。

后续只维护一份正式论文 `paper/论文初稿.md`（由C新建），不再新增“最终版2”等副本。自动生成的两份交接稿与正式论文分开，防止重跑覆盖C的人工写作。数字优先从当前证据读取，不从旧聊天或旧报告抄录。
