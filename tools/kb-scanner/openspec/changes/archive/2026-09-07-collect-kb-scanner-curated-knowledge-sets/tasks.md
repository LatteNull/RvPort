## 1. 冻结基线与来源审计

- [x] 1.1 冻结当前 v1 manifest、两份 compiler facts 的字节/SHA-256/六类计数/source、KnowledgeSource/Entry/Snapshot identity、behavior acceptance matrix、legacy YAML/`generatedSet`、默认结果结构和三个 artifact 基线。
- [x] 1.2 从 RVPT 对比结果、阶段 3 behavior matrix、旧 YAML 和代表性 fixture 建立非权威 candidate inventory，覆盖 inline asm 指令/寄存器、CPU/平台 API、target feature、架构别名和 fixed vector width；排除 OS、内核、系统调用、驱动和板级条目。
- [x] 1.3 对每个候选类别完成 compiler/assembler/linker 可提取性审计，标记 generated、curated、rejected 或 deferred，并明确链接器是否提供不可由 compiler/assembler 替代的 C/C++ 静态分析事实。
- [x] 1.4 为 LLVM、GCC、GNU Binutils 和适用官方语言/API 文档选择精确 release/commit、逻辑路径/章节和许可证，禁止滚动 `main`、搜索结果或宿主机绝对路径作为 accepted provenance。
- [x] 1.5 记录来源取得与校验方式，确保实际 extractor 输入可作为显式只读 source root/archive 提供且知识生产代码不负责联网、clone 或启动 toolchain。

## 2. 知识生产模型、身份与严格 Schema

- [x] 2.1 新建 knowledge production source/reference、candidate decision、generated fact 和 accepted curated entry 的 scanner-owned 不可变模型，明确 runtime source 与 non-runtime decision ledger 边界。
- [x] 2.2 为 2.1 的每个新增业务模块增加 isolated unit tests，覆盖有效/无效字段、冻结、JSON-safe、乱序、重复、缺失引用和 rejected/deferred 不可进入 runtime source。
- [x] 2.3 实现版本化 source/reference registry、decision ledger、generated source 和 curated source 的严格 JSON schema，建立 fact-kind/scope/review-status allowlist并拒绝额外字段。
- [x] 2.4 为 2.3 的 schema 模块增加 isolated unit tests，覆盖滚动分支、绝对路径、缺少 commit/license/hash/reference、非法 review 状态以及 regex/operator/severity/blocking/message 等执行或展示字段。
- [x] 2.5 实现 source、reference、candidate 和 curated entry 的稳定 identity/canonicalization，确保 ID 不包含 checkout 根、mtime、采集顺序、对象地址或随机值。
- [x] 2.6 为 2.5 的 identity/canonicalization 增加 isolated unit tests，覆盖 Windows/POSIX 根、输入排列、别名大小写语义、空白、汇编 token 和跨来源相同事实。
- [x] 2.7 实现确定性 renderer/lint，保证排序、去重、换行和 JSON 序列化稳定，并验证 runtime data 与 decision ledger 不交叉加载。
- [x] 2.8 为 2.7 的 renderer/lint 增加 isolated unit tests，证明相同输入字节一致、冲突不被静默裁决、错误输出不会覆盖有效基线。

## 3. 工具链 Generated Facts 提取

