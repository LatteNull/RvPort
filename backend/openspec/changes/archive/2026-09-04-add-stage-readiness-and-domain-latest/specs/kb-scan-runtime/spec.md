## ADDED Requirements

### Requirement: 知识库扫描必须提供 latest
知识库扫描领域 SHALL 提供当前 Context 下的 latest 接口，用于返回最新知识库扫描执行状态和结果摘要。

#### Scenario: 查询知识库扫描 latest
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/kb-scans/latest`
- **THEN** 后端 SHALL 返回统一 latest 外壳
- **AND** `context.sourceRevisionId` SHALL 为项目当前 active source revision
- **AND** `execution` SHALL 指向当前源码版本下最新知识库扫描任务
- **AND** `result` SHALL 包含知识库扫描摘要、finding 数量和 artifact 摘要

#### Scenario: 知识库扫描 latest 识别旧源码
- **WHEN** 只有旧源码版本的知识库扫描记录存在
- **THEN** 后端 MUST NOT 将该记录标记为 `CURRENT`
- **AND** latest SHALL 返回 `freshness=STALE` 或 `freshness=EMPTY`

### Requirement: 知识库扫描 readiness 必须校验 active source
项目级 readiness 在 `stageId=kb` 时 SHALL 返回知识库扫描所需的源码前置条件。

#### Scenario: active source 已存在
- **WHEN** 项目存在 active source revision
- **THEN** `ACTIVE_SOURCE` prerequisite SHALL 返回 `SATISFIED`
- **AND** `referenceId` SHALL 指向 active source revision

#### Scenario: active source 缺失
- **WHEN** 项目不存在 active source revision
- **THEN** `ACTIVE_SOURCE` prerequisite SHALL 返回 `MISSING`
- **AND** `reasonCode` SHALL 为 `ACTIVE_SOURCE_MISSING`
