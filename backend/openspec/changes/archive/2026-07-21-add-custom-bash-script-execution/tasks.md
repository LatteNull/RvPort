## 1. 数据库与生成代码

- [x] 1.1 新增 Liquibase 迁移，创建脚本正文安全存储表并定义唯一约束、外键、索引和字段长度约束
- [x] 1.2 新增 Liquibase 迁移，创建 `task_log_events` 表并定义 `task_id,id`、`project_id,task_id,id`、`task_id,sequence` 查询路径
- [x] 1.3 更新数据库设计文档，说明脚本正文加密存储、日志事件表和 `task_logs` 完整日志文件分工
- [x] 1.4 执行 Liquibase 迁移验证空库和当前库可升级
- [x] 1.5 运行 jOOQ codegen 并提交新表生成代码

## 2. 脚本正文安全存储

- [x] 2.1 实现脚本正文存储 repository/service，支持按任务保存和按任务读取
- [x] 2.2 使用现有加密能力保护脚本正文，API 响应、审计、任务输入和事件只暴露 hash/length/reference
- [x] 2.3 为脚本正文 hash 校验、缺失引用、解密失败和跨项目访问补充单元测试

## 3. 日志事件与任务级 SSE

- [x] 3.1 实现 `task_log_events` repository/service，支持日志内容切片、脱敏、序号生成和分页/游标查询
- [x] 3.2 扩展任务执行上下文或新增日志 sink，使 worker 输出能同时写入本地日志文件、`task_logs` 元数据、`task_log_events` 和实时发布
- [x] 3.3 实现任务级日志 SSE broker/controller：`GET /api/tasks/{taskId}/log-events`
- [x] 3.4 实现任务级日志 SSE 历史补发、`Last-Event-ID` 恢复、heartbeat、终态事件和终态后关闭策略
- [x] 3.5 补充无权限订阅、非法 `Last-Event-ID`、跨任务游标隔离和 emitter 清理测试

## 4. CUSTOM_BASH 执行

- [x] 4.1 修改环境脚本创建流程，`CUSTOM_BASH` 创建任务前保存脚本正文并在任务输入快照中写入安全引用
- [x] 4.2 修改 SSH runtime，使 `CUSTOM_BASH` 通过远端临时脚本文件执行并在完成后清理远端临时文件
- [x] 4.3 捕获 stdout/stderr 增量输出并写入日志事件、日志文件和任务级 SSE
- [x] 4.4 写入 `tool_runs` 执行记录，保存退出码、脚本 hash、脚本长度、耗时、日志事件数量和安全摘要
- [x] 4.5 处理非 0 退出码、SSH 失败、脚本引用缺失、hash 不匹配、取消和超时场景

## 5. 脚本执行记录 API

- [x] 5.1 实现 `GET /api/projects/{projectId}/script-executions`，支持分页、过滤、排序和项目访问守卫
- [x] 5.2 实现 `GET /api/script-executions/{executionId}`，返回任务、环境、tool run 和日志统计摘要
- [x] 5.3 实现执行记录状态映射：`PENDING/QUEUED/RUNNING -> RUNNING`、`SUCCEEDED -> SUCCEEDED`、`FAILED/TIMEOUT/CANCELLED -> ERROR`
- [x] 5.4 确认响应不包含脚本正文、明文凭据、服务器真实路径或日志文件路径

## 6. 测试与验证

- [x] 6.1 补充 Java 单元测试，覆盖正常流程、异常流程和 edge case
- [x] 6.2 补充 E2E 模块或 case，覆盖 CUSTOM_BASH 成功、失败、参数校验、日志 SSE 首次补发、断线恢复和越权订阅
- [x] 6.3 使用真实后端和基础设施运行相关 E2E，并确认数据库、Redis、RabbitMQ、日志目录无异常副作用
- [x] 6.4 校验任务输入、任务事件、日志事件、审计日志和 API 响应不泄露脚本正文或敏感信息
- [x] 6.5 运行 `mvn test` 和相关模块 E2E

## 7. 文档

- [x] 7.1 更新 `docs/API_DESIGN.md`，补充脚本执行记录 API 和任务级日志 SSE
- [x] 7.2 更新 `docs/api-e2e-coverage.md` 和 `e2e/README.md`，说明新增 E2E 模块和运行方式
- [x] 7.3 更新 README 或后端开发文档中的脚本执行和日志恢复说明