- [x] 3.1 建立只读 extractor protocol 和 source adapter 边界，输入仅为显式 source descriptor/root/archive，输出为生产模型或结构化 Diagnostic，不执行网络、subprocess 或写入上游输入。
- [x] 3.2 为 3.1 增加 isolated unit tests，使用临时目录/fake source 覆盖缺失文件、路径逃逸、不支持修订、读取失败、输入未修改和 Diagnostic 去敏。
- [x] 3.3 实现 LLVM MC/TableGen 与 GNU Binutils opcode/register table 的 x86 instruction/register extractor，并保持两个上游来源独立 provenance。
- [x] 3.4 为 3.3 的每个 extractor 增加最小固定上游结构 fixture 和 isolated table-driven unit tests，覆盖别名、伪指令、寄存器类、重复、乱序、畸形记录及确定性输出。
- [x] 3.5 实现 Clang/GCC x86 target/option definition extractor，产生可证明的 target feature、CPU/architecture name 和 compiler spelling facts；不得修改或调用现有两份 facts 的旧生成脚本。
- [x] 3.6 为 3.5 的每个 extractor 增加 isolated unit tests，覆盖 feature 正反例、value spelling、别名、非 x86 target 排除、结构变化和来源追溯。
- [x] 3.7 审计 Clang/GCC headers/builtin definitions 中未被既有 facts 接纳的 CPUID、RDTSC、XGETBV 等 compiler-facing API，确定复用既有 kind 或产生新 API kind，禁止无意义复制。
- [x] 3.8 若 3.7 需要新 extractor，则实现该 extractor 及其 isolated unit tests；若既有 facts 已覆盖，则在 decision ledger 中记录无需新增数据的证据。
- [x] 3.9 使用选定的固定上游修订生成真实新增 JSON sources，记录每个 source 的条目数、输入摘要、许可证和精确来源，并验证第二次生成字节一致。

## 4. Curated 审校与真实数据集

- [x] 4.1 将不能确定性生成的 API 归属、架构别名归一、来源冲突和向量宽度语义候选写入 decision ledger，逐项附权威 reference 和 accepted/rejected/deferred 状态。
- [x] 4.2 对 accepted 候选执行独立审校，建立 review policy/version；缺少固定来源、许可证或明确语义的条目必须保持 deferred 或 rejected。
- [x] 4.3 生成只包含 accepted entries 的 runtime curated JSON 和独立 reference registry，确保 entry ID 可重算且每条引用闭合。
- [x] 4.4 建立真实数据 component tests，验证所有 generated/curated source 和 decision ledger 的 schema、provenance、引用、hash、排序、重复项、状态隔离及禁止执行语义。
- [x] 4.5 生成按类别统计的知识生产基线，分别记录 generated、accepted curated、rejected 和 deferred 数量，不允许用高数量汇编事实掩盖 API 或向量语义缺口。

## 5. Manifest 与 Knowledge Provider 兼容接入

- [x] 5.1 扩展 `knowledge/schema.py` 支持显式版本化的多来源 manifest 和 source-specific schema，同时继续严格接受原 v1 generated-only 输入并拒绝 v1 `curatedSets`。
- [x] 5.2 扩展 `test_knowledge_schema.py` isolated unit matrix，覆盖 v1 完全兼容、有效新版本、source kind/path/hash 唯一性、decision ledger 禁止加载、额外字段和部分非法来源。
- [x] 5.3 扩展 `knowledge/identity.py` 和 core Knowledge metadata 合同，使新增 source kind/reference/review provenance 可稳定表达且不改变旧 v1 source/entry/snapshot identity。
- [x] 5.4 为 5.3 的所有修改模块增加或扩展 isolated unit tests，固定旧 identity golden values，并覆盖新来源跨 checkout、跨顺序和多来源合并。
- [x] 5.5 扩展 `knowledge/provider.py` 按 manifest 声明加载旧 generated、新 generated 和 accepted curated source，验证 hash/schema/reference，合并相同事实并保留全部 source provenance。
- [x] 5.6 扩展 `test_knowledge_provider.py` isolated unit tests，覆盖 v1 等价结果、新来源成功、generated/curated 合并、单来源 partial、全部新增来源失败、未知 kind、审计数据拒绝和 Diagnostic 去敏。
- [x] 5.7 更新生产 `knowledge-manifest.json` 为选定的新版本并声明真实新增 sources；保留一个 v1 fixture 证明两份既有 facts 仍可独立加载且 identity 不变。
- [x] 5.8 增加真实 manifest/Provider component contract，验证所有提交数据摘要、来源类型、条目计数、引用闭合及两份旧 facts 字节/哈希/source 完全不变。

## 6. Local Detector 知识映射

