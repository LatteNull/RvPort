## Why

当前后端已经使用 session + cookie 完成登录认证，但项目级资源访问仍分散在各 service 中，部分接口只校验登录或资源存在，没有统一校验当前用户是否有权访问目标项目。项目级 SSE、任务日志、项目详情、源码和环境查询等接口存在跨用户读取项目数据的风险，需要在继续扩展任务和源码能力前收敛访问边界。

## What Changes

- 新增统一的项目访问守卫，按 `projects.created_by` 和 `users.is_super_admin` 判断当前用户是否能访问项目。
- 为项目、源码、环境、任务、任务日志和项目级 SSE API 增加显式项目访问校验。
- 对无权限访问使用与资源不存在一致的安全响应，避免暴露其他用户项目、任务、环境、源码版本或日志是否存在。
- 保留 MVP 当前模型，不引入角色、权限表、项目成员表或 RBAC。
- 补充单元测试和 API E2E，覆盖正常流程、异常流程和 edge case，重点包含跨用户越权读取、SSE 订阅和任务日志访问。

## Capabilities

### New Capabilities

- `project-access-guard`: 定义 MVP 项目访问守卫、资源归属校验、超级管理员旁路和越权响应策略。

### Modified Capabilities

- `backend-api-design`: 项目级 API 需要明确所有项目资源接口必须校验当前用户访问权限。
- `project-source-environment`: 项目、源码和环境能力需要在查询、创建、更新、运行任务等入口统一校验项目访问权限。
- `task-runtime`: 任务列表、任务详情、任务日志、日志下载、取消任务和项目级 SSE 必须校验任务所属项目访问权限。
- `api-e2e-test-suite`: API E2E 必须覆盖跨用户访问项目、任务、日志、源码、环境和 SSE 的拒绝路径。

## Impact

- 影响 controller/service：`ProjectController`、`ProjectService`、`SourceController`、`SourceService`、`EnvironmentController`、`EnvironmentService`、`TaskController`、`TaskService`、`TaskLogService`、`TaskSseController`。
- 可能新增 `ProjectAccessService` 或等价共享组件，用于集中判断项目、任务、环境、源码版本和任务日志归属。
- API 行为变化：普通用户访问非本人项目资源时应得到安全错误，不再返回数据；超级管理员继续可访问所有项目资源。
- 测试影响：需要补充 controller/service 单元测试和 E2E 越权测试。
