# memory-order-evidence-documentation

## Purpose

规范内存序语义、实验溯源、DevKit 待验证状态和文档导航，区分已观察事实、官方资料与未来分析器设计，防止过度解读结果。

## Requirements

### Requirement: Keep roadmap and navigation aligned with archived P4 and active P5

项目路线图、README 和文档索引 SHALL 明确 P4 `detect-single-publication-risks` 已实现、质量验收、同步并归档，登记 P5 `validate-and-scale-analysis` 的实际 proposed/applying/validated/archived 状态及边界；不得继续显示 P4 待 sync/archive，也不得把提案状态写成已实现。

#### Scenario: A reader follows the roadmap after P5 proposal

- **WHEN** 读者从 README 或 `doc/IMPLEMENTATION_ROADMAP.md` 查看阶段状态
- **THEN** 能定位 P4 归档、P4 使用/验证文档和当前 P5 change，并清楚区分已完成与计划能力

#### Scenario: P5 has not run an optional backend

- **WHEN** GenMC、herdtools7 或新 DevKit 实验未执行
- **THEN** 文档标为 not_run/待验证，不使用设计计划或历史结果冒充本轮观察

### Requirement: Document P5 evidence layers and reproducible validation

文档 SHALL 分开描述人工 truth、P1–P4 observation、真实工程人工抽样、外部 backend comparison、性能/缓存测量和后续决策，提供版本/hash、命令、分母、报告入口和限制。准确率只引用完整人工 truth 分母；真实工程样本、DevKit success、BC 编译、零 finding 和工具一致 MUST NOT 表述为全工程准确率或并发安全证明。面向用户的诊断和建议示例 SHALL 同时给出中文和英文字段。

#### Scenario: Validation results are published

- **WHEN** P5 离线语料和真实工程基线完成
- **THEN** `doc/VALIDATION_AND_SCALING_VALIDATION.md` 记录精确环境、命令、hash、truth/观察/抽样/性能结果、覆盖率及报告位置，并链接自 README 与文档索引

#### Scenario: A real-project sample looks accurate

- **WHEN** 已裁决样本全部与 P4 一致但未穷尽工程真值
- **THEN** 文档只报告样本分母与选择方法，不外推 100% precision/recall 或安全结论

### Requirement: Distinguish memory-model semantic layers

文档 SHALL 区分 C/C++ 语言模型、LLVM IR 语义和硬件内存序，说明普通数据竞争、全原子协议顺序风险和目标硬件迁移风险的差别；SHALL 解释 atomic/fence、线程入口、共享对象、锁、reads-from 与 happens-before 的联系及未建模边界。

#### Scenario: IR contains atomic operations and fences

- **WHEN** 读者在 BC 中观察到 atomic 或 fence
- **THEN** 文档说明其存在不等于已经建立跨线程同步，并明确 volatile、编译器屏障和信号 fence 不能直接替代通用线程同步

#### Scenario: Optimization changes visible accesses

- **WHEN** 同一示例在 O0 和优化配置下的 IR 不同
- **THEN** 文档结合源语义与编译配置解释差异，不将被优化掉的普通访问解释为原程序已无并发风险

### Requirement: Preserve experiment provenance and scope

文档 SHALL 将本地实测、官方资料、设计建议和待验证结论分开标注；SHALL 保留现有实验的日期、环境、源文件、命令、原始 JSON 入口、27 个 BC 模块和 74 项检查的统计含义，并区分示意命令与实际执行命令。

#### Scenario: Summarize the existing Clang experiment

- **WHEN** 文档引用 2026-09-10 的 Clang 18.1.3 结果
- **THEN** 文档可追溯到 `doc/experiments/results/clang18-evidence.json`，且不将 74 项检查表述为缺陷检测准确率、完整验证或程序安全证明

### Requirement: Keep DevKit observations separate from validation plans

文档 SHALL 保留有日期的 SSH 网络阻塞历史，并按日期区分新 ARM/DevKit 实测、对应版本官方流程和剩余待验证项；SHALL 纳入 2026-09-11 DevKit 25.3.0、自带 LLVM 16.0.4 的代表证据及完整性限制，不再把已执行项目统一标为待验证。SHALL 保留版本探测、BC 接受、跨模块输入和报告解释矩阵，不以在线远端连接作为本 change 的日常或归档验收前提。

#### Scenario: No new ARM validation evidence is collected

