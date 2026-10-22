## Why

当前浮点精度扫描器只从 Clang AST 生成源码语义事实，无法确认 FMA、fast-math、浮点转换、向量归约和数学函数调用在 LLVM IR 中的实际形态；如果各分析模块自行重新生成 BC，还会产生重复编译、并发争用和证据身份不一致。需要让扫描器消费 x86 构建流程统一发布的不可变共享 BC，在不拥有 BC 生产和平台调度职责的前提下，形成可复用、可校验且能回溯源码的 LLVM 浮点事实。

## What Changes

- 增加版本化共享 BC artifact-set manifest 的消费协议；扫描器只接受状态为 `READY` 或可保守消费的 `PARTIAL` 制品，并在读取前校验源码版本、编译数据库摘要、artifact/context 身份、profile、toolchain、target/data layout、文件大小和 SHA-256。
- 增加锁定 LLVM 21.1.8 的 bitcode reader/worker，从逐翻译单元 BC 提取浮点类型、算术与比较、转换、call/intrinsic/libm、FMA、fast-math flags、向量浮点与归约、module/function 属性及 debug location 等 canonical IR facts。
- 分离 AST/source facts、LLVM IR facts 和二者的 evidence binding；通过稳定翻译单元、函数/符号身份、源码位置、inline/macro 链及显式 sidecar 关联证据，无法可靠关联时保留 `unknown`，不以名称或文本相似度猜测。
- 扩展扫描请求、结果元数据、版本输出和失败语义，使 artifact not ready、manifest/BC 损坏、哈希或 target 不一致、LLVM 不兼容、verifier 失败、缺少 debug location、部分翻译单元失败、预算耗尽和取消均可审计。
- 保留现有 AST canonical facts 链路；本 change 只产生 LLVM facts、融合证据和诊断，继续保持 `findings=[]`、`analysis_scope=facts_only`，不实现具体浮点风险规则。
- 规定托管模式不得重新生成共享 BC，也不得轮询等待；x86 构建后的 BC 生产、single-flight registry、不可变对象存储、`BC_ARTIFACT_READY` 事件和下游任务等待/恢复由独立上游 change 提供。
- 为正常、边界、异常和并发契约路径补充单元测试与固定 BC fixtures，项目整体及受影响模块的行覆盖率、分支覆盖率均至少 90%。

## Capabilities

### New Capabilities

- `shared-bitcode-artifact-consumption`: 定义共享 BC artifact-set manifest 的版本、身份、完整性、profile/capability、状态、读取边界及不可变消费规则。
- `llvm-floating-point-facts`: 定义从锁定 LLVM bitcode 提取 canonical 浮点 IR facts、unknown、预算、确定性身份和逐翻译单元失败隔离。
- `ast-ir-floating-point-evidence`: 定义 AST/source facts 与 LLVM IR facts 的可靠绑定、provenance、歧义传播和融合证据协议。

### Modified Capabilities

- `scanner-io-contract`: 扩展 scan request/result，使请求可引用共享 BC manifest，结果公开 artifact/facts/evidence 摘要及相应分母。
- `scanner-failure-semantics`: 增加共享制品未就绪、陈旧、损坏、不兼容、验证失败、源码映射不足和部分 BC 可用时的保守状态语义。
- `scanner-runtime-foundation`: 版本输出和 facts-only 执行范围增加 BC manifest、LLVM facts、evidence schema 及锁定 LLVM reader 版本。

## Impact

- 影响 `src/floating_point_precision_scanner/` 的协议、CLI 编排、应用服务、前端端口、facts、aggregation、diagnostics 和输出层，并新增独立的 bitcode consumer、LLVM worker adapter 与 evidence binding 层。
- 新增 BC artifact-set、LLVM floating-point facts 和 AST↔IR evidence 的 Draft 2020-12 JSON Schema、固定 C/C++/LLVM fixtures、consumer contract tests 及覆盖率门禁用例。
- scan request/result 和 version 输出发生向后兼容的次版本演进；现有 AST-only 本地输入仍保留，但没有共享 BC 时不得声称已经完成需要 IR 证据的分析。
- 外部依赖是上游 x86 构建/平台提供不可变共享 artifact-set；本 change 不修改后端任务状态、对象存储、x86 构建流程，也不迁移强弱内存序分析器。
- 首期只兼容项目锁定的 Clang/LLVM 21.1.8 BC；跨 LLVM 主版本读取、linked whole-program BC、LTO 和具体风险规则不在范围内。
