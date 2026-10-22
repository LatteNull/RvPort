## ADDED Requirements

### Requirement: 内存序分析必须使用统一项目入口
Worker SHALL 将共享 BC v2 适配为工具外部 bundle，创建 `UnifiedMemoryOrderAnalysisRequest v1`，并且只调用 `memory_order_analyzer analyze-project`，不得由 Java 编排工具内部分析阶段。

#### Scenario: 运行全部 Scope
- **WHEN** 当前源码版本具有成功 x86 构建、真实 compile database 和至少一个可用 BC record
- **THEN** 后端 SHALL 以 `scope_selection=all`、`source_assistance=auto` 和固定 policy 创建统一请求
- **AND** 工具 SHALL 自行编排内部阶段和内部 ArtifactKey

#### Scenario: 平台身份与工具身份隔离
- **WHEN** adapter 转换平台 record 和 scope
- **THEN** adapter SHALL 保留源码、编译、producer、target、ABI、profile、分母和 scope 语义
- **AND** MUST NOT 把平台 artifact key 冒充为分析器内部 ArtifactKey

#### Scenario: 开放 Scope
- **WHEN** v2 scope 声明 `closed=false`
- **THEN** 后端 SHALL 允许工具运行
- **AND** 最终 partial/frontier 语义 SHALL 由统一报告决定，不得伪造闭合范围

### Requirement: 内存序任务状态必须遵循统一报告和退出码
后端 SHALL 同时校验 `UnifiedMemoryOrderAnalysisReport v1` 的 status、verdict 和 exit_code，并使用工具定义的退出码语义结束任务。

#### Scenario: 受支持模型内未发现风险
- **WHEN** 工具返回退出码 0 和 `no-finding-within-supported-model`
- **THEN** 任务 SHALL 成功
- **AND** 前端语义 MUST NOT 被翻译为全程序安全或 thread-safe

#### Scenario: 发现正式风险
- **WHEN** 工具返回退出码 3 和 `risk`
- **THEN** 任务 SHALL 成功并发布 `task.succeeded`
- **AND** MUST NOT 因非零退出码进入重试或死信

#### Scenario: 部分或未知结论
- **WHEN** 工具返回退出码 2 和 partial、unknown、ambiguous 或可保留失败结果
- **THEN** 运行 SHALL 以 PARTIAL 结果可查询
- **AND** 后端 SHALL 保存已完成 Finding、source candidates、frontier 和 diagnostics

#### Scenario: 分析失败或状态冲突
- **WHEN** 工具返回退出码 1，或报告 status/verdict/exit_code 相互矛盾
- **THEN** 任务 SHALL 失败
- **AND** 后端 MUST NOT 把不完整输出提升为成功结论

### Requirement: 内存序结果必须区分风险、候选和审计信息
后端 SHALL 逐条保存正式 findings 与 source candidates，并使用 Finding kind、verdict 和 status 明确区分；discharged assessments、unsupported、frontier 和 diagnostics SHALL 作为审计信息保存。

#### Scenario: 导入正式风险 Finding
- **WHEN** 统一报告包含 `MemoryOrderFindingProjection` 且 verdict 为 risk
- **THEN** 后端 SHALL 保存风险、置信度、双语说明、位置、occurrences、evidenceChain、assumptions、limitations 和 semantic digest

#### Scenario: 导入源码候选
- **WHEN** AST-only 或证据不足产生 source candidate
- **THEN** 后端 SHALL 保留并标记为候选或不确定结果
- **AND** MUST NOT 将候选展示为已经证明的 runtime risk

#### Scenario: 保留证据断点
- **WHEN** Finding evidenceChain 包含 breaks 或 frontier
- **THEN** 详情 SHALL 返回对应断点、原因和双语建议
- **AND** 报告 SHALL 能说明置信度限制

### Requirement: 内存序分析必须保存完整审计目录
后端 SHALL 把统一报告、逐项 Finding、Scope execution、source snapshots、artifact index 和 data 审计文件作为受控结果 bundle 保存到对象存储，并生成轻量 HTML。

#### Scenario: 保存部分结果目录
- **WHEN** 某些 Scope 完成而其他 Scope 失败或取消
- **THEN** 后端 SHALL 原子保存工具发布的可审计输出树
- **AND** 查询 SHALL 返回完成与未完成 Scope 的分母

#### Scenario: 拒绝不安全输出引用
- **WHEN** 工具输出引用绝对路径、路径逃逸、链接或 digest 不匹配文件
- **THEN** 后端 MUST 拒绝导入结果
- **AND** MUST NOT 上传不安全文件到对象存储
