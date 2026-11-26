# Seatwise REST API 契约

接口契约的设计源。条款号指向 [SRS.md](SRS.md) 与 [DESIGN.md](DESIGN.md)；机器可读真源为 [openapi.yaml](openapi.yaml)（Apifox 由它导入同步，前端类型由它生成），实现与 `docs/openapi.yaml` 跟本文同步改，同一 PR 落地；从 Apifox 重导出后需先跑 `python3 scripts/normalize-openapi.py` 归一化，再跑 `pnpm gen:api`。

排期与模块归属见 [../PLAN.md](../PLAN.md)：身份与预约接口在第一、二周，预测在第三周，政策模拟与开关在第四周。

## 1 通用约定

### 1.1 基址与版本

- 基址 `/api/v1`，只走 HTTPS。
- 破坏性变更发 `/api/v2`，旧版本保留一个学期。新增可选字段、新增枚举值不算破坏性变更，客户端遇到未知枚举按「其他」处理。

### 1.2 认证与角色

`Authorization: Bearer <access_token>`，令牌有效期 8 小时，失效返回 401，客户端重新登录。

| 角色 | 代号 | 能做什么 |
|---|---|---|
| 学生 | `STUDENT` | 找座、预约、签到、暂离、释放、候补、查看本人信用与申诉 |
| 场馆管理员 | `ADMIN` | 区域与座位维护、政策版本、申诉处理、看板与报表、强制释放、政策模拟 |
| 运维 | `OPERATOR` | 模型版本、漂移告警、三元开关、降级演练；不碰业务数据 |

越权返回 403 并写审计（7.2.1）。路径里不出现用户 id，一律取当前会话身份，这是 7.6.4「不得输出他人预约」在契约层的落点。

### 1.3 时间与时段

- 时间一律 RFC 3339 带偏移，如 `2026-11-23T10:00:00+08:00`；日期用 `2026-11-23`。
- `slot_start` 对齐 30 分钟，`duration_minutes` 为 30 的整数倍。
- 服务端以 `Asia/Shanghai` 计算，客户端时区不同不影响结果。

### 1.4 分页与筛选

`?page=0&size=20`，`size` 上限 100。列表响应统一为：

```json
{ "items": [], "page": 0, "size": 20, "total": 137 }
```

时间区间用 `from` 与 `to`（含 `from`，不含 `to`）。多余的未知查询参数忽略，未知枚举值返回 400。

### 1.5 错误格式

错误体是 `application/problem+json`（RFC 9457），在标准字段上增加 `code` 与 `trace_id`：

```json
{
  "type": "https://seatwise.local/problems/seat-taken",
  "title": "该座位刚被占用",
  "status": 409,
  "code": "SEAT_TAKEN",
  "detail": "座位 st_e2_017 在 2026-11-23T10:00:00+08:00 起 120 分钟内已被预约",
  "trace_id": "4b1c9f2e8a7d"
}
```

`detail` 给人看，`code` 给程序判断，两者都要有。错误码表：

| code | HTTP | 触发 | 额外字段 |
|---|---|---|---|
| `VALIDATION_FAILED` | 400 | 字段缺失、格式错、未知枚举 | `errors[]`：`{field, message}` |
| `POLICY_PARAM_OUT_OF_RANGE` | 400 | 政策参数越界（5～30 分钟这类取值域） | `errors[]` |
| `CONFIRMATION_REQUIRED` | 400 | 高风险变更没带二次确认 | — |
| `UNAUTHENTICATED` | 401 | 无令牌或令牌过期 | — |
| `FORBIDDEN` | 403 | 角色不够、访问他人资源 | — |
| `NOT_FOUND` | 404 | 资源不存在 | — |
| `SEAT_TAKEN` | 409 | 唯一索引冲突 | `alternatives[]`，≤ 3 条 |
| `BOOKING_STATE_CONFLICT` | 409 | 当前状态不允许该迁移 | `current_state` |
| `RULE_VIOLATION` | 409 | 信用、时长、配额、闭馆等业务规则 | `violations[]`：`{code, message}` |
| `SEAT_CODE_INVALID` | 409 | 签到码签名不符或过期 | — |
| `WAITLIST_FULL` | 409 | 候补队列已满 | — |
| `APPEAL_ALREADY_OPEN` | 409 | 同一账本条目已有未结申诉 | `appeal_id` |
| `SIMULATION_RUNNING` | 409 | 同一参数组合的模拟正在跑 | `simulation_id` |
| `ACCOUNT_LOCKED` | 423 | 连续登录失败被锁定 | `retry_after_seconds` |
| `RATE_LIMITED` | 429 | 触发限流 | `Retry-After` 响应头 |
| `INTERNAL` | 500 | 未预期错误 | — |
| `SERVICE_UNAVAILABLE` | 503 | 数据库不可用、工件缺失 | — |

