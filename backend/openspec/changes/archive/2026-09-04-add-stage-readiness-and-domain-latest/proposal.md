## Why

项目工作台需要用统一方式判断各阶段是否具备执行条件，并展示当前 Context 下各领域的最新执行结果。当前后端只有部分列表、详情和少量专用 latest/readiness 接口，前端需要拼接多个接口并散落业务判断，容易出现 Context 过期、旧结果误展示和写接口缺少二次校验的问题。

## What Changes

- 增加项目级阶段 readiness 接口：`GET /api/projects/{projectId}/readiness?stageId={stageId}`。
- 为 `kb`、`x86-build`、`rv-dependency-analysis`、`report`、`build`、`test`、`optimize`、`archive` 等阶段返回统一前置条件事实。
- 保留领域 latest 接口形态，不新增统一 `/latest?stageId=...`，但为各领域 latest 响应增加统一外壳。
- latest 结果必须基于当前 `sourceRevisionId` 和当前 `runtimeEnvironmentVersion` 计算 `freshness`，不得跳过最新失败记录回退到更早成功记录。
- 写接口必须重新读取并校验当前 Context，不能依赖前端先前查询到的 readiness 结果。
- 调整 API E2E 覆盖：验证 readiness 状态、latest 外壳、旧 Context 判定、运行中/失败场景、权限隔离和写接口二次校验。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `backend-api-design`: 增加项目级 readiness 通用接口、领域 latest 统一外壳和写接口二次校验约束。
- `kb-scan-runtime`: 增加知识库扫描 latest 语义和 readiness 前置条件。
- `build-validation-runtime`: 增加 x86 构建 latest、构建验证 latest 和对应 readiness 前置条件。
- `dependency-analysis-runtime`: 增加依赖分析 latest 和 readiness 前置条件。
- `automated-test-runtime`: 增加自动化测试 latest 和 readiness 前置条件。
- `optimization-cycle-runtime`: 增加优化闭环 latest 展示语义。
- `project-archive-runtime`: 增加归档 latest 展示语义和 readiness 前置条件。
- `api-e2e-test-suite`: 增加 latest/readiness 相关端到端测试要求。

## Impact

- 影响后端 API、DTO、service 查询聚合、权限校验和错误码。
- 需要复用现有 `sourceRevisionId`、`environmentConfigVersion`、任务状态、运行记录和迁移输入确认状态。
- 需要为各领域补充 latest 查询方法或包装现有列表查询。
- 需要扩展 E2E 模块，覆盖当前 Context、旧 Context、运行中、失败、无记录和越权访问。
