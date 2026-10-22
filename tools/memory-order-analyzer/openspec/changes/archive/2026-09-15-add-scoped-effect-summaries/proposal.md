## Why

P1 已提供原始值、条件 CFG、调用接口和内存范围事实，但这些事实**不足以直接完成 P2 推理**：O0 栈槽传播、精确 linkage/函数体采用条件、结构化 ABI 解释等仍缺失。为实现 P2，本 change 同时补齐这些前置能力并实现显式 scope 内的参数化效果摘要，避免把未知调用、不可达原子分支或未分析范围误当成确定效果。

## What Changes

- 这是**运行时实现 change**，本次 propose 仅生成实施契约，不表示任何 P2 能力已实现。
- 补齐 P1 尚未具备、P2 必需的 LLVM 局部分析：精确 linkage、visibility/dso-local/可替换性及函数体采用证据、函数与调用点 ABI/控制属性分类、局部对象分配范围、受限非逃逸栈槽值传播。原有 raw unknown 不被覆盖或删除。
- 使用锁定 LLVM 21.1.8 的局部分析和精确整数语义；自研有界符号值/对象域、路径筛选及效果提取，不实现通用 points-to。
- 增加 P2 独立 `ir_nodes` 与 `analysis_evidence` 登记：前者复用原始指令 ID（包括未进入 P1 根闭包的指令），后者使用显式 analysis_id 命名空间。摘要/报告以补充产物 digest 绑定证据代际；不把 LLVM 生成节点混入 P1 v2。
- 按 2026-09-14 批准增加独立 `LocalEvaluationRequest v1` / `LocalEvaluationResult v1`：将按上下文绑定的求值与模块元数据缓存分离；定义带 guard 的有限候选、内部 bottom 与发布 unknown、输入/结果绑定、完整依赖快照及结构预算。外层入口仍用单值/符号模板，不开放任意带 guard 候选输入；局部调度协议允许经过校验的有限候选。
- 新增参数化读写/原子/屏障候选、返回关系、逃逸和未知效果摘要，保留条件、事件顺序、may/must 区分及原始证据。
- 明确区分可复用摘要上下文与有限抽象调用/分配实例：相同实参的不同调用位置可复用模板，但必须重新绑定局部对象、guard、返回和 escape；循环、递归和预算合并记录非单例语义，不凭合并身份证明别名、互斥或强更新。仅修订尚未发布的 P2 v1 草案，P1 v2 不变。
- 在显式 scope 中复核直接调用的接口与函数体采用条件，完成跨 TU 实参替换、返回传播、调用点特化、递归 SCC 固定点及预算降级。为满足已实测 atomic 包装，增加严格受限的 ODR 函数体语义采用通道，不把 weak/COMDAT 选择普遍视为已解析。
- 新增独立的 `LocalAnalysisFacts v1`、`EffectSummary v1`、`EffectAnalysisReport v1` 和分析请求/策略协议；保持 `ModuleFacts v2`、`RunReport v2`、现有 `ScopeIndex v1` 的原始含义、历史文件和旧命令行为。派生产物单独校验、缓存和声明能力。
- 新增显式请求的 `summarize` CLI（待本 change 实现），分别报告输入质量、局部分析、过程间摘要及截断原因；始终 `safety=not_evaluated`、`findings=null`。
- 增加自有代码单元测试，执行项目整体、每语言及逐模块行/分支覆盖率至少 90% 的现有门槛；纳入未加载代码和新增子目录/可执行头文件，集成测试与单元覆盖统计分离。
- 暂不实现线程/MHP/HB、reads-from 求解、风险判定、自动修复、通用指针分析、外部分析后端或生产/开发 Dockerfile 合并。继续限定 GCC/Clang 用户态 C/C++、compile-only，独立开发容器和离线验收。

## Capabilities

### New Capabilities

- `llvm-local-effect-analysis`: 经 BC 身份校验的 LLVM 局部补充事实、精确 ABI/linkage、受限对象与值传播、路径及局部完整性。
- `scoped-effect-summaries`: 参数化效果、确定直接调用的跨 TU 组合、调用上下文特化、递归预算和派生缓存。
- `effect-analysis-reporting`: 显式摘要分析请求、独立报告、完整计划统计、分层状态、证据和退出语义。

### Modified Capabilities

- `scoped-module-association`: 新增独立派生层的直接调用资格复核及受限 ODR 函数体采用规则；不放宽既有原始索引的 weak/COMDAT 保守行为。
- `analysis-integrity-reporting`: 增加 P2 kind 的独立版本、跨产物引用及缓存隔离规则；保留全部 P1 报告与提取状态语义。
- `analyzer-unit-test-quality`: 增加 P2 全源码枚举、语义负例、递归/预算及兼容性验收，延续既有整体/语言/逐模块 90% 门槛。

## Impact

- 预计涉及本项目 `src/` 的局部分析与 worker 接口、`python/memory_order_analyzer/` 的派生协议/绑定/摘要/CLI/报告/缓存/质量逻辑、`schemas/`、CMake 目标与测试枚举、`tests/` 和 `doc/`。具体拆分见 [design.md](design.md)，不依赖 archived 兄弟项目。
- 使用现有 LLVM 开发依赖，不强制引入 SVF、PhASAR、SMT、DevKit 或网络服务。原始 BC 不需要先 llvm-link，更不需要原生链接或运行被分析程序。
- 新产物与旧接口并存，不以添加字段的方式静默改变 v2 schema。旧消费者不支持新 kind 时明确拒绝；新增局部分析协议不触发无关 BC 重新编译或 P1 ArtifactKey 重键。
- 文档将记录此前探索的 Clang C++20/std::atomic O0 栈槽、ODR 辅助调用及 ABI unknown 观察，同时新增固定输入复现；历史一次集成通过不是新能力、覆盖率或检测正确性的证据。