`RULE_VIOLATION` 的 `violations[].code` 取 `CREDIT_TOO_LOW`、`DURATION_EXCEEDED`、`DAILY_LIMIT_EXCEEDED`、`QUOTA_FULL`、`SEAT_NOT_AVAILABLE`、`FEATURE_DISABLED`。

### 1.6 幂等与重放

四个写操作类（预约、签到、释放、扣分）全部幂等（7.3.1）。客户端每次写请求带 `Idempotency-Key: <UUID v7>`；服务端以 `(业务键, op, version)` 落唯一索引，`Idempotency-Key` 只用于客户端重试去重。

重放不发新副作用，返回首次的状态码与响应体，并加响应头 `Idempotent-Replay: true`。

| 端点 | 业务键 | op | version |
|---|---|---|---|
| `POST /bookings` | `(user_id, seat_id, slot_start)` | `CREATE` | `policy_version` |
| `POST /bookings/{booking_id}/check-in` | `(booking_id)` | `CHECK_IN` | `policy_version` |
| `POST /bookings/{booking_id}/release`，以及 `cancel`、`away`、`return` | `(booking_id, reason)` | `RELEASE` | `policy_version` |
| `POST /admin/bookings/{booking_id}/force-release` | `(booking_id, FORCED_RELEASE)` | `RELEASE` | `policy_version` |
| `worker` 的超时释放与扣分 | `(booking_id, NO_SHOW)` | `CREDIT` | `policy_version` |
| `POST /policies/{version}/activate` | `(policy_version)` | `ACTIVATE` | — |
| `POST /waitlist/{entry_id}/confirm` | `(entry_id)` | `CONFIRM` | `policy_version` |

`POST /bookings` 的 409 `SEAT_TAKEN` 不缓存为幂等结果：冲突不是终态，客户端可以马上换座位重试。

### 1.7 限流

| 端点 | 限额 | 说明 |
|---|---|---|
| `POST /auth/login` | 5 次/分钟/IP，连续失败 5 次锁 15 分钟 | 7.2.1 |
| `POST /bookings`、`POST /bookings/{id}/check-in` | 10 次/分钟/（用户 + IP） | 7.2.2，防脚本抢座 |
| 预测查询（`find-seat-probability`、`alternatives`、`occupancy-timeline`） | 60 次/分钟/用户 | 批量预计算兜底 |
| 其余 | 120 次/分钟/用户 | — |

### 1.8 降级时的响应

关闭模型或端口后接口不报 5xx，改用可判定的空值，页面据此隐藏数字（7.3.4、DESIGN 8.7）。

| 关闭项 | 受影响端点 | 响应 |
|---|---|---|
| 预测全关（`feature_flag.prediction=false`） | 三个预测端点、看板的预测列 | 200，`available: false`，`insufficient_reason: "PREDICTION_DISABLED"` |
| 校历端口失联 ≥ 7 天 | 同上 | `available: false`，`insufficient_reason: "COVERAGE_INSUFFICIENT"` |
| 工件回滚中 | 同上 | `available: false`，`insufficient_reason: "MODEL_UNAVAILABLE"` |
| 候补关闭 | `POST /waitlist` | 409 `RULE_VIOLATION`，`violations[0].code = FEATURE_DISABLED` |
| 超额准入关闭 | `GET /zones/{id}/seats` 的 `quota` 字段、`POST /bookings` | 配额按 1.0 返回，预约不再因超发被拒 |

