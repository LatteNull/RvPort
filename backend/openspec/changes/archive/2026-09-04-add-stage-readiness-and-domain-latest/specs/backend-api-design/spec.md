## ADDED Requirements

### Requirement: API 必须提供项目级阶段 readiness
后端 API SHALL 提供项目级阶段 readiness 接口，用于返回当前 Context 下指定 workflow 阶段的前置条件事实。

#### Scenario: 查询阶段 readiness
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/readiness?stageId={stageId}`
- **THEN** 后端 SHALL 校验用户对项目的访问权限
- **AND** 响应 SHALL 包含 `stageId`、`context` 和 `prerequisites`
- **AND** `context` SHALL 包含当前 `sourceRevisionId` 和当前 `runtimeEnvironmentVersion`
- **AND** `prerequisites` 中每项 SHALL 包含 `key`、`status`、`referenceId` 和 `reasonCode`

#### Scenario: readiness 不返回 UI 动作
- **WHEN** 后端返回阶段 readiness
- **THEN** 响应 MUST NOT 包含 `ready`、`actions`、`buttons`、`buttonLabel` 或 `recommendedAction`
- **AND** 前端 SHALL 基于稳定的 `key` 和 `status` 自行组合 UI 行为

#### Scenario: readiness 状态枚举
- **WHEN** 后端计算任一 prerequisite 状态
- **THEN** `status` MUST 使用 `SATISFIED`、`MISSING`、`RUNNING`、`FAILED`、`STALE` 或 `UNAVAILABLE`
- **AND** `reasonCode` MUST 使用稳定枚举值
- **AND** `reasonCode` MUST NOT 依赖中文展示文案

#### Scenario: readiness 越权访问失败
- **WHEN** 普通用户访问无权限项目的 readiness
- **THEN** 后端 SHALL 返回 `FORBIDDEN` 或 `PROJECT_NOT_FOUND`
- **AND** 后端 MUST NOT 暴露该项目的源码、环境、任务或执行记录信息

### Requirement: 领域 latest 接口必须使用统一响应外壳
需要 latest 的领域接口 SHALL 保留各自领域路径，但响应业务数据 SHALL 使用统一 latest 外壳。

#### Scenario: 返回当前领域 latest
- **WHEN** 已登录用户调用某个领域 latest 接口
- **THEN** 后端 SHALL 校验用户对项目的访问权限
- **AND** 响应业务数据 SHALL 包含 `context`、`freshness`、`execution` 和 `result`
- **AND** `context` SHALL 包含当前 `sourceRevisionId` 和当前 `runtimeEnvironmentVersion`
- **AND** `result` SHALL 保持领域自己的结构

#### Scenario: 无执行记录返回空 latest
- **WHEN** 当前 Context 下没有对应领域执行记录
- **THEN** latest 接口 SHALL 成功返回
- **AND** `freshness` SHALL 为 `EMPTY`
- **AND** `execution` SHALL 为 `null`
- **AND** `result` SHALL 为 `null`
- **AND** 后端 MUST NOT 使用 404 表达无 latest

#### Scenario: latest 不回退到旧成功记录
- **WHEN** 当前 Context 下最新执行记录为失败、取消或运行中
- **THEN** latest 接口 SHALL 返回该最新执行记录
- **AND** 后端 MUST NOT 跳过该记录并回退到更早的成功记录

#### Scenario: latest 标识旧 Context
- **WHEN** 领域存在历史记录但没有当前 Context 记录
- **THEN** latest 接口 SHALL 返回 `freshness=STALE` 或 `freshness=EMPTY`
- **AND** 后端 MUST NOT 将旧源码版本或旧运行环境版本的结果标记为 `CURRENT`

### Requirement: 执行类写接口必须重新校验 readiness 事实
所有依赖前置条件的执行类写接口 SHALL 在创建任务前重新读取当前 Context 并校验所需 prerequisite。

#### Scenario: 写接口拒绝已过期前置条件
- **WHEN** 调用方基于旧 readiness 结果提交执行类写请求
- **AND** 后端重新读取后发现前置条件已变为 `STALE`、`FAILED`、`MISSING` 或 `UNAVAILABLE`
- **THEN** 后端 SHALL 拒绝创建任务
- **AND** 错误码 SHALL 为 `PREREQUISITE_NOT_SATISFIED`
- **AND** 错误详情 SHALL 包含 `stageId`、`prerequisite`、`status` 和 `reasonCode`

#### Scenario: 写接口不信任前端判断
- **WHEN** 前端曾经成功查询 readiness
- **THEN** 后端执行写接口时 MUST NOT 复用前端传回的 readiness 判断
- **AND** 后端 SHALL 以数据库当前状态为准
