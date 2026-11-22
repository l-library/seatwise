# 文档

设计与需求基线，源文件来自作业 2 提交包（课程目录 `SAD/assignment2` 与 `SAD/SRS`）。只收 Markdown、图（png/svg）与 PlantUML 源；提交用的 PDF 与汇报 ppt 不入库。

## 目录

| 路径 | 内容 |
|---|---|
| [SRS.md](SRS.md) | 需求基线 v3：定位、用例 UC-01～UC-18、非功能需求 7.1～7.7、R1～R12 变更日志、附录 A 数据来源 |
| [API.md](API.md) | REST 契约：`/api/v1` 端点总表、错误码、幂等键、状态断言与降级响应，与 Apifox 的 OpenAPI 同源 |
| [DESIGN.md](DESIGN.md) | 设计正文：第 0 章数据证据、架构与 ADR-1～9、领域模型与用例实现、需求变更 R7～R12、优化目标推导、治理杠杆与扩展点、UI 规范、开放问题 |
| [evidence/reproduction-notes.md](evidence/reproduction-notes.md) | 实测数字的统计口径、数据获取方式、复现命令、已知限制 |
| `evidence/*.py`、`evidence/*.json` | 生成第 0 章数字与图表的脚本与结果 |
| [fig/](fig/) | 实测图表 A-1 到 A-5 |
| [uml/](uml/) | 全部图的 PlantUML 源，按图号命名（5-1…5-6、D-1…D-10、A-6…A-10） |
| [svg/](svg/) | 渲染结果，与 puml 同名 |
| [mockups/](mockups/) | S1～S5 界面线框 |

需求条款以 SRS 为准，设计条款以 DESIGN 为准，接口条款以 API 为准；实现跟进时三者同步修改。

## 与提交件的差异

- PDF（`Seatwise-Design-A2.pdf`、`Seatwise-SRS-v3.pdf`、`reproduction-notes.pdf`）与汇报 ppt 不入库，留在课程提交件中。
- `SRS.md` 取与 PDF 同版（含标题页与版本历史）。
- SRS 的线框原本是 `diagrams/1..5.png`，仓库中统一为 `mockups/S1..S5.png`，正文链接已同步；DESIGN 的 `fig/S*` 同样指向 `mockups/`。
- DESIGN 中描述提交包结构的一节改为本文档的目录索引；引用需求条款处链接到 `SRS.md`。
- 证据脚本路径改为 `docs/evidence` 与 `docs/fig`；原始数据不入库。

## 复现实测数字

```bash
cd docs/evidence
python3 -m venv .venv
.venv/bin/pip install pandas pyarrow matplotlib holidays
.venv/bin/python parse_hkust_calendar.py   # 需 hkust_calendar/*.pdf
.venv/bin/python evidence.py               # -> evidence.json
.venv/bin/python make_figures.py           # -> ../fig/*.png
```

数据放在脚本同级：`dataverse-wifi/`（HKUST，DOI `10.14711/dataset/RQXRQB`，CC0 1.0）、`kth/kth_library_occupancy.parquet`（KTH，未声明许可，不随仓库分发）、`hkust_calendar/`（9 份校历 PDF）。三者均已在 `.gitignore` 中。

## 与提交件一致、但内部待确认之处

入库时未改正文，以下问题提交件自身存在，确认后另开 PR 同步：

| 位置 | 问题 |
|---|---|
| 图 D-1（`uml/图D-1-系统上下文与容器图.puml`） | 离线训练环境的数据格仍写“2016–2022 · 约 1420 万条”，与 R7（改用 HKUST + KTH，广外数据降级为申请中）矛盾 |
| 设计 2.1 | 正文说“系统边界内有四个运行时容器”并把离线的 ml 列入；2.2 与图 D-1 的口径是 web + api + worker + MySQL，ml 在离线格子 |
| 图 D-1 | api 的模块列表含 booking / credit / policy / insight / identity / audit，漏了 prediction（正文 2.1 与图 A-6 都有） |
| 图 D-10 | 与正文图 D-5 重复，仅为汇报投影版（reproduction notes 已注明） |
