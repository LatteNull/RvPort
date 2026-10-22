## Context

当前 Tree-sitter adapter 以 `"asm" in node.type` 识别内联汇编，因此一条 GNU asm 会同时为 statement、qualifier、output operand、input operand 等父子节点生成 Evidence。Local Detector 又为任何 `inline_asm` 和任何 `declaration_attribute` 提供 structural candidate 兜底；当这些 Evidence 没有匹配 x86 知识时，Classifier 最终统一给出 `candidate-evidence-not-sufficient`。

在 zlib `crc32.c` 的 ARMCRC32 分支中，9 条 AArch64 `crc32x/crc32b` 指令被展开为 63 条候选，`no_sanitize("memory")` 又产生一条无架构语义的属性候选。唯一有 x86 语义的 `defined(__x86_64__) || defined(__aarch64__)` 已能正确归类为 RISC-V 下 inactive。这说明现有链路需要保留真正未知的风险，但必须在 Evidence 粒度、分支归属和候选准入处排除确定的干扰项。

约束如下：

- 仅做静态 C/C++ 分析，不执行预处理、配置、编译、链接或测试；不分析 OS、内核、驱动或板级迁移。
- 保留现有 Clang/GCC x86 generated facts、curated knowledge 和 manifest；不在代码中隐藏新增的指令词表。
- Schema V2 继续默认，显式 V1 继续兼容；仍只生成 `scan-result.json`、`scan-report.html`、`scan.log`。
- 所有依赖和测试只在独立 `kb-scanner-test` 容器中运行，不修改宿主机、生产镜像、根 Compose 或后端。

## Goals / Non-Goals

**Goals:**

- 将每条内联汇编规范为一个完整、可定位、确定性 Evidence。
- 依赖已有知识与可证明的分支上下文区分 x86、明确非 x86 和真正未知的汇编/属性。
- 只让真正未知的架构候选进入 `candidate-evidence-not-sufficient`，从 V2/V1 finding 中排除 ARM 分支和通用属性噪声。
- 用 zlib ARMCRC32 回归固定修复后的 Evidence/Finding 数量和报告语义。
- 为每个修改模块提供隔离单元测试和 90% line / 80% branch 门禁。

**Non-Goals:**

- 不建设完整的 ARM、PowerPC、S390 或其他架构指令知识库。
- 不承诺仅凭未知汇编文本判断其真实目标架构；证据不足仍保持 unknown，而不是声明安全。
- 不进行真实 RISC-V 编译或运行验证，不修改 build selection 对交叉编译的既有假设。
- 不设计新报告 schema，不修改后端消费逻辑，不清理旧知识资产。

## Decisions

### 1. Frontend 只为最外层可执行 asm 构造生成 Evidence

Tree-sitter adapter SHALL 使用经 grammar 版本测试锁定的 asm 容器节点集合，并在节点具有 asm ancestor 时跳过它。Evidence value 使用完整容器源码，span 使用容器 byte range；qualifier、clobber 和 operand 仍包含在完整文本中，但不单独成为 `inline_asm` Evidence。

选择这一方案是因为 Frontend 的职责是恢复语法事实，一条源码汇编语句就是后续检测的最小语义单位。单纯在 Projector 按行去重会丢失同一行合法存在的多条 asm，也无法消除上游 Observation/Classification 膨胀。

备选方案是继续采集所有 asm 子节点并在 Normalizer 聚合。该方案需要重建 AST 父子关系，增加身份漂移和复杂度，因此不采用。

### 2. 架构归属由已有 x86 知识和可证明的 branch role 共同决定

Analyzer SHALL 把嵌套 Evidence 与其最小包含的预处理/选择分支关联，并为显式 ARM/AArch64 selector 产生 `foreign`/`arm` branch role。该角色只表示“已证明不是本次 x86 目标”，不表示已完整分析 ARM 迁移。

Detector 的准入顺序为：

1. Evidence 命中现有 x86 instruction/register/feature/alias KnowledgeEntry：产生 `confirmed_local`。
2. Evidence 位于已证明的非 x86 branch：不产生 x86 Observation，并保留内部排除原因用于测试/诊断。
3. Evidence 没有 x86 命中，但语法本身仍可能是架构相关 asm：产生一个 `candidate`。
4. declaration attribute 只有在属性种类或值具有 target、target_clones、vector_size、architecture alias/feature 语义时才进入检测；通用属性直接忽略。

这一顺序不会使用新的隐藏指令词表。zlib 的 ARM 汇编依靠 `ARMCRC32` 分支证明被排除；无分支且未命中知识的未知汇编仍保持 candidate，避免把缺失知识误当作安全。

备选方案是内置 ARM 指令黑名单。它难以保持完整、权威和可审计，会与 curated knowledge 流程冲突，因此不采用。

### 3. 使用显式候选资格而不是让 Classifier 接收所有结构节点

