-- 预测只读账号的写入授权（7.2.5、ADR-4）。
-- 由 MySQL 容器的初始化脚本在 01_accounts.sql 建好库与两个账号之后执行；
-- 账号名与库名以初始化脚本为准，这里按 seatwise / seatwise_ro 书写。
--
-- 边界：预测账号读业务视图、只写三张结果表。写权限给 INSERT/UPDATE/DELETE 是因为
-- 批量预计算需要覆盖与清理过期行（每 15 分钟一批，单批 ≤ 60 秒，SRS 7.6.2）。

GRANT SELECT, INSERT, UPDATE, DELETE ON seatwise.occupancy_prediction TO 'seatwise_ro'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON seatwise.waste_estimate TO 'seatwise_ro'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON seatwise.simulation_report TO 'seatwise_ro'@'%';

-- 业务写账号不要用 ON seatwise.* 全库授权：MySQL 的权限是叠加的，库级写权限无法用表级
-- REVOKE 收回，会顺带让业务账号拿到三张结果表的写权限（违反 DESIGN 2.1）。
-- 01_accounts.sql 应按 8 张核心表逐表授予 INSERT/UPDATE/DELETE，结果表只授 SELECT。
