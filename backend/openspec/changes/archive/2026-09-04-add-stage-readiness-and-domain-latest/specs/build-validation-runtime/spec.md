## ADDED Requirements

### Requirement: 构建运行必须提供 latest
构建运行领域 SHALL 提供当前 Context 下的 latest 接口，支持区分 x86 构建和双环境构建验证。

#### Scenario: 查询 x86 构建 latest
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/builds/latest?mode=SOURCE_ONLY`
- **THEN** 后端 SHALL 返回统一 latest 外壳
- **AND** `execution` SHALL 指向当前源码版本和当前运行环境版本下最新 source-only 构建运行
- **AND** `result` SHALL 包含构建环境、部署记录、构建状态、日志入口和 artifact 摘要

#### Scenario: 查询构建验证 latest
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/builds/latest?mode=VALIDATION`
- **THEN** 后端 SHALL 返回统一 latest 外壳
- **AND** `execution` SHALL 指向当前源码版本和当前运行环境版本下最新构建验证批次或运行摘要
- **AND** `result` SHALL 包含 x86 与 RISC-V 构建运行摘要

#### Scenario: 构建 latest 不跳过失败
- **WHEN** 当前 Context 下最新构建运行失败
- **THEN** latest SHALL 返回失败 execution
- **AND** 后端 MUST NOT 回退到更早成功构建

### Requirement: 构建 readiness 必须返回源码和环境事实
项目级 readiness 在 `stageId=x86-build` 或 `stageId=build` 时 SHALL 返回构建所需前置条件。

#### Scenario: 查询 x86 构建 readiness
- **WHEN** 用户调用 `GET /api/projects/{projectId}/readiness?stageId=x86-build`
- **THEN** 后端 SHALL 返回 `ACTIVE_SOURCE` 和 `SOURCE_ENVIRONMENT`
- **AND** 如果已有当前 Context 的源码部署执行记录，后端 SHALL 返回 `SOURCE_DEPLOYMENT`

#### Scenario: 查询双环境构建 readiness
- **WHEN** 用户调用 `GET /api/projects/{projectId}/readiness?stageId=build`
- **THEN** 后端 SHALL 返回 `ACTIVE_SOURCE`、`SOURCE_ENVIRONMENT` 和 `TARGET_ENVIRONMENT`
- **AND** 缺少任一运行环境时对应 prerequisite SHALL 返回 `MISSING`

#### Scenario: 环境配置过期
- **WHEN** 构建相关记录的 `environmentConfigVersion` 不等于项目当前运行环境版本
- **THEN** 对应 prerequisite SHALL 返回 `STALE`
- **AND** `reasonCode` SHALL 为 `RUNTIME_ENVIRONMENT_CHANGED`
