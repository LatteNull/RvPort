## 1. 协议、版本与固定语料

- [x] 1.1 为 `SharedBitcodeArtifactSet`、`LLVMFloatingPointFactBundle`、`FloatingPointEvidenceBundle` 和可选 binding sidecar 编写 Draft 2020-12 JSON Schema，固定 kind、独立版本、必填身份、预算字段、`additionalProperties: false` 和跨文档引用约束。
- [x] 1.2 对 scan request/result 做向后兼容的次版本演进，增加 `bitcode_artifact_set`、required profiles、source-mapping 要求、分层 summary/metadata，并保持现有 AST-only 请求可校验。
- [x] 1.3 扩展 schema registry、协议数据模型和 `version` 输出，分别公开 manifest、LLVM facts、evidence、sidecar、Clang 和 LLVM reader/extractor 版本；为未知字段、缺失字段、版本不兼容和多错误聚合编写单元测试。
- [x] 1.4 建立仅含本地固定数据的 C11、C17、C++17、C++20 artifact-set fixtures，覆盖 source-preserving、build-faithful、READY、PARTIAL、生产失败和显式 sidecar；记录二进制 BC 的生成命令、LLVM 版本、SHA-256 和更新审核方式。
- [x] 1.5 建立损坏、截断、空文件、错误摘要、错误 target/data layout、无 debug metadata、未知 intrinsic 和预算超限 fixtures，确保异常语料不会依赖公网、时间、locale 或宿主默认编译器。

## 2. 共享 artifact-set 消费

- [x] 2.1 实现只读 manifest loader 和不可变领域模型，验证 schema、manifest SHA-256、状态、成员分母、重复身份、artifact/context/physical TU identity 及稳定规划顺序。
- [x] 2.2 实现 artifact root 路径边界、普通文件、符号链接、相对路径、URL/凭据拒绝、size 和 SHA-256 校验；覆盖合法路径、路径穿越、越界链接、替换竞态和脱敏诊断单元测试。
- [x] 2.3 实现 source revision、compile database digest、规范化 context、语言、target、ABI、production/analysis compiler 与 source profile 的一致性验证，在任何 LLVM worker 启动前聚合确定冲突。
- [x] 2.4 实现 `source-preserving`/`build-faithful` required profile 规划和 capability 摘要；默认只要求 source-preserving，缺少未请求 profile 不降级，缺少必需 profile 保守计入 failed/unknown。
- [x] 2.5 实现 `READY`、可消费 `PARTIAL` 和不可消费 `MISSING/QUEUED/GENERATING/FAILED` 语义；未就绪返回 `retryable=true` 且不轮询、不编译 BC、不占用 LLVM worker。
- [x] 2.6 为相同 manifest 在不同 artifact root、不同成员排列和不同并发完成顺序下的身份、摘要、诊断及分母确定性编写单元测试。

## 3. 锁定 LLVM worker 与 canonical IR facts

- [x] 3.1 增加 `fp-ir-worker` 构建结构和锁定 LLVM 21.1.8 的 toolchain/容器配置，提供机器可解析的版本探针，禁止静默使用 PATH 中不匹配版本。
- [x] 3.2 定义最小版本化 worker request/response，完成 bitcode parse、LLVM verifier、artifact key/module SHA-256/target/data layout 回显和单 JSON stdout 协议；实现非零退出、崩溃和协议错误的稳定错误分类。
- [x] 3.3 提取并 canonicalize 浮点标量/向量类型、`fadd/fsub/fmul/fdiv/frem/fneg/fcmp`、phi/select 及浮点/整数转换，生成不依赖 LLVM 指针地址或容器遍历顺序的稳定 fact ID。
- [x] 3.4 提取普通 call、libm、`llvm.fma`/`llvm.fmuladd`、constrained FP、vector reduction、fast-math flags 和相关 function/module attributes，并为每类正常、边界及 unknown 语义编写 C++ 单元测试。
- [x] 3.5 提取规范化 debug file/range/scope 和完整 `inlinedAt` 链；缺失、越界或冲突 metadata 只影响位置/evidence，不删除已确认的 IR 操作事实。
- [x] 3.6 实现指令、facts、unknown、诊断、输出字节、wall time/CPU/内存预算和 frontier；预算耗尽返回有界 partial 协议，不产生“剩余模块无浮点行为”的结论。
- [x] 3.7 为 worker 的非法 bitcode、verifier 失败、不兼容版本、未知类型/intrinsic、无 debug、输出上限和确定性重复提取补齐 C++ 单元测试。

## 4. Python worker 适配与逐 TU 隔离

