# Attachment notes: evidence and reproduction

本目录存放设计正文第 0 章引用的实测数字与生成脚本；图表与图源在上级目录，用于复核，不参与系统运行。

## 文件

| 文件 | 内容 |
|---|---|
| `evidence.json` | 第 0 章引用的全部数字：六维质量指标、基线 MAE、校历解释力、漂移指标、稀缺度 |
| `../fig/` | 实测图表 A-1 到 A-5，与设计正文同源 |
| `../uml/` | 全部图的 PlantUML 源，按图号命名（`图A-6-扩展点与端口.puml`、`图D-1-系统上下文与容器图.puml`、`图5-1-用例图.puml`） |
| `../svg/` | 对应的渲染结果，同名 `.svg` |
| `evidence.py` | 从原始数据计算 `evidence.json` |
| `make_figures.py` | 由 `evidence.json` 渲染 `../fig/` |
| `parse_hkust_calendar.py` | 解析 9 份校历 PDF，输出学期与考试期区间 |
| `hkust_calendar_terms.json` | 上述解析结果 |

图号与主文档一致：`5-x` 属需求基线，`D-x` 属设计模型，`A-x` 属本轮新增（扩展点、数据管线、
用户流程、目标推导）。`D-10` 是为汇报做的核心类图投影版，与正文图 D-5 重复，未收入正文，此处一并归档。

## 原始数据

两份数据均为公开数据，未随仓库分发，按下列方式获取后可完整复算。

| 数据 | 用途 | 获取方式 | 许可 |
|---|---|---|---|
| Wi-Fi Connection in HKUST Library | 需求侧主数据（2014-02 到 2022-05，98 个月，2,981 天） | DataSpace@HKUST，DOI `10.14711/dataset/RQXRQB` | CC0 1.0 |
| real-time-library-occupancy（KTH 图书馆） | 占用侧验证集（2024-12 到 2025-07，231 天，6 区域） | Hugging Face `davnas/real-time-library-occupancy` | 未声明，仅课程内方法验证，不随包分发 |
| HKUST 校历 | 学期、考试期、假期区间 | `registry.hkust.edu.hk/academic-calendar` | 公开页面 |

## 复现步骤

数据下载后放在本目录：`dataverse-wifi/`、`kth/`、`hkust_calendar/`（三者均不入库）。

```
python3 -m venv .venv
.venv/bin/pip install pandas pyarrow matplotlib holidays
.venv/bin/python parse_hkust_calendar.py     # 校历 PDF -> hkust_calendar_terms.json
.venv/bin/python evidence.py                 # -> evidence.json
.venv/bin/python make_figures.py             # -> ../fig/*.png
```

`evidence.py` 顶部的 `FIT_START` / `FIT_END` 定义拟合窗口（2014-02 到 2019-06），
2020 年及以后的区间只用于漂移检验，不进入拟合。

## 已知限制

1. 两份数据都不是本校数据。改善目标的外推需要 Part III 以自建系统日志复核一次。
2. 拿不到公开的座位预约与签到记录，爽约率与停留时长用假设区间，可迁移比例 θ 是唯一未标定参数。
3. WiFi 人数是设备去重估算（连接数除人数 = 7.79），不是座位占用人数，只做需求侧口径。
4. “All-Floors” 是跨楼层去重值，楼层值分别计数，两者不得相加（只有 3.15% 的日期相等）。
