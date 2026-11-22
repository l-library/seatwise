# PLAN.md

四周实现计划，把 SRS 4.2 的 M1 到 M5 排进四个周。按角色分工，每周留一个能演示、能验收的断点。

## 起点与终点

仓库现在停在 S0：`docs/` 有需求与设计基线，`backend` 只有一个启动类，`frontend` 只有一个 smoke test，`ml` 只有占位脚本，CI 三端能跑通。第一周的任务是把这里变成能跑的骨架。

四周结束时要能当面演示这些东西：

- 学生选区域、看到带口径的找座概率、三步以内完成预约、签到、离座释放。
- 管理员改政策参数存为新版本，先看模拟报告再决定是否生效，能一键关掉配额。
- 运维关掉全部模型开关，主流程照常走完；再打开，概率与建议回来。
- 压测报告、回测报告、校准曲线、可用性测试记录各一份，贴在各周 PR 里。

## 为什么能压成四周

SRS 4.2 给 M1 到 M5 排了十一周左右。压到四周靠三件事，代价写在最后一节。

- 表结构与 OpenAPI 契约在第一周一次定完，后面只加不改。
- 机制类杠杆（候补、信用优先、峰值轮换、楼层权重）先于预测落地，这是 ADR-8 的分工，预测晚到几天也不阻塞主流程。
- P2 与非目标直接从排期里删掉。

| 周 | 主题 | 对应里程碑 | 周末能演示什么 |
|---|---|---|---|
| 第一周 | 表结构、契约、三端骨架 | M1 前半、S0 收尾 | 四端起得来，接口在 Apifox 里可调 |
| 第二周 | 预约底座、信用、管理后台 | M1、M2 | 100 并发不超卖；扣分与申诉可查；看板出第一版报表 |
| 第三周 | 数据管线与预测 | M3 | 找座页给出带 zone/slot/feature_as_of 的概率 |
| 第四周 | 治理、开关、演练 | M4、M5 | 政策模拟报告 + 关模型演练 |

## 每周固定动作

每周一个 `feat/*` 分支从 `main` 切出，一个 PR 回去，标题就是一条 Conventional Commit。PR 描述按 AGENTS.md 的模板写，验收命令的真实输出贴进「Verification」。CI 三端（frontend、backend、ml）必须绿才请求评审。

周三中途对齐一次，只看两件事：本周退出准则哪条有风险，跨模块接口有没有人偷偷改了签名。周五验收，不通过就顺延到下周并同步删掉下周的等量任务，不靠加班补。

## 第一周：表结构、契约、三端骨架

### 任务

后端 / 预约引擎

- `compose.yaml` 放仓库根，起 MySQL 8，初始化脚本建两个账号：业务写账号，预测只读账号（7.2.5、ADR-4）。
- Flyway 迁移定核心表：`zone`、`seat`、`booking`、`booking_event`、`credit_ledger`、`policy_version`、`waiting_list_entry`、`idempotency`。`booking` 上建唯一索引 `(seat_id, slot_start)`，`idempotency` 上建唯一索引 `(business_key, op, version)`。
- `booking` 模块写出状态机枚举：六状态 + 5.7 的六类 `SettleReason`。状态迁移表落成一张静态 Map，先不接数据库。
- 每条迁移写一句注释说明它对应哪条需求，方便第二周对账。

后端 / AI 与数据

- OpenAPI 首版进 Apifox，覆盖 UC-01/02/03/05/06/07/10/11/12/15/16 的接口，统一错误码与分页结构。预测相关字段按 7.1.4 写全六项：`zone`/`slot`/`feature_as_of`/`model_version`/`band`/`coverage`。
- `prediction` 模块的三张结果表 DDL 一并定下，只给只读账号写权限。
- 在 `ml/` 里把 `main.py` 改成子命令入口（`--task quality|train|backtest`），pytest 进 dev 依赖，写一个空跑通的测试。

前端 / 运维

