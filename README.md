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