`available: false` 时六个口径字段照常返回，`probability` 为 `null`。

## 2 端点总表

| 方法 | 路径 | 角色 | 用例 | 周 |
|---|---|---|---|---|
| POST | `/auth/login` | 公开 | UC-16 | 1 |
| POST | `/auth/logout` | 全部 | UC-16 | 1 |
| GET | `/auth/me` | 全部 | UC-16 | 1 |
| GET | `/zones` | 学生、管理员 | UC-01 | 1 |
| GET | `/zones/{zone_id}/seats` | 学生 | UC-01/02 | 2 |
| GET | `/zones/{zone_id}/find-seat-probability` | 学生 | UC-01 | 3 |
| GET | `/zones/{zone_id}/alternatives` | 学生 | UC-09 | 3 |
| GET | `/zones/{zone_id}/occupancy-timeline` | 学生 | UC-01 | 3 |
| POST | `/bookings` | 学生 | UC-02 | 2 |
| GET | `/bookings` | 学生 | UC-08 | 2 |
| GET | `/bookings/{booking_id}` | 学生（本人）、管理员 | UC-03/08 | 2 |
| POST | `/bookings/{booking_id}/check-in` | 学生 | UC-03 | 2 |
| POST | `/bookings/{booking_id}/away` | 学生 | UC-04 | 2 |
| POST | `/bookings/{booking_id}/return` | 学生 | UC-04 | 2 |
| POST | `/bookings/{booking_id}/release` | 学生 | UC-05 | 2 |
| POST | `/bookings/{booking_id}/cancel` | 学生 | UC-02 | 2 |
| POST | `/waitlist` | 学生 | UC-18 | 2 |
| GET | `/waitlist` | 学生 | UC-18 | 2 |
| DELETE | `/waitlist/{entry_id}` | 学生 | UC-18 | 2 |
| POST | `/waitlist/{entry_id}/confirm` | 学生 | UC-18 | 2 |
| GET | `/credit/account` | 学生 | UC-07 | 2 |
| GET | `/credit/ledger` | 学生 | UC-07 | 2 |
| GET | `/credit/rules` | 学生、管理员 | UC-07 | 2 |
| POST | `/appeals` | 学生 | UC-07 | 2 |
| GET | `/appeals` | 学生 | UC-07 | 2 |
| GET | `/appeals/{appeal_id}` | 学生（本人）、管理员 | UC-07/13 | 2 |
| GET | `/notifications` | 学生 | UC-03/18 | 4 |
| POST | `/notifications/{notification_id}/read` | 学生 | — | 4 |
| GET | `/policies/current` | 全部 | UC-12 | 2 |
| GET | `/policies` | 管理员、运维 | UC-12 | 2 |
| GET | `/policies/{version}` | 管理员、运维 | UC-12 | 2 |
| POST | `/policies` | 管理员 | UC-12 | 2 |
| POST | `/policies/{version}/activate` | 管理员 | UC-12 | 2 |
| GET | `/admin/overview` | 管理员 | UC-11 | 2 |
| GET | `/admin/reports/{report_key}` | 管理员 | UC-11 | 2 |
| GET | `/admin/bookings` | 管理员 | UC-10/11 | 2 |
| POST | `/admin/bookings/{booking_id}/force-release` | 管理员 | UC-10 | 2 |
| POST | `/admin/zones` | 管理员 | UC-10 | 2 |
| PATCH | `/admin/zones/{zone_id}` | 管理员 | UC-10 | 2 |
| POST | `/admin/zones/{zone_id}/seats/import` | 管理员 | UC-10 | 2 |
| PATCH | `/admin/seats/{seat_id}` | 管理员 | UC-10 | 2 |
| POST | `/admin/zones/{zone_id}/closures` | 管理员 | UC-10 | 2 |
| GET | `/admin/appeals` | 管理员 | UC-13 | 2 |
| POST | `/admin/appeals/{appeal_id}/decision` | 管理员 | UC-13 | 2 |
| POST | `/admin/simulations` | 管理员 | UC-14 | 4 |
| GET | `/admin/simulations/{simulation_id}` | 管理员 | UC-14 | 4 |
| GET | `/admin/attribution` | 管理员 | UC-14 | 4 |
| GET | `/admin/models` | 运维、管理员 | UC-15 | 3 |
| POST | `/admin/models/{model_version}/activate` | 运维 | UC-15 | 3 |
| GET | `/admin/drift` | 运维 | UC-15 | 4 |
| GET | `/admin/flags` | 运维 | UC-15 | 4 |
| PATCH | `/admin/flags` | 运维 | UC-15 | 4 |
| GET | `/health` | 公开 | — | 1 |

