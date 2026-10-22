## Why

后端已经完成数据库设计归档，API 设计需要同步收敛到当前 MVP 持久化边界和任务模型。

根目录下已有 `docs/design/01_API_DESIGN.md`，它可以作为 API 设计底稿，但其中仍包含与最新数据库设计不一致的内容，例如通用 Artifact API、用户角色权限返回、任务状态缺少 `QUEUED`、任务级 SSE 与项目级 SSE 并存、测试用例级能力超出 MVP 边界等。

如果不先整理后端 API 设计，后续前后端联调、Worker 编排、日志下载、报告导出和安全脱敏会在接口边界上反复返工。

## What Changes

- 在 backend 下建立中文 API 设计文档，基于根目录 API 设计底稿进行收敛。
- 明确 API 以 `/api` 为 base path，使用统一响应包络、分页格式和错误格式。
- 明确认证 API 只返回本地用户信息和 `isSuperAdmin`，不返回角色或权限模型。
- 增加超级管理员用户管理 API，支持在配置页用户信息表中查看用户列表，并对本地用户进行创建、读取、更新、禁用/删除和重置密码。
- 明确 `isSuperAdmin` 不允许通过 API 创建或修改，只能通过数据库初始化脚本或数据库维护方式设置。
- 明确用户创建和密码重置流程需要 `users.must_change_password` 字段支持首次登录或重置后强制改密。
- 明确项目 `stage` 是导航提示，项目概览由源码版本、任务、运行结果、问题和差异聚合得到。
- 明确异步任务创建接口返回 `taskId` 和初始状态；队列只投递 `task_id`。
- 统一使用项目级 SSE：`GET /api/projects/{projectId}/task-events`，任务详情与日志分页作为断线补偿。
- 去掉通用 Artifact API，改为报告、归档和任务日志等业务资源各自提供下载入口。
- 明确凭据只允许写入或重新配置，查询响应只返回遮蔽摘要。
- 明确 MVP 测试 API 只暴露退出码和汇总计数，不提供测试用例级重跑或解析能力。
- 对齐数据库领域表：项目、源码版本、环境、凭据、任务、KB 扫描、SBOM、问题、报告、复检、构建、测试、归档和审计。

## Capabilities

### New Capabilities

- `backend-api-design`：定义 RvPort 后端 MVP API 的接口边界、通用约定、异步任务模型、SSE 事件模型、下载边界、凭据脱敏要求和各业务模块 API。

### Modified Capabilities

- 无。

## Impact

- 影响后续 `backend/docs/API_DESIGN.md` 文档。
- 为后续后端路由、请求/响应 DTO、OpenAPI schema、前端 mock 和 worker 编排提供契约依据。
- 与已归档的 `backend-database-design` spec 强相关，尤其是任务状态、SSE、凭据、日志、artifact 排除和测试摘要边界。
- 同时补充数据库设计 delta spec：用户管理 API 需要 `users.must_change_password boolean not null default false`。