Observation metadata SHALL 记录候选依据和架构归属，例如 `candidateBasis=unclassified_inline_asm`、`architectureDisposition=unknown|x86|foreign`。Classifier 只有在 disposition 为 unknown 且 Observation 为 candidate 时才能返回 `candidate-evidence-not-sufficient`；foreign 或 `not_architecture_related` 输入属于上游合同错误，不能形成迁移 Classification。

Projection Policy SHALL 继续从 Classification 投影现有 V2/V1 字段，并以 disposition 做防御性验证。被排除的 Evidence 不产生 Finding；真正未知候选仍以现有低严重度、非阻断、非操作语义展示。无需新增顶层字段或第二个结果文件。

备选方案是在 HTML renderer 中隐藏候选。该方案会让 JSON、HTML 和 summary 计数不一致，也无法修正 V1，因此不采用。

### 4. 去重身份以完整 asm span 为根，而不是 AST 节点类型

同一 source、configuration 和完整 asm byte span 只产生一个 NormalizedFact 根因，不同 producer 的 Evidence 合并 provenance；不同 span 即使文本相同仍保留为不同 occurrence。现有身份模型保留，仅去除 asm/attribute 的文本截断，并在显式 compilation context 下区分 occurrence。

既有噪声 Finding ID 和数量会改变，这是批准的正确性修复；Schema 字段、artifact 名称和合法 x86 finding 身份规则保持不变。

### 5. 测试分层与容器边界

- `tree_sitter_adapter.py`：fake Node/Tree 覆盖 C/C++ asm 节点层级、同一行多语句、partial parse 和稳定 span。
- Analyzer/branch role 模块：使用内存 Evidence/Knowledge fake 覆盖 ARMCRC32、AArch64、x86、RISC-V、fallback 和 unknown。
- Normalizer/Detector：使用 snapshot fake 覆盖 confirmed x86、foreign suppression、unknown asm candidate、`no_sanitize` suppression、`target("avx2")` confirmed 和 vector-size candidate。
- Classifier/Projection：使用 Observation/Classification fake 覆盖 candidate 准入、foreign 拒绝、V2 默认、V1 兼容、summary/HTML/log 一致性。
- 每个新增或修改业务模块登记到机器可读 inventory，并在 `kb-scanner-test` 中分别达到 90% line / 80% branch；zlib component/full regression 不替代模块覆盖。

## Risks / Trade-offs

- [不同 grammar 版本的 asm 节点名称变化] → 通过锁定版本、显式 allowlist 和真实 C/C++ parser component test 固定；未知节点降级为 Diagnostic，不恢复 substring sweep。
- [foreign branch 识别不足导致未知 ARM asm 仍作为 candidate] → 只在证据完整时排除；未知保持 candidate 并记录原因，后续可通过独立 curated knowledge change 扩展。
- [foreign 识别过宽而吞掉混合架构条件] → 对 `x86 || aarch64` 等混合 selector 保留逐 token 知识命中和 unknown/alternative 关系，不把整个条件简单标成 foreign。
- [Finding 数量变化影响 golden] → 将 zlib 差异登记为 approved correction，更新 V2/V1 golden 和 summary 断言但不改变 schema。
- [只在 Projector 防御会掩盖上游错误] → 主过滤放在 Detector，Projector 对非法 disposition 返回 Diagnostic，测试同时验证每层。

## Migration Plan

1. 先加入失败回归，固定当前 9 条 ARM asm→63 candidate、`no_sanitize` candidate 和唯一 x86 inactive finding 的基线。
2. 收紧 Frontend asm Evidence 并更新 Normalizer 身份，确保 9 条语句只形成 9 个完整局部事实。
3. 补齐 branch containment/foreign role，实施 Detector 候选准入和属性语义过滤。
4. 加固 Classifier/Projector 防御合同，更新 V2/V1 golden、HTML/log 和 summary。
5. 在独立测试容器运行模块覆盖、zlib、AVX、架构枚举、三个原生崩溃 fixture 和全量兼容回归。

回滚时可整体回退本 change；不涉及数据迁移、后端或生产容器。已有 generated/curated knowledge 字节保持不变。

## Open Questions

已在实现中闭合：两个锁定 grammar 都只支持 `gnu_asm_expression`；不猜测 MS 节点。未知布局仅保留 Diagnostic。foreign provenance 保留在 graph guarded_by 的 Evidence 引用，不为正常排除额外制造报告诊断；非法候选绕过上游时才产生合同诊断。

ARMCRC32 必须追溯到同文件唯一且在先的受 ARM selector 保护的宏定义，不能只按名字认定。否定、歧义、相关 undef 和循环均保守处理；无关 undef W 不破坏定义链。`structureComplete` 区分条件/宏定义/asm 的局部错误和文件其他位置的解析错误，后者不阻止完整 foreign guard 排除，前者仍保留未知候选。

投影边界采用 fail-closed：发现违反候选合同的 Classification 时返回失败 Diagnostic、不发布新 artifacts，保留已有报告；不在 mapper/renderer 中静默过滤。详细验证与修正基线见 `docs/architecture-candidate-noise-baseline.md`。