## 3 端点详情

### 3.1 身份

`POST /auth/login`，请求 `{"username": "u2023011", "password": "..."}`，返回 200：

```json
{
  "access_token": "eyJhbGciOi...",
  "expires_at": "2026-11-23T18:00:00+08:00",
  "role": "STUDENT",
  "user": { "id": "us_1042", "display_name": "李同学", "credit_score": 92 }
}
```

演示环境用本地账号，`IdentityProviderPort` 后续换 CAS 或 OAuth（DESIGN 7.4）。`GET /auth/me` 返回 `user` 与 `role`。

### 3.2 找座与预测

`GET /zones?date=2026-11-23` 返回区域列表与当日开放时段、座位总数、当前可用数。

`GET /zones/{zone_id}/seats?slot_start=2026-11-23T10:00:00%2B08:00&duration_minutes=120` 返回座位图。只回座位编号与状态，不回他人预约信息：

```json
{
  "zone": { "id": "zn_east", "name": "东区" },
  "slot": { "start": "2026-11-23T10:00:00+08:00", "end": "2026-11-23T12:00:00+08:00" },
  "quota": 1.0,
  "seats": [
    { "id": "st_e2_017", "label": "E2-17", "status": "AVAILABLE" },
    { "id": "st_e2_018", "label": "E2-18", "status": "BOOKED" },
    { "id": "st_e2_019", "label": "E2-19", "status": "CLOSED" }
  ]
}
```

`status` 取 `AVAILABLE`、`BOOKED`（含暂离）、`CLOSED`（闭馆或停用）。超额准入放开时 `quota` 大于 1.0，座位状态不变。

`GET /zones/{zone_id}/find-seat-probability?slot_start=...&duration_minutes=120`，D2 的输出必须带齐 7.1.4 的六项：

```json
{
  "zone": { "id": "zn_east", "name": "东区" },
  "slot": { "start": "2026-11-23T10:00:00+08:00", "end": "2026-11-23T12:00:00+08:00" },
  "feature_as_of": "2026-11-23T09:45:00+08:00",
  "model_version": "d2-2026w47",
  "band": "HIGH",
  "coverage": 0.94,
  "available": true,
  "probability": 0.71,
  "proxy_metric": true,
  "insufficient_reason": null
}
```

`band` 取 `LOW`、`MEDIUM`、`HIGH`，G2 未通过时只给 `band`，`probability` 为 `null`。`proxy_metric: true` 表示这个概率吃的特征里有 WiFi 或门禁推断值（R12），界面要标「估算」。

`GET /zones/{zone_id}/alternatives?slot_start=...&duration_minutes=120&limit=3` 返回 ≤ 3 个候选区域，每个带概率、步行距离与一句依据（C2）：

```json
{
  "items": [
    {
      "zone": { "id": "zn_north", "name": "北区" },
      "slot": { "start": "2026-11-23T10:00:00+08:00", "end": "2026-11-23T12:00:00+08:00" },
      "feature_as_of": "2026-11-23T09:45:00+08:00",
      "model_version": "d2-2026w47",
      "band": "MEDIUM",
      "coverage": 0.91,
      "available": true,
      "probability": 0.55,
      "proxy_metric": true,
      "walking_minutes": 6,
      "reason": "北区同一时段历史占用低 12 个百分点"
    }
  ]
}
```