- **WHEN** 某次文档整理没有执行新的 ARM/DevKit 实验
- **THEN** 只引用此前有日期和来源的历史记录，不声称该次重新确认了当前网络状态或工具行为

#### Scenario: Preserve the September 11 experiment evidence

- **WHEN** 纳入 2026-09-11 的实测
- **THEN** 保存环境、命令、源码/产物 hash、代表原始报告与完整矩阵入口，说明 47 份 success 报告不是检测正确率、322 文件 hash 验证不是单元覆盖率，并区分提交的证据子集与完整原包

#### Scenario: Interpret independent and linked bitcode results

- **WHEN** 文档比较三个 object BC 的零建议与 linked BC 的 2/3/4 条建议
- **THEN** 明确三个 TU 来自同源码不同 PART 配置，结论限定该样例，说明同目录扫描未自动恢复所需关联，不声称已经验证所有跨文件能力

#### Scenario: Compiler exit zero or scanner success is misleading

- **WHEN** 引用 bc-gen 零退出零产物、缺 debug 零建议或正确同步仍被建议插入屏障的结果
- **THEN** 文档分别说明产物/定位/语义判定限制，不把 mm-check 作为 C/C++ 并发正确性 oracle 或自动修复依据

### Requirement: Explain coverage before interpreting findings

文档 SHALL 区分构建覆盖和分析完成度，并说明缺失 TU、外部实现、未建模同步与超时等对结论的限制。

#### Scenario: A partial analysis reports zero findings

- **WHEN** 编译不完整或分析存在未知行为且报告零告警
- **THEN** 文档明确零告警仅描述已覆盖范围内的结果，不能解释为全程序并发安全

### Requirement: Provide discoverable and consistent documentation

项目 README 和文档索引 SHALL 链接构建上下文、跨 TU、BC 流水线、分析设计、实验与 DevKit 专题，并增加实际实现的开发容器、CLI/schema 和测试验收入口；文档 SHALL 保持阶段说明、统计值、状态和术语一致，对外部技术结论标注出处及版本，对本地文件提供有效链接。SHALL 区分已完成基础设施与未实现的线程/别名/内存序判定，不依赖归档项目。

#### Scenario: Follow the documentation entry point

- **WHEN** 新读者从项目 README 进入文档
- **THEN** 可找到各专题、实测证据、开发镜像构建和测试命令，并明确当前只实现已验收的基础设施，尚不能输出并发安全结论

#### Scenario: Development image is delivered before production consolidation

- **WHEN** 本 change 已完成独立开发镜像构建验证
- **THEN** 文档记录该完成状态和复现命令，同时明确与生产 Dockerfile 的合并属于后续 change，不将两项工作混为未交付或已合并

### Requirement: Document the AST and IR authority boundary

项目 SHALL 在 README、文档索引、路线图和 `doc/AST_CROSS_TU_EVIDENCE.md` 说明 source facts、program entity、AST–IR binding、LLVM memory facts、P3 execution relations 与 P4 publication conclusions各自能证明和不能证明的内容，并明确 `compile_commands.json` 不是 target/link 图、AST source order 不是 SB/SW/HB、BC 编译或零 finding 不是安全证明。

#### Scenario: A reader follows one cross-TU finding

- **WHEN** 读者查看文档中的跨 TU publication 示例
- **THEN** 能从 source declaration/definition、canonical object、IR access、thread relation 到 finding 逐层定位证据和 unknown 边界

### Requirement: Publish reproducible AST-assisted validation results

`doc/AST_CROSS_TU_EVIDENCE_VALIDATION.md` SHALL 记录实际环境、锁定 Clang/LLVM 与输入 hash、命令、测试/覆盖率分母、IR-only 与 AST-assisted truth 指标、source/binding 完整性、TinyCThread cold/warm 性能/缓存、未运行项和限制；未执行结果 MUST 标为 not_run。面向用户的诊断、原因与建议示例 SHALL 同时提供中文和英文字段。

#### Scenario: Validation is not yet complete

- **WHEN** 任一 90% 覆盖率、truth、确定性、真实工程或文档门禁尚未通过
- **THEN** 文档标明实际失败/未运行状态，不写成已实现、已验证或可归档

#### Scenario: AST-assisted exact match improves

- **WHEN** 固定 truth 中的实际指标优于 IR-only 基线
- **THEN** 文档发布精确 case/分母和代价，同时保留非全程序安全声明及未支持 fence/RMW/std::thread 边界