- 路由与角色守卫：学生、管理员、运维三条壳，登录页先接本地账号（统一认证在演示环境用本地账号替代，SRS 5.1）。
- 座位图、找座页、政策页、看板页四个静态骨架，数据来自写死的 mock，先把布局和 375 px 宽度定下来。
- CI 加 ml job（`uv sync` + `uv run pytest`），把现有 backend/frontend job 的缓存配好。

### 退出准则

- `docker compose up -d mysql` 起得来，两个账号都能连，预测账号往 `booking` 插一条被拒。
- 状态机的合法与非法迁移各有单测，六状态 × 六原因的组合表全覆盖。
- OpenAPI v0.1 在 Apifox 发布，三个人都能拉到。
- 四个页面在 375 px 与 1440 px 下都不溢出。

### 验收命令

```bash
docker compose up -d mysql
cd backend && ./mvnw checkstyle:check && ./mvnw test
cd frontend && pnpm lint && pnpm test && pnpm build
cd ml && uv sync && uv run pytest -q
```

## 第二周：预约底座、信用、管理后台

### 任务

后端 / 预约引擎

- UC-02 预约：事务内先查幂等键，未命中再靠唯一索引插、`SELECT ... FOR UPDATE` 锁单座、状态断言校验信用与配额。冲突返回 3 个备选（ADR-3）。
- UC-03 签到、UC-05 主动离座与到期释放、UC-04 暂离与超时。
- UC-06 超时释放进 `worker`：每批 ≤ 200 条，逐条条件更新，幂等键 `(预约号, NO_SHOW, policy_version)`，已签到的跳过，中断可续跑。
- UC-18 候补队列的入队与出队逻辑，先不接通知。

后端 / AI 与数据

- `credit` 模块：账本只追加，`score` 由账本派生，5 条计分规则可配；申诉工单的表单与状态流转（UC-07/13）。
- `policy` 模块：8 项参数、取值域校验、版本表与唯一生效指针、回滚只移动指针（ADR-5、UC-12）。
- 看板接口读分钟级物化汇总表，三张报表（利用率、浪费、违规分布）能导出 CSV（7.4.4、UC-11）。

前端 / 运维

- 预约三步流程打通：选时段看座、确认、提交；签到与离座各 ≤ 2 次点击（7.1.2）。
- 管理端：区域与座位维护、政策参数表单、看板首版、申诉处理页。
- 每个系统决定都能展开看原因：扣分依据、拒绝理由、释放来源（7.1.3）。

### 退出准则

- 100 并发抢同区域最后一座，重复分配 0 例。
- 同一批释放事件重放 100 次，账本条目数不变。
- 预约路径 ≤ 3 步、≤ 5 次点击，签到 ≤ 2 次点击。
- 5 条计分规则可配，3 张报表可导出，申诉闭环且留痕。
- 常规接口 p95 ≤ 300 ms、p99 ≤ 800 ms（7.4.1）。

### 验收命令

```bash
cd backend && ./mvnw checkstyle:check && ./mvnw test -Dtest='BookingConcurrencyTest,IdempotencyTest,LatencyTest' && ./mvnw test
cd frontend && pnpm lint && pnpm test && pnpm build
```

## 第三周：数据管线与预测

### 任务

后端 / AI 与数据

- HKUST 清洗（需求侧）与 KTH 清洗（占用侧），六维闸门各写一条质量记录：维度、影响行数、处置（7.4.6）。楼层值与去重总量分开存，不相加。
- B1 停留时长、B2 爽约、B3 需求三个模型；D1 占用轨迹、D2 找座概率。B2 的训练标签来自假设区间，写在配置文件里，界面上要能说明这一点。
- 固定时间切分回测，产出 MAE 对照、校准曲线、coverage 统计，报告进 PR。
- 导出 ONNX 工件与特征契约，Java 侧用 ONNX Runtime 打分，两边对同一批输入的误差 < 1e-3（ADR-2）。
- `prediction` 模块只用只读账号：读业务视图，写三张结果表，批量预计算每 15 分钟一批、单批 ≤ 60 秒。

前端 / 运维

