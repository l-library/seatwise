-- 预测结果表（V2）。假设 V1 由「预约引擎」那节建立 8 张核心表；本迁移与业务表之间不建外键，
-- 因此可以先于 V1 单独执行 —— 预测结果不得与任何一条预约产生关联（DESIGN 4.1）。
--
-- 对应需求：
--   7.2.5 / ADR-4  预测只读账号对业务表只读，只写这三张结果表
--   7.1.4 / R2     概率必须落 zone、slot、feature_as_of、model_version、band、coverage 六项
--   3.6            D1/D2 写 occupancy_prediction，D3 写 waste_estimate，C3 写 simulation_report
--   7.6.4 / R12    由 WiFi 或门禁推断的代理指标必须可识别
--
-- 时间列一律存 UTC，展示层再按 Asia/Shanghai 转换（API.md 1.3）。

CREATE TABLE occupancy_prediction (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '代理主键',
    zone_id VARCHAR(32) NOT NULL COMMENT '区域标识，对应业务库 zone.id',
    slot_start DATETIME NOT NULL COMMENT '时段起点（UTC），对齐 30 分钟',
    duration_minutes SMALLINT UNSIGNED NOT NULL COMMENT '时长（分钟），30 的整数倍',
    model_version VARCHAR(32) NOT NULL COMMENT '模型版本（7.5.3）',
    feature_as_of DATETIME NOT NULL COMMENT '特征截至时间（7.1.4）',
    band ENUM('LOW', 'MEDIUM', 'HIGH') NOT NULL COMMENT '概率分档（7.1.4）',
    probability DECIMAL(5, 4) NULL COMMENT '找座概率；G2 未通过或数据不足时为 NULL',
    coverage DECIMAL(5, 4) NOT NULL COMMENT '覆盖率（7.1.4、7.4.6）',
    proxy_metric TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1 表示特征含 WiFi/门禁推断值（R12）',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '写入时间（UTC）',
    PRIMARY KEY (id),
    UNIQUE KEY uk_occupancy_prediction (zone_id, slot_start, duration_minutes, model_version),
    KEY idx_occupancy_prediction_lookup (zone_id, slot_start, model_version)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci COMMENT = 'D1/D2 预测结果：只由预测账号写，不参与预约校验';

CREATE TABLE waste_estimate (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '代理主键',
    zone_id VARCHAR(32) NOT NULL COMMENT '区域标识，对应业务库 zone.id',
    slot_start DATETIME NOT NULL COMMENT '统计窗口起点（UTC）',
    duration_minutes SMALLINT UNSIGNED NOT NULL COMMENT '窗口长度（分钟），30 的整数倍',
    model_version VARCHAR(32) NOT NULL COMMENT '模型版本（7.5.3）',
    feature_as_of DATETIME NOT NULL COMMENT '特征截至时间（7.1.4）',
    expected_waste_seat_minutes DECIMAL(12, 2) NOT NULL COMMENT '期望浪费（座·分钟，D3）',
    coverage DECIMAL(5, 4) NOT NULL COMMENT '覆盖率（7.4.6）',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '写入时间（UTC）',
    PRIMARY KEY (id),
    UNIQUE KEY uk_waste_estimate (zone_id, slot_start, duration_minutes, model_version),
    KEY idx_waste_estimate_window (zone_id, slot_start)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci COMMENT = 'D3 期望浪费：供看板与配额建议读取（UC-11/12）';

CREATE TABLE simulation_report (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '代理主键',
    simulation_id VARCHAR(32) NOT NULL COMMENT '对外标识（API.md 3.8）',
    baseline_policy_version INT NOT NULL COMMENT '基线政策版本',
    candidate_params JSON NOT NULL COMMENT '只记录被改的参数，其余继承基线（UC-14）',
    window_from DATE NOT NULL COMMENT '重放窗口起点',
    window_to DATE NOT NULL COMMENT '重放窗口终点（不含）',
    status ENUM('QUEUED', 'RUNNING', 'DONE', 'FAILED') NOT NULL DEFAULT 'QUEUED' COMMENT '执行状态',
    direction_only TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1 表示数据不足只给方向（UC-14）',
    results JSON NULL COMMENT '利用率/浪费/找座失败率/拒绝率四列对比',
    data_notes JSON NULL COMMENT '剔除或降级说明，如闭馆日',
    coverage DECIMAL(5, 4) NULL COMMENT '覆盖率（7.4.6）',
    model_version VARCHAR(32) NULL COMMENT '当时生效的模型版本，可为空',
    created_by VARCHAR(32) NOT NULL COMMENT '触发模拟的操作者',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
    PRIMARY KEY (id),
    UNIQUE KEY uk_simulation_report (simulation_id),
    KEY idx_simulation_report_status (status, created_at)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci COMMENT = 'C3 政策模拟结果：只追加，生效只能走政策版本';
