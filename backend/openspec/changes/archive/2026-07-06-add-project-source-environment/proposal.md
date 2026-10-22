## Why

后端已经具备认证、任务运行时、队列、SSE、数据库 schema 和凭据加密能力，但项目工作台还缺少项目、源码版本、执行环境这三个核心业务入口。现在补齐这层能力，可以让后续 KB 扫描、SBOM、构建、测试和报告能力都有稳定的项目上下文、当前源码版本和环境引用。

## What Changes

- 新增项目管理 API：项目列表、创建、详情、基础信息更新和项目概览。
- 新增源码版本 API：源码版本列表、压缩包上传、Git 同步任务创建和当前源码版本切换。
- 新增环境管理 API：SSH 环境列表、创建、详情、更新、禁用、连接测试任务、环境采集任务、远程脚本任务和快照列表。
- 环境配置支持可选跳板机：先登记一个环境作为跳板机，创建或更新源机器/目标机器时可选择该跳板机。
- 新增凭据写入和遮蔽展示流程：Git/SSH 凭据写入 `credentials` 表前必须加密，查询响应只返回配置状态、类型、名称和遮蔽摘要。
- 将项目、源码、环境中的长操作接入现有任务运行时：任务状态以 PostgreSQL 为事实来源，RabbitMQ 只投递任务 ID，API 不返回完整输入快照、明文凭据或服务器本地路径。
- 明确 MVP 访问边界：不引入角色、权限、用户角色映射或项目成员模型；项目级权限先收敛为已登录用户可访问，超级管理员没有额外项目授权模型。
- 不实现真实 KB 扫描、SBOM、构建、测试、报告、完整 Git clone 处理或 SSH 采集执行细节；这些由后续任务处理器能力补齐。

## Capabilities

### New Capabilities
- `project-source-environment`: 覆盖项目管理、源码版本管理、环境管理、凭据遮蔽展示和相关长任务投递的实现契约。

### Modified Capabilities
- `backend-api-design`: 补充项目、源码、环境 API 的具体行为、任务投递边界、凭据安全边界和 MVP 访问约束。
- `backend-database-design`: 补充 `environments` 对跳板机自引用关系的 schema 要求。

## Impact

- 受影响代码区域：
  - `src/main/java/cn/rvport/backend/project`
  - `src/main/java/cn/rvport/backend/source`
  - `src/main/java/cn/rvport/backend/environment`
  - `src/main/java/cn/rvport/backend/credential`
  - `src/main/java/cn/rvport/backend/task`
  - `src/main/java/cn/rvport/backend/audit`
- 受影响数据库与生成代码：
  - 新增 Liquibase changelog，给 `environments` 增加可空跳板机引用字段
  - 重新运行 jOOQ 生成脚本并提交生成代码
- 受影响配置：
  - `RVPORT_UPLOAD_DIR`
  - `RVPORT_CREDENTIAL_MASTER_KEY`
  - `RVPORT_CREDENTIAL_KEY_ID`
- 受影响数据表：
  - `projects`
  - `source_revisions`
  - `source_imports`
  - `credentials`
  - `environments`
  - `environment_snapshots`
  - `environment_components`
  - `tasks`
  - `task_events`
  - `audit_logs`
- 需要补充控制器、服务、仓储、DTO、校验、审计和测试。
