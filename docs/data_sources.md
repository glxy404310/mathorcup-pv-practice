# 当前数据来源与使用口径

更新：2026-10-14。主分析为station08，station01仅保留第一问共同完整日对比。清理未修改保留的原始CSV、metadata.csv或清洗表内容。

## 本地文件

| 文件 | 用途 |
| --- | --- |
| `data/PVOD/station08.csv` | 主站实测功率、现场气象、NWP字段 |
| `data/PVOD/station01.csv` | 第一问对照站原始数据 |
| `data/PVOD/metadata.csv` | 原始10站元数据，保留完整文件以保持哈希一致 |
| `data/processed/station08_q1_clean.csv` | 主分析输入，原始列与清洗列并存 |
| `data/processed/station01_q1_clean.csv` | 第一问对照输入 |

数据来自项目此前下载的PVOD v1.0解压文件；原ZIP现不在项目内。历史记录的下载日期为2026-10-12，未独立核验下载日志；实际文件下载直链、数据文件许可和发布修订版仍待补记。仓库代码许可不等于数据文件许可。

## station08事实与边界

- 原始时间按UTC读取，转为北京时间；2018-07-01至2019-06-13，33120条、345个完整96点观测日。2018-11-11至13日缺测，不补零。时间跨度不足完整一年。
- 功率按MW，元数据容量20000 kW换算为20 MW。组件78042块×265 Wp合计20.68113 MWp；交流限制和评分开机容量暂用20 MW，二者均不能据此视作已核实。
- 经纬度113.89999°E、36.70761°N，朝南33°；海拔、逆变器总台数、功率AC/DC和采样瞬时/区间均值口径尚未核实。
- `nwp_*`为预报字段；`lmd_*`为现场气象。CSV未提供NWP发行时刻、版本、实际提前量、邻域格点坐标与空间分辨率。不能证明本次七天目标上的NWP均已在起报时可得，也不能把其他电站坐标当作预报格点。
- 四个测试周各672条，共2688条，白昼评分1346条。具体协议、指标、向前与补充离线实验区分见 `paper/final/论文终稿.md` 第六至九章。
- station08当前清洗规则没有修改字段值；这不等于已经排除所有物理异常。station01存在多字段持值，保留相关日志和持值段表以支持对比。

终稿整理于2026-10-16核对了作者仓库的论文引用记录及软件官方资料。数据发布许可、本地修订版本、NWP发行信息仍未独立核实。

## 来源线索

1. Yao, T., Wang, J., Wu, H., et al. *A photovoltaic power output dataset: Multi-source photovoltaic power output dataset with Python toolkit*. Solar Energy, 2021, 230:122–130. [DOI:10.1016/j.solener.2021.09.050](https://doi.org/10.1016/j.solener.2021.09.050)。
2. [PVODataset作者仓库](https://github.com/yaotc/PVODataset)：字段说明、工具代码与作者引用要求。
3. PVOD v1.0，Science Data Bank，2021。[数据DOI:10.11922/sciencedb.01094](https://doi.org/10.11922/sciencedb.01094)。
4. [数据发布页](https://www.scidb.cn/en/detail?dataSetId=f8f3d7af144f441795c5781497e56b62)：用于补齐具体发布版本及数据许可。
