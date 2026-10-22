## ADDED Requirements

### Requirement: Preserve evaluation frontiers in final completeness

最终报告 SHALL 保留局部求值 request_hash、依赖代际和 pending/unknown 前沿的可追溯关系；局部结果 partial/failed/not_run、相关未知候选或未稳定调用 SHALL 不能因空 effects 或过滤计划升级为 complete。块 unreachable SHALL 具有显式证明。

#### Scenario: Local evaluation stops before visiting a block

- **WHEN** 工作或输出预算阻止完成一个已计划局部请求
- **THEN** 报告保留未完成请求及原因、已知可用结果与非 complete 状态，不把未访问块算作不可达或缩小分母

### Requirement: Require an explicit effect-analysis request

系统 SHALL 提供新增 summarize 命令，接受 EffectAnalysisRequest v1、artifact store、新输出目录和分析 worker；请求 SHALL 引用显式 scope，并在非空入口 ID 集合和显式 all-defined 模式中二选一，记录策略/预算和入口实参。SHALL 不默认 main、目录全体 BC 或编译数据库为程序，不要求链接/运行被分析应用；旧命令不隐式启动摘要分析。

#### Scenario: A user selects explicit roots

- **WHEN** 请求提供合法 scope、artifact/function ID 入口和支持的抽象实参
- **THEN** 按入口及可达调用生成摘要，报告入口/范围选择；不把 scope 中所有函数都当作该入口必然执行

#### Scenario: Roots are missing or invalid

- **WHEN** 请求既没有有效入口也没有显式 all-defined，或混用两模式、含非成员函数/不合法绑定
- **THEN** 拒绝请求并给出结构合法错误报告，不猜入口或以空计划声称完成

### Requirement: Report layered completeness without safety verdicts

EffectAnalysisReport v1 SHALL 分别报告 input_integrity、raw_fact_extraction、local_analysis、interprocedural_analysis 和 source_mapping，以及完整性原因、支持策略和假设；分析状态 SHALL 区分 complete/partial/failed/not_run。SHALL 保留 raw unknown 及其已解释/已证不相关证据，不改历史 RunReport；所有结果 SHALL 保持 safety=not_evaluated、findings=null，不输出竞争/HB/内存模型安全结论。

#### Scenario: Raw ABI facts are partial but a context is understood

- **WHEN** raw extraction 因 ABI unknown 为 partial，而补充分析已合法解释相关属性且请求上下文没有剩余局部缺口
- **THEN** 原始 partial 和解释证据同时保留，可单独报告该局部/上下文阶段 complete，不把原始报告改写成已完整提取

#### Scenario: Summaries contain no externally visible writes

- **WHEN** 请求的受支持函数只产生局部效果或没有可见写
- **THEN** 仅报告范围内的效果分析结果，safety 仍 not_evaluated、findings 为 null，不输出安全或零风险声明

### Requirement: Account for planned members and unexpanded analysis frontiers

报告 SHALL 保留完整 scope 成员与入口计划，以及读取/局部完成/部分/失败/未运行、已发现/处理/截断上下文、未展开前沿、未知调用/对象和定位统计。SHALL 明确各分母，零分母为 null，已发现上下文数不得冒充所有可能上下文总数；失败成员和预算未执行项不得从计划消失。

#### Scenario: One of three planned modules cannot be processed

- **WHEN** scope 计划 3 个成员，其中 1 个缺失或局部分析失败，其他成员可产出合法摘要
- **THEN** 报告计划 3 和该失败项，保留可用结果及受影响调用的 unknown，整体 partial，不以成功 2 个重算为完整输入

#### Scenario: A context limit leaves undiscovered descendants

- **WHEN** 上下文预算阻止展开后续调用
- **THEN** 报告已发现计数、未展开前沿和未知剩余规模，不把未发现部分记成零或显示全部上下文完成

### Requirement: Return effect-analysis exit statuses and durable evidence

summarize SHALL 在请求完成且无相关完整性/来源/定位缺口时退出 0；有可用摘要但 partial/unknown、来源或定位缺口、预算截断时退出 2；非法请求或全部不可用时退出 1。SHALL 尽力保存合法报告、摘要引用、原始 IR 与调用链证据，stdout 仅 JSON、stderr 为日志，不改旧 collect/index/link 退出语义。

#### Scenario: Debug information is absent

- **WHEN** 有效输入能够产生 IR 效果摘要但没有 debug 位置
- **THEN** 保留 IR 与调用链证据，source_mapping unavailable、退出 2，不猜源码位置或将局部语义结果伪称失败

#### Scenario: A worker fails after other roots succeed

- **WHEN** 部分入口已产生可用结果，另一个 worker 超时/输出超限或失败
- **THEN** 保留成功摘要和失败项，输出合法 partial 报告并退出 2，不以最后一个成功进程退出码代替请求结果

### Requirement: Document support boundaries and reproducible validation

系统 SHALL 交付 doc/EFFECT_SUMMARIES.md 和 doc/EFFECT_SUMMARIES_VALIDATION.md，记录 P1 缺口与 P2 补齐对应关系、协议/CLI、支持/不支持矩阵、策略预算、标准库实际包版本/hash、复现输入、测试命令及结果。SHALL 区分历史观察、当前实测、设计和 unknown，校验文档链接，并保留已有 compile-only、ARM/mm-check 历史证据含义。

#### Scenario: Validation records atomic-wrapper support

- **WHEN** 固定 O0 atomic 包装通过新语义验收
- **THEN** 文档列出源码/IR 证据、工具和标准库版本、对象/order/路径断言，不把一次编译或历史集成通过当作摘要正确性证明