`GET /zones/{zone_id}/occupancy-timeline?from=...&to=...` 返回 30 分钟粒度的 D1 占用轨迹，供座位图做热度底色，字段同上加 `series[]`。

### 3.3 预约与使用

`POST /bookings`，`Idempotency-Key` 必填：

```json
{ "seat_id": "st_e2_017", "slot_start": "2026-11-23T10:00:00+08:00", "duration_minutes": 120 }
```

201 加 `Location: /api/v1/bookings/bkg_7f3a91`：

```json
{
  "id": "bkg_7f3a91",
  "zone": { "id": "zn_east", "name": "东区" },
  "seat": { "id": "st_e2_017", "label": "E2-17" },
  "slot": { "start": "2026-11-23T10:00:00+08:00", "end": "2026-11-23T12:00:00+08:00" },
  "state": "PENDING_CHECKIN",
  "settle_reason": null,
  "grace_period_minutes": 15,
  "check_in_deadline": "2026-11-23T10:15:00+08:00",
  "policy_version": 12,
  "credit_delta": 0,
  "created_at": "2026-11-23T09:41:12+08:00",
  "actions": { "can_check_in": true, "can_away": false, "can_release": false, "can_cancel": true }
}
```

冲突走 409 `SEAT_TAKEN`，`alternatives[]` 直接给 3 个备选，服务端已经换过座位校验，客户端不用重算。配额已满走 409 `RULE_VIOLATION`，`QUOTA_FULL`，响应加 `suggested_slots[]`（同日替代时段，最多 3 条）。

`actions` 由状态机推导，客户端不自己判断状态能不能点。签到、暂离、返回、释放、取消都返回同一个预约对象，避免客户端拼装；变化的只有 `state`、`settle_reason`、时间戳与 `actions`。

| 端点 | 允许的当前状态 | 目标状态 | settle_reason |
|---|---|---|---|
| `check-in` | `PENDING_CHECKIN` | `IN_USE` | — |
| `away` | `IN_USE` | `AWAY` | — |
| `return` | `AWAY` | `IN_USE` | — |
| `release` | `IN_USE`、`AWAY` | `COMPLETED` | `CHECK_OUT` |
| `cancel` | `PENDING_CHECKIN` | `CANCELLED` | `USER_CANCEL` |
| `/admin/bookings/{id}/force-release` | `PENDING_CHECKIN`、`IN_USE`、`AWAY` | `COMPLETED` | `FORCED_RELEASE` |

状态不符返回 409 `BOOKING_STATE_CONFLICT`，带 `current_state`。签到请求体是 `{"seat_code": "eyJ...sig"}`，服务端校验签名、有效期与座位一致，不符返回 409 `SEAT_CODE_INVALID`（7.2.2）。管理员强制释放要带 `{"reason": "设备维修", "confirm": true}`，理由与操作者进审计。

`worker` 自己产生的两条迁移没有对外端点：`PENDING_CHECKIN → NO_SHOW`（`NO_SHOW`，UC-06）与 `IN_USE/AWAY → COMPLETED`（`SESSION_END` 或 `AWAY_TIMEOUT`）。

### 3.4 候补

`POST /waitlist`，请求 `{"zone_id": "zn_east", "slot_start": "...", "duration_minutes": 120}`，201 返回 `{id, zone, slot, priority, enqueued_at, status, expires_at}`。`status` 取 `WAITING`、`OFFERED`、`CONFIRMED`、`EXPIRED`、`CANCELLED`。候补不锁座，`priority` 由 `credit_priority_tiers` 与入队时间决定，不接受手工插队。

座位释放时服务端取队首生成待确认预约，`POST /waitlist/{entry_id}/confirm` 在 `expires_at` 之前调用才有效；超时未确认，服务端顺延下一位，再调返回 409 `BOOKING_STATE_CONFLICT`。

### 3.5 信用与申诉

`GET /credit/account` 返回派生值，没有写入口（7.2.6）：

```json
{ "score": 92, "tier": "NORMAL", "window_days": 180, "next_tier_score": 95, "updated_at": "2026-11-22T20:00:00+08:00" }
```

