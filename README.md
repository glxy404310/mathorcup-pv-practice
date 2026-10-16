# 光伏电站出力特性与功率预测

基于 PVOD 数据集的 MathorCup B 题建模练习。以 **station08** 为主站，分析光伏出力特性，比较历史功率预测、融入 NWP 的预测及单站局地气象订正；station01 仅用于第一问的数据质量与同日出力对比。

当前论文为署名展示版，作者依次为孙煜凡、韦中天、叶锦润。正式参赛提交前须按匿名规范移除署名及文档作者属性。

## 阅读入口

- **论文**：[PDF 终稿](paper/final/论文终稿.pdf) · [可编辑 Word](paper/final/论文终稿.docx) · [正文文本](paper/final/论文终稿.md)
- **逐点预测**：[题目表 2](paper/final/表2_七天固定起报逐点预测.csv)，2688 条记录，功率单位 MW，时间为北京时间。
- **数据说明**：[来源与使用口径](docs/data_sources.md) · [晴空参考模型](docs/第一问_参考功率方案.md)
- **核验**：[数值核验记录](results/validation/final_metrics_check.json) · [初稿历史复核](docs/reviews/初稿复核记录.md)
- **交付与格式**：[交付说明](paper/final/交付说明.md) · [论文格式规范](docs/templates/论文格式及提交规范.pdf)

## 主要结果与适用范围

四个测试周共 1346 个白昼点，以 20 MW 为归一化容量，向前协议下：

| 方案 | nRMSE |
| --- | ---: |
| 历史功率验证选优 | 0.1210 |
| 历史功率与 NWP | 0.1086 |
| 原始气象对照 | 0.1148 |
| 非线性局地气象订正 | 0.1193 |

NWP 方案相对历史功率选优方案的误差下降约 10.28%，但按日期重抽的差值区间跨零；局地订正未降低总体误差。以上是固定样本上的条件回测结果。

- 数据覆盖 2018-07-01 至 2019-06-13，348 个日历日中有 345 个完整观测日，未满一年。
- 每个测试周固定一次起报，提前量为 24—191.75 小时；仅第一个目标日属于 24—48 小时日前窗口。
- NWP 缺少发行时刻、预报版本及有效提前量，起报时可用性尚未证实。
- 第四问仅检验单站局地统计订正，未验证空间分辨率提升。

## 项目结构

```text
├── src/                  # 六个计算及结果汇总脚本
├── tests/                # 数据清洗、参考功率及预测边界测试
├── scripts/              # 证据核验、论文排版、支撑材料打包
├── data/
│   ├── PVOD/             # 两站原始数据与完整元数据
│   └── processed/        # 清洗表，保留原始列和标记
├── results/
│   ├── q1/               # 两站第一问逐点结果与汇总
│   ├── q234/station08/   # 预测证据包与汇总图
│   └── validation/       # 终稿数值核验记录
├── figures/q1/           # 论文第一问图件
├── docs/                 # 赛题、误差附件、参数和数据来源
│   ├── templates/        # 写作模板与提交规范
│   └── reviews/          # 历史复核记录
├── paper/
│   ├── final/            # 唯一终稿、逐点预测与交付说明
│   └── layout/           # 定稿目录页码
├── requirements.txt      # 建模直接依赖
├── requirements-lock.txt # 建模环境版本锁定
└── requirements-paper.txt# 可选排版依赖
```

`build/`、`dist/`、`.venv/` 和缓存属于本地生成目录，不纳入版本管理。支撑材料压缩包生成于 `dist/`，避免在仓库中重复保存整套数据。旧草稿、任务分工和一次性排版检查文件不再保留在当前目录，可通过 Git 历史追溯。

## 环境与验证

已有 `.venv` 可直接使用。重新安装时，在项目根目录运行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/verify_results.py
```

Windows 将 `.venv/bin/python` 换成 `.venv\Scripts\python.exe`。原计算环境为 Python 3.13，完整版本见核验记录；跨平台安装需确认锁定依赖可用。

核验脚本只读现有证据：检查输入 SHA-256、2688 个唯一目标时间、1346 个白昼点，并独立复算两种协议共 22 组模型的六项总体指标。查看选参、训练时序等详细记录：

```bash
.venv/bin/python src/q234_forecast.py --inspect
```

## 重算结果

第一问主站：

```bash
.venv/bin/python src/q1_check_data.py --station station08 --source data/PVOD
.venv/bin/python src/q1_clean_data.py --rules docs/q1_cleaning_rules_station08.json
.venv/bin/python src/q1_reference_power.py --assumptions docs/q1_reference_assumptions_station08.json --source data/PVOD
.venv/bin/python src/q1_characteristics.py --station station08
.venv/bin/python src/build_q1_station08_report.py
```

最后一步读取保留的 station01 对比结果。需重算对照站时，前三步分别使用 `station01`、`docs/q1_cleaning_rules.json`、`docs/q1_reference_assumptions.json`，随后运行 `q1_characteristics.py --station station01`。旧脚本部分默认参数仍指向 station01 或已移除的 ZIP，请使用显式参数。

第二至四问：

```bash
OMP_NUM_THREADS=2 .venv/bin/python src/q234_forecast.py
.venv/bin/python src/q234_forecast.py --export-table2 paper/final/表2_七天固定起报逐点预测.csv
```

重算会覆盖相应结果、图件和自动报告，不会修改终稿。自动报告仍按计算脚本原有路径生成，已列入 `.gitignore`；研究结果变动后，需人工同步论文及重新核验。第一问输入发生变化后，应重算第二至四问以更新证据哈希。

## 论文排版与交付打包

现成 PDF 和 Word 可直接阅读。需要重排时，另装可选依赖：

```bash
.venv/bin/python -m pip install -r requirements-paper.txt
.venv/bin/python scripts/build_paper.py
```

输出为 `build/paper/论文终稿.docx`，不会覆盖已验收终稿。排版脚本读取正文、模板及完整计算源程序；原排版使用 Songti SC、Heiti SC、Times New Roman 和 Menlo 字体。缺少这些字体时需配置替代字体并重新检查分页。PDF 可由 Word 或 LibreOffice 导出；目录采用已验收终稿的页码映射，修改正文后必须更新 `paper/layout/toc_pages.json` 并检查导出文件。

```bash
.venv/bin/python scripts/package_support.py
```

打包输出 `dist/支撑材料.zip`。压缩包用于本地交付；正式提交的文件名、压缩格式及签名要求见格式规范。

## 数据引用

数据来源与许可边界见 [data_sources.md](docs/data_sources.md)。代码仓库许可不能替代数据许可；此仓库未额外授予原始数据的再分发许可。

Yao T, Wang J, Wu H, et al. A photovoltaic power output dataset: Multi-source photovoltaic power output dataset with Python toolkit. *Solar Energy*, 230: 122–130, 2021. DOI: 10.1016/j.solener.2021.09.050.
