# mathorcup-pv-practice
三人团队光伏功率预测建模练习

## 第一问，步骤1：读表与质量检查

当前选用PVOD v1.0的station01。原始数据保存在`docs/PVODdatasets_v1.0.zip`，脚本直接读取ZIP，不改写原始文件。

使用Python 3.13创建环境（本次实际运行版本及依赖版本见输出的`summary.json`）：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python src/q1_check_data.py
```

已创建环境时，从项目目录直接运行：

```bash
.venv/bin/python src/q1_check_data.py
```

`requirements.txt`固定直接依赖；`requirements-lock.txt`保存本次Python 3.13环境的全部依赖版本。需要按本次完整版本复现时，使用`python -m pip install -r requirements-lock.txt`。

脚本将UTC时间转换为北京时间，检查字段、缺测、重复、15分钟时间间隔、日覆盖和四个测试周，并根据站点坐标计算太阳高度角用于昼夜筛查。海拔缺失，暂设0m；本步不计算理论参考功率。功率字段原单位为MW，容量字段由kW除以1000转换为MW。

输出：

- `results/q1/station01/检查摘要.md`：读表检查说明、筛查结果与局限。
- `results/q1/station01/summary.json`：结果、输入SHA256、规则与运行版本。
- `results/q1/station01/field_profile.csv`：每列缺失、解析失败、无穷值和分位数。
- `results/q1/station01/flagged_rows.csv`：可疑记录、筛查标记及原始CSV行号。
- `results/q1/station01/missing_timestamps.csv`：缺失的15分钟时间点。
- `results/q1/station01/interval_counts.csv`：相邻唯一时间戳间隔统计。
- `results/q1/station01/daily_coverage.csv`：每日记录数与唯一时间点数。
- `results/q1/station01/test_week_coverage.csv`：四个测试月月末7天的时间覆盖。
- `results/q1/station01/preview.csv`：前8条解析记录，含UTC、北京时间与太阳高度角。
- `figures/q1/station01_week.png`：连续一周功率和辐照诊断图。

默认图窗为2018-08-25至2018-08-31（北京时间），选择固定窗口用于检查，不声称代表全年。更换图窗：

```bash
.venv/bin/python src/q1_check_data.py --plot-start 2019-02-22 --plot-days 7
```

同一站点重跑会覆盖该站点的派生检查结果和诊断图，原始ZIP保持不变。可疑值只作标记，不自动删除、归零或裁剪；NWP发布时间尚未确认，不能由本步结果宣称已验证真实日前预测。数据来源与待确认口径见`docs/data_sources.md`。

已安装的数学建模辅助技能、来源版本及使用边界见`docs/技能安装记录.md`。

## 第一问，步骤2：复查持值与第一版清洗

```bash
.venv/bin/python src/q1_clean_data.py
```

规则保存在`docs/q1_cleaning_rules.json`。只有连续至少4个15分钟采样点的功率及六项现场气象量完全相同、且该段含深夜正功率与正辐照时，才标为可疑持值段。首点保留待复查，后续重复点在七项`*_clean`列中设为缺失。白昼有辐照但零功率、近地平线小正功率继续保留并标记；不填补、不归零、不裁剪。

输出：

- `data/processed/station01_q1_clean.csv`：保留原始列、全部时间点、CSV原始行号，以及清洗列和复查标记。
- `results/q1/station01/清洗摘要.md`、`cleaning_summary.json`：规则、处理数量、局限与输入/规则哈希。
- `results/q1/station01/frozen_runs.csv`：可疑持值段及边界。
- `results/q1/station01/cleaning_log.csv`：逐值原值、清洗值和原因。
- `results/q1/station01/cleaned_daily_coverage.csv`：每日有效功率点数，后续月度比较需要据此筛选完整日。
- `results/q1/station01/cleaned_test_week_coverage.csv`：原测试周时间覆盖和清洗后有效功率检查。
- `figures/q1/station01_frozen_review.png`：持值段原始/清洗列对照图。

第一问统计使用`power_clean`，不使用原始`power`列冒充清洗结果。`valid_power_for_q1`只表示通过当前基础规则，不表示全部物理口径已经验证；`needs_review`可与其同时为真。缺失点不补零，不完整日不直接作为完整日发电量比较。

此规则使用整段序列进行离线质量复查，不能把事后标记作为日前预测输入，也不能宣称起报时已知道未来段会持值。后续真实回测需要按实际可用时刻处理质量标记。

清洗边界验证：

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## 第一问，步骤3：假设工况的晴空参考功率

```bash
.venv/bin/python src/q1_reference_power.py
```

参数与假设保存在`docs/q1_reference_assumptions.json`；计算口径、公式、来源与局限见`docs/第一问_参考功率方案.md`。

利用真实坐标、朝南33°倾角和74000块270 Wp组件，得到19.98 MWp直流额定容量。第一版固定组件温度25°C，采用Ineichen晴空辐照、isotropic板面转换、PVWatts逆变器模型。交流限制20 MW、海拔0米、额定效率96%均为明确记录的假设；额外损耗0%、10%、20%及海拔200米只作敏感性情景，没有使用实测功率拟合。

输出`results/q1/station01/reference_power.csv`、`reference_sensitivity.csv`、`reference_summary.json`和`figures/q1/station01_reference_day.png`。MAE等描述实际与物理参考的偏差，不是日前预测评估；参考不是严格发电上限。本步不计算日发电量，功率采样口径仍待确认。

角色B可按`docs/角色B_第一问学习记录.md`自行复现、解释核心口径并记录读图发现。

## 第一问，步骤4：月度、日内与15分钟波动

```bash
.venv/bin/python src/q1_characteristics.py
```

脚本校验参考曲线与清洗数据版本一致，月度和日内曲线统一使用完整96点功率日。日发电量暂按`Σ采样功率×0.25小时`作矩形积分估计，注明功率采样口径未确认；缺失日不补零、不作为完整日。季节分组采用3—5月春、6—8月夏、9—11月秋、12—2月冬；当前夏季含2018年7/8月和2019年6月1—13日，不是完整连续夏季。

所有变化均要求相邻时间确实相差15分钟、两个值有效；波动图要求两端太阳高度角均>0。辐照/功率变化只作相关性比较，不据此认定唯一原因。

输出保存在`results/q1/station01/`：

- `特性分析摘要.md`、`characteristics_summary.json`：口径、观察、数量、哈希与局限。
- `daily_characteristics.csv`、`monthly_characteristics.csv`：逐日积分估计、有效天数与月度分布。
- `seasonal_characteristics.csv`、`seasonal_diurnal_profiles.csv`：季节分组与各时刻平均、分位数和样本数。
- `continuous_15min_changes.csv`、`largest_daylight_changes.csv`：连续变化及最大变化时段。
- `monthly_daylight_deviation.csv`：实际与基准晴空参考的白昼偏差，不是预测误差。

三张图保存在`figures/q1/`：`station01_monthly_integral.png`、`station01_seasonal_diurnal.png`、`station01_daylight_fluctuation.png`。

## 第一问，步骤5：生成正文审阅稿

```bash
.venv/bin/python src/build_q1_draft.py
```

根据已有结果表生成`paper/第一问_正文初稿.md`，并同步更新`paper/论文骨架.md`的第一问章节；不会修改其他问题章节。数字索引保存在`results/q1/station01/q1_evidence_index.csv`，输入文件与稿件哈希、未决项保存在`q1_draft_manifest.json`。

正文含数据口径、晴空模型、月度和日内结果、实际/参考偏差、短时波动、参数敏感性、结论与局限。第一问仍待A、C复核，不表示已经核实真实AC/DC、测量区间、设备参数或异常原因。临时Q1引用编号应在合并全文时统一。

此命令会重新生成第一问文字；人工修改前保存副本，或同步修改生成脚本，避免下次重跑覆盖编辑内容。


## station08第一问重跑（2026-10-13）

从解压后的`data/PVOD`读取，原始数据和station01结果保留。独立稿件见`paper/第一问_station08重跑与对比.md`，结果见`results/q1/station08/`。

```bash
.venv/bin/python src/q1_check_data.py --station station08 --source data/PVOD
.venv/bin/python src/q1_clean_data.py --rules docs/q1_cleaning_rules_station08.json
.venv/bin/python src/q1_reference_power.py --assumptions docs/q1_reference_assumptions_station08.json --source data/PVOD
.venv/bin/python src/q1_characteristics.py --station station08
.venv/bin/python src/build_q1_station08_report.py
```

station08当前规则下无可疑持值段，强辐照零/低功率28点；缺2018-11-11至11-13整3日。两站清洗后各345个完整功率日，共同完整342日。比较仅说明已检查异常与统计特征，不证明后续预测性能更好。昨日ZIP目前不在项目中，旧版默认命令依赖该ZIP；本次命令显式指定解压目录。参考模型的旧`source_zip_sha256`字段在目录输入时记录metadata.csv与对应站点CSV的组合哈希，输入路径另记于`source`。