`GET /credit/ledger?page=0&size=20`：

```json
{
  "items": [
    {
      "id": "cle_5531",
      "occurred_at": "2026-11-19T10:16:00+08:00",
      "rule_code": "R_NO_SHOW",
      "reason_code": "NO_SHOW",
      "delta": -5,
      "score_after": 87,
      "booking_id": "bkg_6c20d4",
      "policy_version": 12,
      "description": "超过宽限期 15 分钟未签到",
      "reversal_of": null,
      "appealable": true
    }
  ],
  "page": 0, "size": 20, "total": 31
}
```

申诉只针对账本条目：`POST /appeals` 请求 `{"ledger_entry_id": "cle_5531", "reason_type": "SYSTEM_ERROR", "description": "..."}`，`reason_type` 取 `SYSTEM_ERROR`、`EXEMPTION`、`OTHER`。201 返回工单，同一账本条目已有未结申诉时返回 409 `APPEAL_ALREADY_OPEN`。

管理员裁决 `POST /admin/appeals/{appeal_id}/decision`，请求 `{"decision": "REVERSE", "reply": "...", "confirm": true}`。`REVERSE` 追加一条冲正账本条目，不修改原条目；`REJECT` 只关闭工单。两者都留操作者与时间。

### 3.6 政策

`GET /policies/current` 返回生效版本。学生只看到 `public_params`（宽限期、单次时长上限），管理员与运维看到 8 项全量参数：

```json
{
  "policy_version": 12,
  "effective_at": "2026-11-20T00:00:00+08:00",
  "effective_by": "us_2001",
  "params": {
    "grace_period_minutes": 15,
    "max_booking_minutes": { "single": 240, "daily": 480 },
    "credit_threshold": 60,
    "oversell_ratio_max": 0.05,
    "waitlist_capacity_per_slot": 20,
    "waitlist_confirm_timeout_minutes": 10,
    "credit_priority_tiers": [
      { "min_score": 95, "advance_booking_hours": 72 },
      { "min_score": 85, "advance_booking_hours": 48 }
    ],
    "peak_rotation_interval_minutes": 120
  },
  "public_params": { "grace_period_minutes": 15, "max_booking_minutes": { "single": 240, "daily": 480 } }
}
```

`POST /policies` 建草稿版本，请求 `{"params": {...}, "reason": "..."}`，`params` 可以只带要改的键，其余继承当前生效版本，201 返回 `{"policy_version": 13, "status": "DRAFT"}`，此时不生效。

`POST /policies/{version}/activate` 才是生效动作，请求 `{"reason": "...", "confirm": true}`。缺 `confirm` 返回 400 `CONFIRMATION_REQUIRED`（7.2.3），成功返回 `{"policy_version": 13, "status": "ACTIVE", "effective_at": "..."}`。回滚就是把旧版本再 activate 一次，生效指针移动，历史版本只读（ADR-5）。`GET /policies/{version}` 返回该版本的参数与元数据。

### 3.7 管理端

`GET /admin/overview?zone_id=zn_east&from=...&to=...` 返回看板卡片。每个指标带单位、口径版本与 `coverage`，口径与 BG1–BG5 一致（7.4.4）：

```json
{
  "window": { "from": "2026-11-16", "to": "2026-11-23" },
  "metric_version": "m1",
  "metrics": [
    { "key": "effective_utilization", "value": 0.712, "unit": "ratio", "baseline": 0.681, "coverage": 0.96 },
    { "key": "waste_seat_minutes", "value": 41230, "unit": "seat_minutes", "baseline": 58900, "coverage": 0.96 },
    { "key": "find_seat_failure_rate", "value": 0.0099, "unit": "ratio", "baseline": 0.0129, "coverage": 0.88 },
    { "key": "floor_imbalance", "value": 4.0, "unit": "ratio", "baseline": 4.1, "coverage": 0.96 }
  ]
}
```

