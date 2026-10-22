## Context

项目已经完成 P1 原始语义事实、P2 受限效果摘要、P3 pthread 线程/同步上下文和 P4 一次性发布风险分析，并通过单元覆盖与固定 CASE0–CASE7 集成矩阵。现有结果能够证明这些固定输入上的实现行为，但不能代表真实工程覆盖率、检测准确率、规模性能或外部工具兼容性；路线图中的 P4 状态也仍停留在归档前描述。

P5 需要跨越语料、编译配置、P1–P4 编排、指标统计、第三方后端和文档多个层面，因此采用独立验证协议和 runner，而不向既有事实、摘要、线程图或风险报告追加字段。输入仍限定 GCC/Clang 用户态 C/C++；编译数据库只描述 TU 命令，真实工程必须另给显式 scope，且验证工具不得擅自运行 CMake 配置、原生链接或目标程序。

## Goals / Non-Goals

**Goals:**

- 建立可离线复现、来源可审计、带人工真值的 C11/C17/C++17/C++20 单 TU 与跨 TU 验证集。
- 用独立 v1 契约驱动 P1–P4 只读验证，严格区分 truth、observed、adjudicated、unknown、unsupported、failed 与外部对照。
- 固定一个真实 CMake 工程、已有 `compile_commands.json` 和显式 scope，量化输入覆盖、完整性、候选分布、性能、峰值内存和缓存行为。
- 隔离评估 GenMC、herdtools7，并支持导入有来源的 ARM DevKit 证据包；任一外部结果都不作为唯一 oracle。
- 形成 B1 CMake scope、`std::thread`、更强指针分析、fence/RMW 四类后续投资的量化决策记录。
- 保持全部自有代码单元测试及项目整体、语言、受影响模块行/分支覆盖率至少 90%。

**Non-Goals:**

- 不升级或改写 ModuleFacts/RunReport v2、EffectSummary v1、ThreadContextGraph v1、PublicationRiskReport v1。
- 不实现通用 points-to、`std::thread`/RAII、fence、RMW/CAS release sequence、CMake File API scope 导入或新的风险规则。
- 不把真实工程的零 finding、外部工具一致、BC 编译成功或 DevKit 零建议解释为全程序安全。
- 不把 GenMC/herdtools7/DevKit、网络、SSH 或第三方源码下载加入日常单元测试和核心运行依赖。
- 不合并开发与生产 Dockerfile，不执行用户工程的 configure/build/install 脚本或目标程序。

## Decisions

### 1. 使用独立 P5 契约和单一显式 CLI

新增严格的 `ValidationSuiteManifest v1`、`TruthAnnotation v1`、`AnalysisValidationRequest v1`、`AnalysisValidationReport v1`、`AnalysisExtensionDecision v1` 和 `BackendEvidenceBundle v1`，初始 policy 为 `analysis-validation-v1`、runner version 为 `0.1.0`。`validate-analysis --request --artifact-store --output --worker` 只接受新且为空的输出目录，stdout 只写最终合法报告 JSON，stderr 写日志。

退出码定义为：0 表示请求的验证完整且所有必需 truth/质量 gate 匹配；3 表示完整运行但存在预期不匹配或必需验收阈值失败；2 表示已有可用结果但存在 partial、unknown、超限或请求的可选后端不可用；1 表示请求/契约无效或不可继续。partial 优先于 mismatch 返回 2，同时报告保留已观察的不匹配。该语义只属于新命令，不改变 P1–P4 CLI。

备选方案是把验证字段加入 PublicationRiskReport，或只提供若干测试脚本。前者会污染产品报告并触发 P1–P4 迁移，后者缺少可校验身份、分母和缓存，因此均不采用。

### 2. 验证 runner 以子进程调用既有阶段并保持产物只读

runner 根据 request 为每个 case 建立独立工作目录，以固定 argv、环境、预算和超时顺序调用已有 collect/index/summarize/model-threads/detect-publication-risks 入口；只读取结构化 stdout/文件，不解析日志文字。每层产物以 kind/schema/digest、artifact/scope/profile/request hash 和实际命令关联，原文件不得被补字段或覆盖。失败 TU、未运行阶段和超限项始终保留在计划分母。

