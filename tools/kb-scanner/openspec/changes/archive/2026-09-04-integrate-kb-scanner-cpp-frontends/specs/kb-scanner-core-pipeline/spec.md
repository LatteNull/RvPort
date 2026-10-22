## MODIFIED Requirements

### Requirement: Staged Pipeline 必须按确定顺序执行可替换阶段
KB Scanner 的 `StagedPipelineRunner` SHALL 按工作区采集、输入前端、事实归一化、关系分析、局部检测、分类、项目评估和兼容报告投影的顺序执行阶段，并 SHALL 通过显式 profile 或构造参数注入各阶段实现；正式 C/C++ Workspace Collector 与 Frontend SHALL 能作为该 profile 的真实组件运行，但在其余正式阶段尚未完成时，默认 CLI SHALL 继续选择独立的 legacy-compatible runner。

#### Scenario: 执行完整 pipeline
- **WHEN** 所有阶段均成功返回
- **THEN** orchestrator SHALL 按定义顺序把前序 scanner 自有结果传给后续阶段
- **AND** Report Projector SHALL 是写入正式 artifact 的唯一阶段

#### Scenario: 测试阶段编排
- **WHEN** 测试使用 recording stages 执行 pipeline
- **THEN** 测试 SHALL 能观察确定的调用顺序和输入传递
- **AND** orchestrator MUST NOT 通过隐藏的服务定位器或全局 plugin registry 选择组件

#### Scenario: 注入正式 C/C++ Frontend
- **WHEN** profile 使用正式 C/C++ Workspace Collector、Frontend 和 recording/no-op downstream components
- **THEN** StagedPipelineRunner SHALL 把真实 WorkspaceSnapshot 和 FrontendSnapshot 按合同传给后续阶段
- **AND** qualification 运行 MUST NOT 写入正式 artifact 或替代默认 CLI 报告

#### Scenario: 其余正式阶段尚未完成
- **WHEN** Knowledge、Normalizer、Detector、Classifier、Assessor 或兼容 Report Projector 仍缺少正式实现
- **THEN** 默认 CLI MUST NOT 切换到产生空检测结论的 staged profile
- **AND** scanner MUST NOT 把不完整 staged 运行呈现为完整成功扫描

### Requirement: Legacy compatibility profile 必须支持渐进迁移
默认运行 profile SHALL 通过 adapter 调用当前 compile command loader、项目解析、规则评估和报告逻辑，并 SHALL 把 legacy 私有状态限制在 adapter 内；当后续阶段提供正式新组件时，旧实现 SHALL 保持只读行为基线，不得为了适配新 core 合同而继续修改或把 legacy DTO 引入新组件。

#### Scenario: 使用默认 profile 扫描现有 fixture
- **WHEN** CLI 使用默认 compatibility profile 扫描任一现有规则 fixture
- **THEN** scanner SHALL 产生与当前实现语义等价的 Finding 和 Diagnostic
- **AND** legacy `ProjectFacts` 或其他私有 DTO MUST NOT 成为新 core protocol 的参数或返回类型

#### Scenario: 后续替换一个阶段
- **WHEN** 后续 change 为某一阶段提供正式新实现
- **THEN** pipeline SHALL 能通过 profile 替换该实现而不要求同步重写所有其他阶段
- **AND** 未替换的 legacy 行为 SHALL 保持可回归直至最终 cut-over

#### Scenario: 实现正式 C/C++ Frontend
- **WHEN** 新 frontend 需要 workspace、compilation context、源码事实或 diagnostic 能力
- **THEN** 实现 SHALL 在新的正式模块中直接产生 core 类型
- **AND** 实现 MUST NOT 修改或导入 legacy `compile_commands.py`、`cpp_frontend.py`、`models.py`、`rules.py` 或 `report.py`

#### Scenario: 旧行为存在缺陷或限制
- **WHEN** 新实现发现 legacy frontend 的 bug、误报或信息缺失
- **THEN** 该差异 SHALL 通过 baseline fixture 和迁移说明显式记录
- **AND** 修复 SHALL 进入新实现，不得通过修改旧代码制造兼容