`GET /admin/reports/{report_key}?from=...&to=...&zone_id=...&group_by=day&format=json|csv`，`report_key` 取 `utilization`、`waste`、`violation`。`format=csv` 返回 `text/csv` 与 `Content-Disposition` 文件名，导出行数与生成时间写进响应头 `X-Row-Count`、`X-Generated-At`。

`GET /admin/bookings` 支持 `state`、`zone_id`、`from`、`to`、`page`、`size`，用于处置与核对。区域与座位维护按 REST 常规：

- `POST /admin/zones`、`PATCH /admin/zones/{zone_id}`：名称、容量、开放时段、状态。
- `POST /admin/zones/{zone_id}/seats/import`：`multipart/form-data` 上传 CSV，返回 `{"imported": 120, "skipped": 3, "errors": [{"line": 41, "message": "重复座位号"}]}`。
- `PATCH /admin/seats/{seat_id}`：`{"status": "DISABLED", "reason": "..."}`。
- `POST /admin/zones/{zone_id}/closures`：`{"from": "...", "to": "...", "reason": "..."}` 临时闭馆，闭馆期请求预约返回 409 `RULE_VIOLATION`，`SEAT_NOT_AVAILABLE`。

所有管理端写操作要求 `reason`，写审计（7.5.5）。

### 3.8 政策模拟

`POST /admin/simulations` 异步执行，请求：

```json
{
  "candidate_params": { "grace_period_minutes": 20 },
  "baseline": "current",
  "window": { "from": "2026-10-01", "to": "2026-10-29" }
}
```

只传要改的参数，其余继承基线。202 返回 `{"simulation_id": "sim_2c1", "status": "RUNNING", "poll_after_seconds": 2}`，`Location` 指向结果。`GET /admin/simulations/{sim_id}` 完成后返回：

```json
{
  "simulation_id": "sim_2c1",
  "status": "DONE",
  "baseline": { "policy_version": 12, "params": { "grace_period_minutes": 15 } },
  "candidate": { "params": { "grace_period_minutes": 20 } },
  "window": { "from": "2026-10-01", "to": "2026-10-29", "weeks": 4 },
  "results": [
    { "key": "effective_utilization", "baseline": 0.712, "candidate": 0.749, "delta": 0.037, "unit": "ratio", "confidence": "HIGH" },
    { "key": "waste_seat_minutes", "baseline": 41230, "candidate": 33010, "delta": -8220, "unit": "seat_minutes", "confidence": "HIGH" },
    { "key": "find_seat_failure_rate", "baseline": 0.0129, "candidate": 0.0121, "delta": -0.0008, "unit": "ratio", "confidence": "LOW" },
    { "key": "reject_rate", "baseline": 0.041, "candidate": 0.044, "delta": 0.003, "unit": "ratio", "confidence": "LOW" }
  ],
  "direction_only": false,
  "coverage": 0.94,
  "data_notes": ["2026-10-03 闭馆，已剔除"],
  "model_version": "d2-2026w47",
  "created_at": "2026-11-23T14:02:10+08:00"
}
```

`direction_only: true` 表示数据不足，只给方向不给数值（UC-14、DESIGN 8.5）。模拟结果只写 `simulation_report`，不生效；生效只能走 `POST /policies/{version}/activate`。

`GET /admin/attribution?policy_version=12&from=...&to=...` 返回上线前后的分区域对比，字段有 `method: "before_after"` 与 `causal_claim: false`，这是本轮的方法边界（只做前后对比，不做 DID 的平行趋势检验）。

### 3.9 运维

`GET /admin/models` 列出模型版本与回测指标：

```json
{
  "items": [
    {
      "model_version": "b3-2026w47",
      "trained_on": { "from": "2014-02-01", "to": "2022-05-31" },
      "status": "ACTIVE",
      "metrics": { "mae": 651, "persistence_mae": 835, "relative_gain": 0.220 },
      "gates": { "g1": "PASS" }
    },
    {
      "model_version": "d2-2026w47",
      "trained_on": { "from": "2024-12-09", "to": "2025-07-31" },
      "status": "ACTIVE",
      "metrics": { "mae": 0.0295, "persistence_mae": 0.0299, "relative_gain": 0.013, "calibration_gap_pp": 0.031, "coverage": 0.94 },
      "gates": { "g2": "PASS", "g3": "PASS" }
    }
  ]
}
```

