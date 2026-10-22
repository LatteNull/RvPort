## 1. 固化失败基线与测试映射

- [x] 1.1 在 zlib 回归 fixture 中固定 9 条 ARMCRC32 asm、`no_sanitize("memory")`、`target("avx2")`、混合 `__x86_64__ || __aarch64__` 条件和真正未知 asm，并记录预期 Evidence/Observation/Classification/Finding 数量。
- [x] 1.2 添加当前失败断言，证明 9 条 asm 被展开为 63 条 candidate、通用属性产生 candidate，并确保测试能够分别定位 Frontend 重复、Detector 误准入和 Projector 噪声。
- [x] 1.3 更新 frontend、evidence graph、knowledge/detection、classification 和 projection 的机器可读 unit inventory，为本 change 每个实质修改模块登记隔离测试、fake/mock 边界及 90% line / 80% branch 门禁。

## 2. 收紧 Frontend asm 与 attribute Evidence

- [x] 2.1 用锁定 C/C++ grammar 实测并固定最外层 asm 容器节点集合，替换节点类型 substring sweep；具有 asm ancestor 的 qualifier、operand、constraint 和 clobber 节点不得单独生成 `inline_asm` Evidence。
- [x] 2.2 以完整最外层 asm byte span 建立确定 Evidence，保留同一行不同 span 的独立语句，并使 partial ERROR/MISSING asm 至多产生一个可恢复 Evidence 和一个结构化 Diagnostic。
- [x] 2.3 收紧 declaration attribute 采集为完整属性构造单 Evidence，禁止属性名称/参数子节点重复，同时保持 Frontend 不承担 x86 分类。
- [x] 2.4 为 `tree_sitter_adapter.py` 的 C/C++ asm 层级、同一行多语句、partial parse、完整 attribute 和稳定 byte span 添加 fake Node/Tree 隔离单元测试，并通过该模块覆盖门禁。

## 3. 建立分支归属与候选准入

- [x] 3.1 扩展 Evidence Graph 的最小包含分支关联，使嵌套 asm/attribute Evidence 能追溯到对应预处理或选择 branch，而不依赖重复 AST 子节点。
- [x] 3.2 为显式 ARM/AArch64 selector 增加可审计的 foreign branch role，并正确处理 `x86 || aarch64` 混合条件、否定条件、fallback 和 unknown；不得引入隐藏指令黑名单。
- [x] 3.3 调整 Normalizer 的 asm/attribute 语义根和身份材料，使同一完整 Evidence 不产生多个事实，而不同 source span/configuration 保持独立 occurrence。
- [x] 3.4 调整 Local Detector 准入顺序：现有 x86 知识命中保持 `confirmed_local`，完整 foreign branch 抑制 x86 Observation，真正未知 asm 产生单一 `unclassified_inline_asm` candidate。
- [x] 3.5 仅允许 target、target_clones、vector width、architecture alias 或已加载 target feature 语义进入 attribute 检测，排除 `no_sanitize` 等通用属性并保留 `target("avx2")` 既有知识命中。
- [x] 3.6 为 branch attribution、Normalizer 和 Local Detector 分别添加内存 snapshot/fake knowledge 单元测试，覆盖 ARMCRC32、AArch64、x86、RISC-V、混合 selector、unknown asm、通用属性和 target attribute，并通过各模块覆盖门禁。

## 4. 加固分类与版本化投影

- [x] 4.1 为合法 candidate 增加显式候选依据和 architecture disposition，限制 Classification Policy 只对 unknown 且引用完整的候选返回 `candidate-evidence-not-sufficient`。
- [x] 4.2 对错误进入 Classifier 的 foreign、not-architecture-related 或 duplicate-child Observation 产生结构化合同 Diagnostic，且不得生成 Classification 或影响 Assessment。
- [x] 4.3 在 V2 默认和显式 V1 Projection Policy/Mapper 中防御性拒绝无合法候选资格的分类，保证被过滤项不会重新形成 Finding、summary 计数或 HTML/log 条目。
- [x] 4.4 保持真正未知 asm 为一个低严重度、非阻断、非操作 Finding，并使 evidence chain/trace 指向完整 asm span；保持知识支持的 x86 finding、不同 occurrence 和 configuration 不被误合并。
- [x] 4.5 为 Classification Policy、Migration Classifier、Assessment 聚合、V2/V1 mapper、summary 和 renderer 的修改路径分别添加隔离单元测试，并通过各模块 90% line / 80% branch 门禁。

## 5. 兼容回归与验收

- [x] 5.1 在独立 `kb-scanner-test` 容器运行 zlib 回归，断言 9 条 ARM asm 和 `no_sanitize` 产生零个对应 x86 findings，真实 mixed x86 condition 保持 inactive，真正未知 asm 只产生一个 candidate。
- [x] 5.2 为 zlib 回归固定宽松墙钟预算以及 Evidence、Observation、Classification、Finding 数量上限，防止父子节点爆炸和持续高 CPU 恢复。
- [x] 5.3 分别运行默认 V2、显式 V2 和显式 V1 contract，验证 schema、三类 artifact、JSON/HTML/log/summary 计数一致且没有第二个主结果文件。
- [x] 5.4 运行 AVX、架构枚举、cJSON/zlib/libarchive 原生崩溃、知识数据哈希和全量兼容回归，确认 Clang/GCC 两份 generated facts 字节未变且扫描未执行项目命令。
- [x] 5.5 更新候选判定与维护文档，说明单 asm Evidence 边界、foreign branch 只用于 x86 干扰排除、unknown candidate 语义、通用属性过滤和容器复现命令。
- [x] 5.6 对 change 和全部受影响主规范执行 OpenSpec strict validation，复核所有任务、模块覆盖清单和 zlib approved correction 后再允许同步归档。
