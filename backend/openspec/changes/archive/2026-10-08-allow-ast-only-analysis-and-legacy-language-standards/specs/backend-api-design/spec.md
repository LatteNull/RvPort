## MODIFIED Requirements

### Requirement: API 必须提供专项分析 readiness 和 latest
项目级 readiness SHALL 支持 `floating-point-analysis` 与 `memory-order-analysis`，领域 latest SHALL 使用统一响应外壳并返回当前运行、当前源码、分析模式、BC 覆盖和失效或降级原因。BC 可用性 SHALL 表达证据能力，不得在源码、成功 x86 构建、真实 compile database 和工具均可用时单独阻断任务创建。

#### Scenario: readiness 返回完整前置事实
- **WHEN** 用户查询任一专项分析 stage readiness
- **THEN** 响应 SHALL 列出源码、x86 构建、compile database、工具可用性以及该领域额外 profile 条件
- **AND** 响应 SHALL 返回建议执行模式 `AST_ONLY`、`AST_BC_MIXED` 或 `AST_BC_COMPLETE`
- **AND** 响应 SHALL 返回 BC 状态、计划、可用和失败翻译单元计数及稳定降级原因码

#### Scenario: BC 不可用但 AST 前置满足
- **WHEN** 当前源码、成功 x86 构建、真实 compile database 和分析工具可用，但 BC 缺失、失败、损坏或没有 produced record
- **THEN** readiness 的硬前置条件 SHALL 保持满足
- **AND** 建议执行模式 SHALL 为 `AST_ONLY`
- **AND** 响应 MUST NOT 将 BC 降级描述为整个分析不可用

#### Scenario: 部分 BC 可用
- **WHEN** BC artifact set 仅有部分翻译单元可用
- **THEN** readiness SHALL 返回 `AST_BC_MIXED`
- **AND** SHALL 返回 AST-only 与 AST+BC 的翻译单元分母

#### Scenario: latest 和详情公开实际模式
- **WHEN** 用户查询专项分析 latest、运行详情或列表
- **THEN** 运行响应 SHALL 返回实际 `analysisMode`、BC 状态、BC 覆盖计数和降级原因
- **AND** 无 artifact set 的 AST-only 运行 SHALL 允许 `artifactSetId` 为空

#### Scenario: 执行时重新校验
- **WHEN** readiness 查询后源码、构建、compile database、BC 或工具状态发生变化
- **THEN** 创建 API SHALL 重新校验硬前置事实并重新计算分析模式
- **AND** 仅硬前置不满足时 SHALL 返回 `PREREQUISITE_NOT_SATISFIED`
- **AND** BC 从可用变为不可用时 SHALL 安全降级为 AST-only 并记录原因

## ADDED Requirements

### Requirement: 专项分析 API 必须准确表达旧标准处理结果
专项分析运行和结果 API SHALL 保留工具识别到的语言、基础标准、方言和标准来源，并 SHALL 对不支持的单翻译单元返回稳定诊断。

#### Scenario: 返回旧标准分析摘要
- **WHEN** 项目包含 C89/C99 或 C++98/C++03 翻译单元
- **THEN** 运行详情 SHALL 能返回实际识别的标准及 GNU/ISO 方言摘要
- **AND** MUST NOT 将其显示为 C17 或 C++17

#### Scenario: 单翻译单元不受支持
- **WHEN** 某个编译上下文无法由锁定 Clang 或规则可靠处理
- **THEN** API SHALL 在结果中返回该翻译单元的 unknown 或 unsupported 诊断及双语说明
- **AND** 其他翻译单元结果 SHALL 保持可查询