- [x] 4.1 实现可注入的 LLVM worker adapter，负责版本预检、受限子进程、超时/取消、stdout/stderr 字节限制、返回码分类和安全日志，不允许 worker 写入 artifact root 或加载项目动态库。
- [x] 4.2 对 worker 响应执行 JSON Schema、artifact key、module hash、target/data layout、producer/reader/extractor 版本和 semantic digest 复核，拒绝串线、陈旧或部分伪造输出。
- [x] 4.3 实现逐 artifact/profile 的失败隔离和确定性聚合；一个模块失败不影响其他模块，全部必需模块失败时为 `failed`，部分成功时保留 facts 并至少为 `partial`。
- [x] 4.4 使用 fake worker 覆盖启动失败、超时、取消、崩溃、非零退出、无效 JSON、超大输出、身份不符和并发乱序等正常/边界/异常单元测试。

## 5. AST↔IR evidence 融合

- [x] 5.1 扩展 source canonical facts 的稳定 TU/context、函数/符号和 spelling/expansion range 引用，但保持现有 AST bundle schema 兼容及相同输入确定性。
- [x] 5.2 实现 binding sidecar 的路径、schema、摘要、TU/context 和两端 fact ref 验证；无效 sidecar 不得产生 `explicit-sidecar` 绑定。
- [x] 5.3 实现同一 TU/context 内基于唯一函数身份、debug range、inline chain 与 AST spelling/expansion range 的结构化 derived matcher；禁止只凭函数名、demangled 文本或源码字符串相似度确定绑定。
- [x] 5.4 实现一对多、多对一、多对多、unbound、ambiguous 和 unavailable 关系，覆盖 FMA 融合、表达式拆分、内联、宏位置冲突、同一行多表达式和疑似优化删除路径。
- [x] 5.5 实现 evidence ID、排序、semantic digest、候选/输出预算和 frontier，使 materialization 根、输入排列和并发顺序不影响结果。
- [x] 5.6 为显式绑定、唯一 derived 绑定、digest/ref 冲突、歧义、缺少 debug、预算耗尽及 binding method 变化编写正常、边界和异常单元测试。

## 6. 应用编排、状态和输出

- [x] 6.1 扩展应用服务，在 AST-only 模式保持原行为；在 AST+BC 模式按“请求/manifest 校验→AST facts→LLVM facts→evidence→聚合”编排，任何缺失 BC 都不得触发本地 BC 编译。
- [x] 6.2 扩展 aggregation，使 artifact、source facts、IR facts 和 evidence 分别维护 planned/completed/failed/unknown 分母，并按 invalid_request/failed/partial/internal_error 规则保守合并。
- [x] 6.3 增加 artifact not ready、integrity、LLVM compatibility、verifier、worker、source mapping 和 profile capability 的稳定双语诊断、聚合计数、retryable 与建议动作，默认输出不泄露绝对路径或凭据。
- [x] 6.4 扩展结果 metadata 和原子输出，引用 artifact-set/bundle digest 而非可变路径，持续输出 `analysis_scope=facts_only`、`enabled_rule_count=0` 和空 `findings`。
- [x] 6.5 更新 CLI 适配和示例请求/结果，验证 AST-only、完整 AST+BC、PARTIAL artifact-set、未就绪、全部 worker 失败和未分类异常的退出码固定为 0/2/3/4/5 既有映射。

## 7. 测试、覆盖率与验收

- [x] 7.1 补齐 Python 项目全部新增/修改模块的单元测试，覆盖正常、边界和异常路径；集成测试、真实 Clang/LLVM 编译、schema 校验和静态检查不得替代单元测试。
- [x] 7.2 使用锁定 Clang/LLVM 21.1.8 执行 C11、C17、C++17、C++20 本地集成验证，覆盖算术、比较、转换、FMA、fast-math、constrained FP、libm、向量归约、宏、内联和无 debug，并核对固定 oracle。
- [x] 7.3 执行不同 artifact root、重复扫描、成员乱序、部分失败、取消和预算注入验证，证明 facts/evidence 身份、semantic digest、排序和安全失败语义可重复。
- [x] 7.4 配置并实际运行 Python coverage.py `branch = true` 门禁，将未被测试加载的全部项目自有 Python 源码纳入分母，确认项目整体与受影响 Python 模块 line/branch 四项均以未四舍五入值达到 90%。
- [x] 7.5 配置并实际运行 C++ worker 的 LLVM coverage/`llvm-cov` 门禁，将全部项目自有 worker 源码纳入分母，确认 worker 整体与受影响模块 line/branch 四项均达到 90%；仅排除第三方 LLVM、纯生成文件和固定二进制 fixture并记录理由。
- [x] 7.6 更新 README、设计/协议说明和验证报告，记录消费者范围、上游 producer 前置依赖、AST-only 与 AST+BC 用法、profile 区别、失败状态、实际测试命令、测试数量、覆盖率数值、统计范围、排除项及报告位置。
- [x] 7.7 运行所有单元测试、锁定工具链集成测试、schema/example 校验、格式/静态检查、覆盖率门禁及 `openspec validate consume-and-scan-shared-llvm-bitcode --strict --no-interactive`；任何测试失败或 line/branch 低于 90% 时不得完成质量任务或归档 change。
