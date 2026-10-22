## 1. 文档与数据库

- [x] 1.1 更新 `backend/docs/API_DESIGN.md`，明确 latest compare 是复检差异状态而不是源码文本 diff，并补充新增 API 请求/响应。
- [x] 1.2 更新 `backend/docs/DATABASE_DESIGN.md`，补充 `diff_items` 摘要字段、snapshot 字段、match confidence/reason 字段和索引说明。
- [x] 1.3 新增 Liquibase migration，扩展 `diff_items` 以及必要的迁移输入 identity 字段。
- [x] 1.4 运行 Liquibase 并重新生成 jOOQ 代码，确认 generated sources 纳入源码。

## 2. 复检任务创建 API

- [x] 2.1 新增 `POST /api/projects/{projectId}/rechecks`，支持显式 base/target source revision。
- [x] 2.2 新增 `POST /api/projects/{projectId}/rechecks/latest`，由后端选择 active target 和 previous base。
- [x] 2.3 校验项目权限、源码版本归属、base/target 不可相同、previous 不存在等异常。
- [x] 2.4 实现同 project/base/target 的复检任务幂等复用，避免重复创建并发任务。
- [x] 2.5 创建复检任务后投递 RabbitMQ，并返回 `TaskResponse`。

## 3. 复检运行时与差异生成

- [x] 3.1 新增 recheck task handler，读取 base/target source revision 下 `CONFIRMED` 的迁移输入 reference。
- [x] 3.2 实现迁移输入 snapshot 构建，包含列表展示字段、来源详情摘要和匹配 identity 字段。
- [x] 3.3 实现 exact fingerprint 匹配，并生成 `matchConfidence=HIGH`、`matchReason=EXACT_FINGERPRINT`。
- [x] 3.4 实现代码类 finding 的规则化 fuzzy matching，支持行号变化后的同一 issue 匹配。
- [x] 3.5 实现 SBOM 类输入的稳定 identity 匹配。
- [x] 3.6 生成 `RESOLVED`、`NEW`、`UNCHANGED`、`CHANGED` diff items，并写入 old/new source id 与 snapshot。
- [x] 3.7 更新 `recheck_runs.status`、`summary`、任务状态和 SSE 事件。
- [x] 3.8 复检任务失败时正确写入失败状态和错误摘要。

## 4. 差异查询 API

- [x] 4.1 扩展 `GET /api/rechecks/{recheckRunId}/diff-items` 响应字段，返回 `title`、`locationLabel`、`recommendation`、`confirmationStatus`、`matchConfidence`、`matchReason`。
- [x] 4.2 扩展 diff item 列表过滤，支持 `diffStatus`、`sourceType`、`severity`、`matchConfidence`。
- [x] 4.3 扩展 diff item 列表排序白名单，覆盖前端表格需要的字段。
- [x] 4.4 新增 `GET /api/rechecks/{recheckRunId}/diff-items/{diffItemId}`，返回 old/new 两侧快照和匹配证据。
- [x] 4.5 确保所有响应只返回源码相对路径或脱敏展示字段，不暴露服务器真实路径。

## 5. latest compare 集成

- [x] 5.1 调整 latest compare 文档和响应语义，明确返回 latest recheck diff 状态。
- [x] 5.2 latest compare 在存在运行中复检时返回 `RUNNING` 和 task id。
- [x] 5.3 latest compare 在复检成功时返回 diff summary 和 diff item 分页入口。
- [x] 5.4 latest compare 在没有复检记录时保持 `NOT_STARTED`，不自动创建任务。

## 6. 单元测试

- [x] 6.1 覆盖复检任务创建正常流程：显式版本、latest 版本、幂等复用。
- [x] 6.2 覆盖复检任务创建异常流程：无权限、跨项目 revision、base/target 相同、无 previous revision。
- [x] 6.3 覆盖复检任务创建 edge case：已有 running/succeeded/failed 复检记录的处理。
- [x] 6.4 覆盖 diff 生成正常流程：`RESOLVED`、`NEW`、`UNCHANGED`、`CHANGED`。
- [x] 6.5 覆盖 diff 生成异常流程：来源快照缺失、来源类型未知、迁移输入不完整。
- [x] 6.6 覆盖 diff 生成 edge case：行号变化但 stable anchor 相同、路径轻微变化、低置信度匹配。
- [x] 6.7 覆盖 diff item 列表和详情权限校验、过滤、排序和分页。

## 7. E2E 与验证

- [x] 7.1 更新模块化 E2E，创建两个源码版本和两组已确认迁移输入。
- [x] 7.2 E2E 覆盖创建 latest 复检任务、监听任务完成、查询 latest compare。
- [x] 7.3 E2E 覆盖 diff item 列表和详情，验证 old/new snapshot、matchConfidence 和 diffStatus。
- [x] 7.4 E2E 完成后清理测试项目、迁移输入、复检记录、diff items 和任务数据。
- [x] 7.5 运行 `mvn test` 和相关 E2E 模块，记录结果。
