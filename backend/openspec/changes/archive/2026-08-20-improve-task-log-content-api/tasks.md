## 1. 数据库和生成代码

- [x] 1.1 新增 Liquibase changeset，为 `build_runs` 增加 `combined_log_id` 或等效 merged log 引用字段。
- [x] 1.2 为 `build_runs.combined_log_id` 增加到 `task_logs.id` 的外键或等效完整性约束。
- [x] 1.3 运行 Liquibase 并确认旧构建记录允许 `combined_log_id` 为空。
- [x] 1.4 运行 jOOQ 生成脚本并确认生成代码纳入 `src/generated/java`。

## 2. 日志内容读取服务

- [x] 2.1 新增日志内容读取请求 DTO，支持 `types`、全局 `lines`、单类 offset 和单类 lines。
- [x] 2.2 新增日志内容响应 DTO，返回每类日志的 `type`、`logId`、`offset`、`lines`、`returnedLines`、`hasMore` 和 `content`。
- [x] 2.3 实现受控日志文件 tail 工具，从文件底部按 offset 和 lines 读取内容。
- [x] 2.4 日志读取逻辑必须支持空文件、无结尾换行、Windows/Unix 换行、超长单行和大日志文件。
- [x] 2.5 日志读取 service 按任务和日志类型选择最新 `task_logs` 元数据作为文件引用。
- [x] 2.6 缺失某类日志时返回空内容和 `hasMore=false`，不得导致整个请求失败。

## 3. API 实现和权限边界

- [x] 3.1 新增 `GET /api/tasks/{taskId}/log-content`。
- [x] 3.2 接口复用任务访问守卫，确保无权限用户无法读取任务日志内容。
- [x] 3.3 校验未知 `types`、负数 offset、负数 lines 和超过上限的 lines。
- [x] 3.4 接口默认返回 `merged`、`stdout`、`stderr` 三类最后 100 行。
- [x] 3.5 接口支持只请求单类日志。
- [x] 3.6 接口支持同一请求中三类日志使用不同 offset 和 lines。
- [x] 3.7 响应不得返回服务器真实日志路径、明文凭据或未脱敏敏感信息。

## 4. 构建和测试运行记录

- [x] 4.1 构建验证 worker 完成时写入最新 `COMBINED` 日志 ID。
- [x] 4.2 构建验证成功、失败、取消、超时路径均保存 merged/stdout/stderr 日志引用。
- [x] 4.3 构建详情响应增加 `mergedLogId` 或等效字段，并保留 `stdoutLogId`、`stderrLogId`。
- [x] 4.4 自动化测试响应确认 `combinedLogId` 作为 merged log 引用，并在文档中统一命名说明。
- [x] 4.5 旧构建或测试记录缺少 merged log 时，API 返回明确空值而不是错误。

## 5. 文档和 OpenSpec 同步

- [x] 5.1 更新 `docs/API_DESIGN.md`，补充日志内容读取 API 参数和响应。
- [x] 5.2 更新 `docs/DATABASE_DESIGN.md`，补充构建 merged log 字段。
- [x] 5.3 更新 `docs/api-e2e-coverage.md`，补充任务日志内容读取覆盖项。
- [x] 5.4 确认运行中日志 SSE 和完成态日志内容读取的边界在文档中清晰区分。

## 6. 测试和验证

- [x] 6.1 增加 tail 工具单元测试，覆盖正常流程、异常流程和 edge case。
- [x] 6.2 增加日志内容 service 单元测试，覆盖单类、多类、不同 offset、缺失日志和非法参数。
- [x] 6.3 增加 MVC 或 controller 测试，覆盖权限校验和参数校验。
- [x] 6.4 增加构建验证测试，覆盖 merged log ID 写入。
- [x] 6.5 增加自动化测试日志引用回归测试。
- [x] 6.6 增加 E2E case，覆盖默认三类日志读取、单类读取、多类不同 offset、非法参数和越权读取。
- [x] 6.7 运行 `mvn test`。
- [x] 6.8 重建并启动后端容器。
- [x] 6.9 运行相关 E2E 模块，确认测试数据清理不留下脏数据。
- [x] 6.10 运行 `openspec validate improve-task-log-content-api --strict`。