- [x] 6.1 为 assembly instructions、register names、CPU/platform APIs、target features、architecture aliases 和 vector-width markers 定义 code-owned DetectorDefinition/matcher binding，数据文件不得携带 recipe。
- [x] 6.2 扩展 `test_detector_definitions.py` isolated unit tests，覆盖新 kind、重复 binding、错误输入 Evidence kind、confirmed/candidate/hint 状态和 registry 确定顺序。
- [x] 6.3 扩展 `detectors/matchers.py`，对 inline asm、symbol/call、declaration attribute、macro/preprocessor、type/comment 实现有边界的知识匹配；不得回退为整文件 regex 重扫。
- [x] 6.4 扩展 `test_local_matchers.py` isolated table-driven tests，覆盖各类正例、大小写/别名、汇编操作数与寄存器边界、相似 API 反例、未知 feature、普通数字宽度和 comment 降级。
- [x] 6.5 扩展 `detectors/local.py` 和 deferred capability 映射，使有权威 Evidence/Knowledge 的 x86 专属事实形成 `confirmed_local`，vector width 保持 knowledge-backed candidate，comment 保持 hint。
- [x] 6.6 扩展 `test_local_detector.py` isolated unit tests，覆盖引用完整性、多来源聚合、重复去重、输入排列稳定、未知/partial 状态和禁止产生 blocker/severity/readiness。
- [x] 6.7 更新 `behavior-acceptance.json`，逐项把已覆盖能力改为明确 generated/curated local 状态，并为未完成项保留来源审计决定的 deferred reason。

## 7. Staged Qualification 与兼容回归

- [x] 7.1 增加覆盖 instruction/register、CPU API、target feature、architecture alias 和 vector width 的 C/C++/inline asm component fixtures，验证 SourceSpan、Evidence kind 和知识匹配语义。
- [x] 7.2 扩展 staged qualification integration，验证新 manifest 经 Workspace、Frontend、Provider、Normalizer 和 Local Detector 产生可追溯 Observation，并保留 graph/build/classification deferred 状态。
- [x] 7.3 回归固定向量宽度、comment、相似 API、未知汇编词和普通架构样式变量不会被误升级为 confirmed/blocker。
- [x] 7.4 在独立测试容器复扫阶段 3 的两个 x86-only 项目，比较新增知识前后的 Observation 类别/数量并人工抽样新增命中，且不执行项目构建、compiler 或测试。
- [x] 7.5 回归默认 legacy CLI、`schemaVersion: "1.0"`、顶层字段、Finding 关键语义、三个 artifact、24 个 YAML/`generatedSet` 和 legacy 五文件均不变。
- [x] 7.6 验证本 change 不读取或执行 OS、内核、系统调用、驱动、板级或 RVWMO 数据，并且新内部对象不产生第二套主结果。

## 8. 单元覆盖门禁、容器与文档

- [x] 8.1 扩展机器可读 test inventory，将每个新增/修改 production、knowledge、core 和 detector 业务模块双向映射到 isolated unit 与适用 component/integration/contract tests。
- [x] 8.2 扩展容器 test runner，分别运行 knowledge-production unit gate、knowledge/detection unit gate、frontend unit gate 和 full regression；每个 inventory 模块必须有 executed lines且达到 90% 行、80% 分支覆盖。
- [x] 8.3 确认 extractor tests 使用最小只读 source fixtures且无网络/subprocess；真实刷新流程只复用 `kb-scanner-test` 镜像环境并读取显式固定来源，不安装宿主机依赖。
- [x] 8.4 确认不修改/构建生产镜像、根 Compose 或现有业务服务，不给测试容器业务凭据，也不让扫描运行时获得网络或 toolchain 执行能力。
- [x] 8.5 更新知识数据来源说明、采集/审校/刷新手册、decision ledger 说明、knowledge baseline、容器文档和开发计划，记录精确版本、许可证、各类别数量、残留缺口及回滚到 v1 manifest 的方式。
- [x] 8.6 在唯一独立 `kb-scanner-test` 容器运行全部 isolated/component/integration/contract/full regression，记录各 unit suite 数量、逐模块覆盖率、高层测试数和总回归数。
- [x] 8.7 运行数据确定性复验、`git diff --check` 和 `openspec validate collect-kb-scanner-curated-knowledge-sets --strict`，修复全部格式、引用和一致性问题。