- UC-01 找座页：概率必须带区域、时段、数据时间、模型版本、分档、覆盖率六项，缺一项就别渲染数字（7.1.4）。数据不足显示「暂无可靠预测」。
- UC-09 错峰建议：≤ 3 个候选，附依据，可接受、忽略、关闭。
- 运维页：模型版本列表、回测指标、一键切换 `model_version` 指针。

### 退出准则

- 日粒度需求预测相对 persistence 提升 ≥ 20%。
- 30 分钟前瞻不劣于 persistence 10%，分档校准偏差 ≤ 5 pp，coverage ≥ 90%（R8）。
- 用预测账号写 `booking`、`credit_ledger`、`policy_version` 全部被拒（7.7）。
- 预测查询 p95 ≤ 150 ms（7.4.2）。
- 同一输入下 Java 与 Python 打分误差 < 1e-3。

### 验收命令

```bash
cd ml && uv sync && uv run python main.py --task quality && uv run python main.py --task backtest && uv run pytest -q
cd backend && ./mvnw test -Dtest='PredictionParityTest,PredictionReadOnlyTest'
cd frontend && pnpm test && pnpm build
```

## 第四周：治理、开关与演练

### 任务

后端 / AI 与数据

- D3 期望浪费、C1 配额建议（只出建议，人采纳后生效）、UC-14 政策模拟：重放历史事件，输出利用率、浪费、找座失败率、拒绝率四列对比，结果只写 `simulation_report`。
- 三个开关落地：`policy_version`、`model_version`、`feature_flag`。任一关闭时页面退回规则版，主流程可完成（7.3.4）。
- 漂移检测：滚动 MAE 连续 5 天超阈、楼层份额位移、校历端口失联 7 天，任一条告警并可回滚（7.3.6、R11）。
- 产出「宽限期 15 分钟改 20 分钟」的模拟报告一份。

前端 / 运维

- 模拟对比表与置信说明页，按钮写「保存为新版本」，不写「应用」。
- WCAG 2.1 AA 自查：键盘可达、对比度 ≥ 4.5:1、图表不只靠颜色（7.1.5）。
- 压测与演练脚本：关模型、关 LLM、断校历端口三种情形各跑一遍。

### 退出准则

- 模拟报告里 15 分钟列与 20 分钟列并排，带置信说明。
- 配额上限一键关闭，关掉后预约仍可用。
- 关闭全部模型与 LLM，预约、签到、释放、计分、报表全部可完成。
- 政策回滚 ≤ 1 分钟、模型回滚 ≤ 10 分钟，回滚不丢数据（7.3.5）。
- 20 req/s 下 p95 ≤ 300 ms、p99 ≤ 800 ms；5 人可用性测试成功率 ≥ 80%。
- 演示脚本从登录走到模拟报告，全程不手改数据库。

### 验收命令

```bash
cd backend && ./mvnw checkstyle:check && ./mvnw test -Dtest='DegradeTest,RollbackTest,LatencyTest' && ./mvnw test && ./mvnw package
cd ml && uv run python main.py --task simulate --from-policy 15 --to-policy 20
cd frontend && pnpm lint && pnpm test && pnpm build
```

## 排期里的取舍

四周装不下十一周的东西，下面这些明确不进排期，免得中途临时插入：

- L1 自然语言适配与 A1 异常检测不实现，只在第四周的开关演练里留占位（SRS 4.1 的 P2）。
- 归因只做上线前后对比，不做 DID 的平行趋势检验，结论标注为方向性。
- 灰度发布用手工切换 `model_version` 指针，不写自动灰度。
- 通知走站内消息，不接短信与邮件。
- 多校区、支付、原生 App、对接真实校方系统，按 4.1 的非目标不做。

如果第三周的 G2 或 G3 闸门没过，第四周不硬推：找座页退回分档显示，配额建议与政策模拟降级为离线报告，演示脚本同时保留规则版路径。这条退路比赶一遍模型重训更稳。

## 已知风险

两份数据都不是本校数据，外推结论一律标注来源（ADR-6）。缺预约与签到记录，爽约率与停留时长只能取自假设区间，B2 报告要写这一条。θ 只能靠自建日志标定，第四周前标不出来就 G4 不过、超额准入不上线，这属于预期内的结果，不算延期。
