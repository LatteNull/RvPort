## Why

zlib 的 Schema V2 报告将 9 条 ARM CRC32 内联汇编膨胀为 63 条 `candidate-evidence-not-sufficient`，并把通用 `no_sanitize` 属性也展示为架构候选。这说明当前结构 Evidence 边界、目标架构判别和候选分类之间缺少约束，导致 x86→RISC-V 报告被非 x86 内容和重复 AST 子节点淹没。

## What Changes

- 将一条内联汇编语句规范为一个最外层、完整且精确定位的 Evidence，不再为 qualifier、输入/输出 operand 等嵌套节点重复建证据。
- 为内联汇编候选增加保守的架构归属判别：已确认属于 ARM、RISC-V 或其他非 x86 架构的汇编不得进入 x86 finding；无法归属的汇编仍可保留为明确的低置信候选，不能伪装成已确认 x86 依赖。
- 收紧 declaration attribute 候选规则，只有 target、target_clones、vector_size 或知识集中可识别的架构/目标特性语义才能进入架构检测；`no_sanitize` 等通用属性不得产生架构 finding。
- 调整候选分类和投影语义，使 `candidate-evidence-not-sufficient` 只表示真正存在未决架构相关性的证据，禁止把已识别的非 x86 内容或无架构语义的通用语法投影为 x86→RISC-V finding。
- 为 Frontend、Normalizer/Detector、Classifier/Projection 的每个修改模块补齐隔离单元测试，并在独立 `kb-scanner-test` 容器内执行 90% 行覆盖率、80% 分支覆盖率门禁。
- 增加 zlib 回归：固定 ARMCRC32 代码、通用属性、真实 x86 宏混合分支及未知汇编正例，验证去重、排除、保留和确定输出；同时固定 finding/Evidence 数量上限，防止候选再次爆炸。
- 保持静态分析边界，不执行配置、编译、链接或测试；不涉及操作系统迁移、生产镜像、根 Compose 或后端改造。
- 保持现有 `scan-result.json` Schema V2 默认输出、显式 V1 兼容，以及 `scan-report.html`、`scan.log` 三类 artifact，不引入新的结果结构；Clang/GCC 编译器事实数据保持不变。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `kb-scanner-cpp-frontends`: 收紧 inline asm 与 declaration attribute 的 Evidence 粒度和语义边界，保证单语句单证据且不宽泛采集属性内部节点。
- `kb-scanner-knowledge-and-local-detection`: 增加内联汇编架构归属和通用属性过滤合同，区分已确认 x86、已确认非 x86 与真正未知候选。
- `kb-scanner-classification-and-assessment`: 限制 `candidate-evidence-not-sufficient` 的适用条件，确保非 x86 或无架构语义证据不影响迁移结论。
- `kb-scanner-compatible-projection-and-cutover`: 保持 V2 默认/V1 兼容结构，同时禁止将被过滤的候选重新投影为 finding，并维持稳定去重身份。

## Impact

- 主要影响 `kb_scanner/frontends/cpp/tree_sitter_adapter.py`、C/C++ normalizer、本地 detector、migration classifier 和 V2/V1 projection policy。
- 需要扩展 zlib/inline-asm/attribute fixture、模块级测试清单、容器覆盖门禁和兼容回归。
- 预期 zlib 预览报告从 63 条重复 ARM asm candidate 与 1 条通用属性 candidate 收敛为零条对应 x86 finding；真实 `__x86_64__` 条件仍保留并按 RISC-V 可达性分类。
- 不改变 `rulesets/riscv-porting/generated/clang-x86-entries.json`、`gcc-x86-entries.json`、知识集引用方式或正式 artifact 名称。
