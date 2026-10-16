# 光伏电站出力特性与功率预测

基于 PVOD 数据集的 MathorCup B 题建模练习。以 **station08** 为主站，分析光伏出力特性，比较历史功率预测、融入 NWP 的预测及单站局地气象订正；station01 仅用于第一问的数据质量与同日出力对比。

当前论文为署名展示版，作者依次为孙煜凡、韦中天、叶锦润。正式参赛提交前须按匿名规范移除署名及文档作者属性。

## 阅读入口

- **论文**：[PDF 终稿](paper/final/论文终稿.pdf) · [可编辑 Word](paper/final/论文终稿.docx) · [正文文本](paper/final/论文终稿.md)
- **逐点预测**：[题目表 2](paper/final/表2_七天固定起报逐点预测.csv)，2688 条记录，功率单位 MW，时间为北京时间。
- **数据说明**：[来源与使用口径](docs/data_sources.md) · [晴空参考模型](docs/第一问_参考功率方案.md)
- **核验**：[数值核验记录](results/validation/final_metrics_check.json)

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
├── src/                  # 数据清洗、参考功率、特性分析与预测程序
├── tests/                # 处理逻辑与预测边界测试
├── scripts/              # 结果核验与支撑材料打包
├── data/
│   ├── PVOD/             # 两站原始数据与完整元数据
│   └── processed/        # 清洗后的数据
├── results/
│   ├── q1/               # 第一问逐点结果与汇总
│   ├── q234/station08/   # 第二至四问证据包与汇总图
│   └── validation/       # 数值核验记录
├── figures/q1/           # 第一问结果图
├── docs/                 # 赛题、误差附件、处理参数与来源说明
├── paper/final/          # 署名终稿和逐点预测表
├── requirements.txt      # 建模直接依赖
└── requirements-lock.txt # 复现环境版本锁定
```

`dist/`、`.venv/` 和缓存不纳入版本管理。支撑材料压缩包生成于 `dist/`，可按需重新生成。

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

## 支撑材料打包

```bash
.venv/bin/python scripts/package_support.py
```

输出为 `dist/支撑材料.zip`，包含计算程序、测试、数据、参数、结果、图件和复现说明。

## 数据引用

数据来源与许可边界见 [data_sources.md](docs/data_sources.md)。代码仓库许可不能替代数据许可；此仓库未额外授予原始数据的再分发许可。

Yao T, Wang J, Wu H, et al. A photovoltaic power output dataset: Multi-source photovoltaic power output dataset with Python toolkit. *Solar Energy*, 230: 122–130, 2021. DOI: 10.1016/j.solener.2021.09.050.