子进程边界便于采集 wall time、CPU time、峰值 RSS 和退出码，也避免验证 runner 的状态污染分析缓存。备选的进程内函数调用更快，但容易掩盖 CLI、环境和资源隔离问题；P5 以真实使用路径优先，纯统计/比较逻辑仍拆成可单测函数。

### 3. truth 是版本化输入，不从当前分析输出反推

每个固定 case 保存源码/IR hash、语言标准、编译器及版本、target/layout、优化/debug 配置、物理 TU、scope、适用 P4 模型和人工审阅依据。truth 使用稳定语义断言描述 required/forbidden finding code、允许的 verdict/完整性、关键对象/线程/证据关系与预期 unknown 原因，不仅保存一次运行生成的易变 ID。

truth 变更必须更新 suite version、来源 hash、审阅记录和变更理由；runner 拒绝 source/profile/scope digest 不匹配的注解。固定语料覆盖正确、风险和 unknown/unsupported，且同一语义在 C11/C17/C++17/C++20、单 TU/跨 TU 中保持明确映射。DevKit、GenMC、herdtools7 或当前 P4 输出均不能自动生成 truth。

### 4. 准确率只在有资格的人工真值分母上计算

报告同时给出严格指标和条件指标：严格 recall 的分母包含所有 truth 中必需 finding，分析返回 unknown/unsupported 时记为未检出；条件 precision/recall 只统计真正完成评估的 supported assessment，并单独报告 coverage/abstention。按 finding code 生成 TP/FP/FN、exact-match 和混淆记录，所有 hit/total 明示，零分母为 null。

真实工程若没有穷尽真值，只报告分层完整性、finding/unknown 分布和确定性分层抽样的人工裁决；只有被裁决样本可计算带清晰分母的样本指标，不能推广成全工程准确率。备选的“零告警率”或将 unknown 排除后给出高准确率会系统性夸大能力，因此禁止。

### 5. 真实工程通过审计门固定，日常运行完全离线

实施首先按以下门槛选择恰好一个项目：许可证允许提交验证快照；上游 URL、不可变 revision 和源树 hash 可记录；使用 CMake 且可获得 GCC/Clang `compile_commands.json`；规模足以暴露跨 TU/未知边界但能在预算内运行；含 pthread、原子或共享状态相关代码。将必要的未修改源码快照、许可证、预生成编译数据库、路径重映射和显式 scope profile 放入受控测试数据目录，不由 runner 下载或运行 CMake。

profile 记录计划 TU、纳入/排除规则、roots、构建配置身份、source-preserving/build-faithful 模式和已知选择偏差。编译记录越过快照根、引用缺失生成物、依赖不闭合或 scope 不一致时，结果为 partial/failed，不能静默丢弃。若候选项目不能通过许可证、尺寸或可复现性审核，实施在固定项目前暂停并修订提案，而不是临时换源。

### 6. 性能和缓存采用成对运行与语义 digest

每个规模 profile 至少执行一个空验证缓存的 cold run 和一个输入完全相同的 warm run，记录逐阶段 wall/CPU、峰值 RSS、计划/完成 TU、产物字节、缓存 hit/miss 和预算。排除时间戳、临时绝对路径及资源计数后计算 semantic digest；相同输入的 cold/warm 语义结果必须一致。

初次 P5 建立基线，不预设跨机器通用的绝对性能承诺。request 提供明确超时、内存和工作预算，超限返回 partial 并保留 frontier。决策记录同时保存环境指纹与原始 hit/total，后续 change 才能基于同环境基线设置回归阈值。

### 7. 外部后端仅通过隔离适配器或证据导入

GenMC 与 herdtools7 使用独立命令/容器适配器，显式声明镜像或二进制 digest、版本、许可证、支持输入子集、转换规则、命令、预算和原始输出 hash；适配器将结果规范化为 `BackendEvidenceBundle`，但保留原始类别与不适用原因。日常单元测试只读取固定录制输出，不启动后端。

