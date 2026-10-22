## ADDED Requirements

### Requirement: 依赖分析必须提供 latest
依赖分析领域 SHALL 提供当前 Context 下的 latest 接口，返回最新依赖分析执行状态和结果摘要。

#### Scenario: 查询依赖分析 latest
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/dependency-analyses/latest`
- **THEN** 后端 SHALL 返回统一 latest 外壳
- **AND** `execution` SHALL 指向当前源码版本和当前运行环境版本下最新依赖分析任务
- **AND** `result` SHALL 包含结果总数、风险统计、目标匹配统计、报告 artifact 和可修复候选摘要

#### Scenario: 依赖分析 latest 识别旧环境
- **WHEN** 只有旧运行环境版本的依赖分析记录存在
- **THEN** 后端 MUST NOT 将该记录标记为 `CURRENT`
- **AND** latest SHALL 返回 `freshness=STALE` 或 `freshness=EMPTY`

### Requirement: 依赖分析 readiness 必须校验 x86 构建和目标环境
项目级 readiness 在 `stageId=rv-dependency-analysis` 时 SHALL 返回依赖分析所需前置条件。

#### Scenario: x86 构建已成功且目标环境存在
- **WHEN** 当前 Context 下存在成功的 x86 source-only 构建
- **AND** 项目已配置目标 RISC-V 运行环境
- **THEN** `X86_BUILD` 和 `TARGET_ENVIRONMENT` prerequisites SHALL 返回 `SATISFIED`

#### Scenario: x86 构建失败
- **WHEN** 当前 Context 下最近一次 x86 source-only 构建失败
- **THEN** `X86_BUILD` prerequisite SHALL 返回 `FAILED`
- **AND** `reasonCode` SHALL 为 `X86_BUILD_FAILED`

#### Scenario: x86 构建正在运行
- **WHEN** 当前 Context 下存在运行中的 x86 source-only 构建任务
- **THEN** `X86_BUILD` prerequisite SHALL 返回 `RUNNING`

#### Scenario: 目标环境不可用
- **WHEN** 项目配置了目标环境但环境被禁用或最近连接检查不可用
- **THEN** `TARGET_ENVIRONMENT` prerequisite SHALL 返回 `UNAVAILABLE`