日粒度看 `relative_gain ≥ 0.20`，30 分钟前瞻看相对 persistence 不劣 10% 与校准偏差，两条闸门不共用口径（R8）。

`POST /admin/models/{model_version}/activate` 带 `{"reason": "...", "confirm": true}` 切换生效指针，回滚 ≤ 10 分钟（7.3.5）。`GET /admin/drift` 返回滚动 MAE、份额位移与端口健康，触发条件写在 7.3.6。

`GET /admin/flags` 与 `PATCH /admin/flags` 管三元开关：

```json
{
  "policy_version": 12,
  "model_version": "d2-2026w47",
  "feature_flag": { "prediction": true, "waitlist": true, "oversell": false, "llm": false }
}
```

`PATCH` 只带要改的键，需要 `reason`，改完 1 分钟内生效（7.5.2）。`llm` 默认 `false`，本轮不实现 L1，开关留在契约里占位。G4 闸门没通过时 `oversell` 保持 `false`，配额按 1.0 走，这是 6.4 的硬约束在开关上的体现。

训练本身由 `ml` 侧命令行执行，不走 HTTP：训练、回测、导出 ONNX 都在离线侧完成后，再由 `activate` 把工件挂上。这样契约里只有一个生效入口。

`GET /health` 公开，返回 `{"status": "UP", "degraded": [], "flags": {...}}`，`degraded` 列出当前降级项与原因，供演练与监控取。

## 4 数据结构与枚举

预约状态六种，与 5.6 一致：`PENDING_CHECKIN`、`IN_USE`、`AWAY`、`COMPLETED`、`NO_SHOW`、`CANCELLED`。

结算原因六种，与 5.7 一致：`CHECK_OUT`、`SESSION_END`、`AWAY_TIMEOUT`、`NO_SHOW`、`FORCED_RELEASE`、`USER_CANCEL`。原因是受控枚举，账本与幂等键都以它为键，新增要同时改 5.7 与本文。

其余枚举：

| 字段 | 取值 |
|---|---|
| `seat.status` | `AVAILABLE`、`BOOKED`、`CLOSED` |
| `band` | `LOW`、`MEDIUM`、`HIGH` |
| `insufficient_reason` | `PREDICTION_DISABLED`、`COVERAGE_INSUFFICIENT`、`MODEL_UNAVAILABLE`、`NOT_READY` |
| `waitlist.status` | `WAITING`、`OFFERED`、`CONFIRMED`、`EXPIRED`、`CANCELLED` |
| `appeal.status` | `OPEN`、`REVERSED`、`REJECTED` |
| `appeal.reason_type` | `SYSTEM_ERROR`、`EXEMPTION`、`OTHER` |
| `confidence` | `HIGH`、`MEDIUM`、`LOW` |
| `policy.status` | `DRAFT`、`ACTIVE`、`RETIRED` |
| `model.status` | `CANDIDATE`、`ACTIVE`、`ROLLED_BACK` |
| `simulation.status` | `QUEUED`、`RUNNING`、`DONE`、`FAILED` |

## 5 两条硬约束

第一，任何端点都不能写信用分。信用分由账本派生，申诉撤销走追加冲正条目（7.2.6）。

第二，预测端点只读业务视图、只写三张结果表。契约上体现为预测相关接口没有写方法，内部打分落库也不对客户端暴露（7.2.5、3.6）。

## 6 不在本契约内

- `L1` 自然语言转检索参数与 `A1` 异常检测：本轮不实现，接口不预留（SRS 4.1 的 P2）。
- 对接真实校方系统、多校区、支付、原生 App 的接口，按 4.1 的非目标不做。
- 统一身份认证的对接细节：本轮用本地账号，`IdentityProviderPort` 只留实现位（DESIGN 7.4）。
- 短信与邮件通知：站内消息走 `/notifications`，外部渠道不排期。