ARM DevKit 不提供 SSH runner，只导入明确给出的历史/新证据包并验证版本、输入/报告 hash 和采集日期。外部后端差异进入 comparison，不覆盖 truth、不改变 P4 verdict。未请求后端为 not_run；显式请求但不可用为 partial；后端崩溃不能使核心验证结果消失。

### 8. 决策记录使用透明分母，不自动批准扩展

`AnalysisExtensionDecision` 分别登记 B1、`std::thread`、指针分析、fence/RMW 的阻塞 case/TU/candidate 数、对 finding/unknown/coverage 的潜在影响、证据来源、实现与维护成本等级、兼容性风险、建议和限制。面向用户的 detail/suggestion/decision 字段提供中文与英文成对内容；排序和缓存不依赖翻译文本。

runner 可计算候选排序，但最终状态仅为 `recommend`、`defer`、`insufficient-evidence`，必须保存人工确认和理由，不能自动创建后续 change 或把预计收益写成已实现能力。

### 9. 文档与验收产物分层

- `doc/IMPLEMENTATION_ROADMAP.md`：修正 P4 已 sync/archive，登记 P5 当前状态与边界。
- `README.md`、`doc/README.md`：增加 P5 使用、报告和复现入口。
- `doc/VALIDATION_AND_SCALING.md`：说明契约、CLI、truth 方法、真实工程 profile、指标、外部后端和限制。
- `doc/VALIDATION_AND_SCALING_VALIDATION.md`：记录实际命令、版本/hash、测试数、覆盖率、语料/真实工程结果和决策依据。
- 历史 `DEVKIT_BC_VALIDATION.md` 及证据目录保持原义，不把 P5 导入描述成重新执行。

文档链接、阶段状态、统计分母和中英文诊断通过自动化测试或内容校验；没有执行的后端明确标为 not_run。

## Risks / Trade-offs

- [人工 truth 可能出错或随配置失效] → 绑定 source/profile/scope hash，要求可追溯审阅依据、版本变更理由和正反例，拒绝陈旧注解。
- [固定语料导致对测试过拟合] → truth runner 与分析规则分层，并加入真实工程 unknown/性能分布；真实工程不冒充准确率数据集。
- [真实项目快照带来许可证、体积或生成文件问题] → 在任务早期执行硬性审核，只提交必要未修改输入、许可证与 hash；审核失败时暂停修订，不偷偷替换。
- [外部工具版本或模型无法映射] → 独立适配、显式 applicability 和转换证据，不将“不支持”映射为同意/安全。
- [性能测量受宿主噪声影响] → 保存环境指纹、原始计数和重复/冷暖运行，初版只建立同环境基线，不宣称跨机器阈值。
- [子进程编排增加运行时间] → 允许按 suite/profile 选择阶段并复用只读产物，但缓存身份必须完整，不能牺牲证据隔离。
- [P5 被误解为扩大检测能力] → 保持 P1–P4 schema/CLI 不变，所有报告固定声明 validation 不建立全程序安全。

## Migration Plan

1. 先修正文档状态并引入新 schema/验证器、固定语料和单元测试；P1–P4 黄金产物必须逐字节或语义 digest 不变。
2. 接入 `validate-analysis` runner 和离线语料，完成 truth mismatch、partial、预算和确定性验收。
3. 通过审核门固定真实工程 profile，再执行 cold/warm 规模基线和人工分层抽样。
4. 最后接入可选外部后端证据，生成决策记录与最终验证文档。
5. 所有产物写入新的版本化输出目录。回滚只需移除 P5 CLI/schema/数据和文档入口；既有 P1–P4 产物、缓存与命令无需迁移或回写。

## Open Questions

- 具体真实工程在实施任务的许可证、规模和可复现性审核后锁定；未锁定前不开始真实工程 runner 验收。
- GenMC/herdtools7 可执行镜像或二进制是否在实施环境预先可用，将决定本 change 产生 live 结果还是仅完成适配器与录制证据验证；两种状态都必须如实记录。
- 首轮性能数据建立基线后，是否足以为下一 change 设置硬性回归阈值，由最终决策记录确定，不能在测量前臆定。
