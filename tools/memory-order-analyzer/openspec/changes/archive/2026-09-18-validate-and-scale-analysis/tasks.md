## 1. 状态基线与文档纠偏

- [x] 1.1 更新 `doc/IMPLEMENTATION_ROADMAP.md`，将 P4 标记为已实现、质量验收、同步并归档，并将 P5 标记为当前 implementing 状态，核对归档、使用与验证链接有效。
- [x] 1.2 更新项目 README 和 `doc/README.md` 的阶段导航，只登记已经存在的 P5 入口，不把提案、设计或未执行后端写成已实现结果。
- [x] 1.3 固定 P1–P4 关键 schema、黄金产物和 CLI/退出码基线 hash，增加回归断言保证本 change 不迁移、补写或覆盖既有产物。
- [x] 1.4 盘点现有 Python/C++ 自有源码枚举、质量排除项与开发容器工具版本，记录 P5 新模块纳入覆盖率的方案。

## 2. P5 协议与严格校验

- [x] 2.1 定义 `ValidationSuiteManifest v1` 与 `TruthAnnotation v1` schema，包含 case/profile/source/scope/truth/reviewer 身份、canonical digest 和确定性排序。
- [x] 2.2 定义 `AnalysisValidationRequest v1`、`AnalysisValidationReport v1`、`AnalysisExtensionDecision v1` 与 `BackendEvidenceBundle v1` schema，包含版本、policy、预算、依赖、完整性、双语诊断和分层分母。
- [x] 2.3 实现统一 canonical JSON、digest 和严格未知字段/未来版本拒绝逻辑，校验重复 ID、悬空引用、混合 profile、陈旧 truth 及依赖替换。
- [x] 2.4 实现 request/suite/truth/report/decision/backend bundle 的加载、验证、确定性写入和失败报告，确保无效输入不以默认值降级。
- [x] 2.5 为全部 P5 契约补充正常、边界、损坏、未来版本、陈旧 digest、跨 profile 和排序稳定性单元测试。

## 3. 离线人工真值语料

- [x] 3.1 设计并登记 C11、C17、C++17、C++20 的单 TU 与至少三个物理 TU case 矩阵，覆盖正确发布、P4 已支持风险及 unknown/unsupported。
- [x] 3.2 为每个 case 保存源码/IR、编译器与版本、target/layout、优化/debug、compile command、scope、roots 和输入 hash，禁止依赖网络、SSH、原生链接或运行目标程序。
- [x] 3.3 编写人工 `TruthAnnotation`，声明 required/forbidden finding、允许 verdict/完整性、对象/线程/证据关系、unknown 原因、语义依据、reviewer 与审阅日期。
- [x] 3.4 增加 truth 变更版本、来源变更拒绝、旧 truth 保留和 suite identity 回归测试，证明当前 P4 或外部输出不能自动生成/修改 truth。
- [x] 3.5 在开发容器执行完整固定语料，核对四种语言、单/跨 TU、正确/风险/unknown 类别计划分母和确定性输入清单。

## 4. 验证 runner 与 CLI

- [x] 4.1 实现 `validate-analysis --request --artifact-store --output --worker` 参数、stdout/stderr 隔离、新空输出目录检查和小型合法失败报告。
- [x] 4.2 实现逐 case 专用工作目录与固定子进程 argv/environment 编排，按请求调用 P1–P4 现有入口并只消费结构化产物。
- [x] 4.3 实现 P1–P4 kind/schema/digest、artifact/scope/profile/request hash 和退出状态的跨层绑定，拒绝陈旧、混代或被替换依赖。
- [x] 4.4 实现 wall/CPU、峰值 RSS、输出字节、实际预算、超时和 frontier 采集，限制子进程写入并只清理已验证的专用临时目录。
- [x] 4.5 实现 0/3/2/1 验证退出语义及 partial 优先级，验证 truth mismatch、可用但不完整、非法和全部不可用路径。
- [x] 4.6 增加 CLI/runner 单元测试，覆盖参数错误、非空输出、子进程成功/失败/超时、日志污染、部分阶段和 P1–P4 文件只读不变。

## 5. Truth 比较、完整性与准确率

- [x] 5.1 实现稳定语义断言匹配，将 observed finding/verdict/evidence/unknown 与 required/forbidden truth 比较而不依赖易变运行 ID。
- [x] 5.2 实现 request/input、compile、P1、P2、P3、P4、truth、sampling、performance、backend 的 complete/partial/failed/not_run 状态和全计划 hit/total 聚合。
- [x] 5.3 实现按 finding code 的 TP/FP/FN、strict precision/recall、supported-only 条件指标、exact-match、abstention 和 null 零分母语义。
- [x] 5.4 断言 truth 预期风险而分析 unknown/unsupported 时进入 strict FN 与 abstention，未经审核/陈旧/不适用 case 不进入准确率分母。
- [x] 5.5 为完整匹配、完整 mismatch、部分 mismatch、零候选、零分母、混合 finding/unknown 和损坏 evidence 补充单元测试。

## 6. 性能、缓存与确定性基线

- [x] 6.1 实现排除时间戳、临时绝对路径和资源计数的 semantic digest，同时保留原始运行报告与资源字段。
- [x] 6.2 实现相同 request 的 cold/warm 成对执行与 cache hit/miss、逐阶段 wall/CPU、峰值 RSS、产物字节和环境指纹统计。
- [x] 6.3 当 cold/warm semantic digest 不一致、预算耗尽或输出截断时生成失败/partial 证据，禁止只发布加速比例。
- [x] 6.4 补充 deterministic clock/resource collector、缓存损坏、碰撞、并发发布、cold/warm 等价和预算边界单元测试。

## 7. 真实 CMake 工程审核与规模验证

- [x] 7.1 建立候选审核表，核对许可证、上游 URL、不可变 revision、源树 hash、CMake/GCC/Clang、pthread/atomic 相关性、规模和离线预算，并选择恰好一个项目。
- [x] 7.2 固定所选项目的必要未修改源码快照、许可证、预生成 `compile_commands.json`、路径重映射和显式 scope；若审核失败则停止并修订 proposal/design/specs，不临时忽略缺口。
- [x] 7.3 实现真实工程 profile 校验，分别统计原始记录、去重 TU、依赖、配置、scope/roots 和纳入/排除项，拒绝越根路径并保留缺失成员分母。
- [x] 7.4 设计确定性分层抽样，覆盖 finding/discharged/unknown/unsupported/无候选层，保存 seed、计划/抽中/已裁决/未裁决及 inconclusive。
- [x] 7.5 对固定 profile 执行 P1–P4 cold/warm 规模基线，记录完整性、候选/unknown 分布、性能、内存、缓存和 semantic digest，不执行 CMake 或目标程序。
- [x] 7.6 完成人工样本裁决并只对已裁决样本给出样本指标，明确选择偏差且不外推全工程准确率或安全性。
- [x] 7.7 为 profile 越根、缺失生成物、scope 差异、抽样稳定性、未裁决/inconclusive 和禁止执行配置脚本补充单元与离线集成测试。

## 8. 外部后端隔离与证据导入

- [x] 8.1 实现 GenMC 适配器的 applicability、版本/许可证/命令/输入转换身份、预算、原始输出 hash 和规范化 bundle；日常测试只回放固定输出。
- [x] 8.2 实现 herdtools7 适配器的 litmus 映射、not_applicable 边界、转换证据、预算和规范化 bundle，不将近似映射称为源码等价。
- [x] 8.3 实现 ARM DevKit 证据导入器，验证日期、DevKit/LLVM 版本、源/BC/命令/报告 hash，并保留 2026-09-10 与 2026-09-11 历史原义，不增加 SSH runner。
- [x] 8.4 实现 truth、P4 与 backend observation 的 agree/disagree/not_applicable/inconclusive 比较，确保外部一致或零建议不修改 truth、P4 verdict 或 safety。
- [x] 8.5 增加录制成功、差异、exit-zero 空报告、未来版本、损坏、超时、崩溃、输出截断和 requested-unavailable 单元测试，验证其他核心结果仍可用。
- [x] 8.6 若锁定的 GenMC/herdtools7 镜像或二进制在实施环境可验证，则执行隔离 live smoke 并保存 bundle；否则明确记录 not_run、原因和复现命令，不阻塞离线核心验收。

## 9. 决策记录与双语输出

- [x] 9.1 实现 B1 CMake scope、`std::thread`、更强指针分析、fence/RMW 的阻塞 case/TU/candidate、潜在覆盖收益、成本和兼容性证据聚合。
- [x] 9.2 实现 `recommend`、`defer`、`insufficient-evidence` 状态与人工确认流程，禁止自动创建 change 或把潜在收益写成已实现。
- [x] 9.3 为所有面向用户的 detail/suggestion/decision/diagnostic 字段提供中文与英文成对输出，证明翻译不参与身份、排序、缓存或退出码。
- [x] 9.4 补充低分母、矛盾证据、未知占优、后端不可用、人工未确认和翻译变化单元测试。

## 10. 文档与可复现证据

- [x] 10.1 编写 `doc/VALIDATION_AND_SCALING.md`，说明 P5 契约、CLI、truth 方法、真实工程 profile、准确率/抽样、性能/缓存、外部后端和安全边界。
- [x] 10.2 编写 `doc/VALIDATION_AND_SCALING_VALIDATION.md`，记录实际环境、精确命令、版本/hash、语料与真实工程分母、指标、资源、后端状态、决策依据和报告位置。
- [x] 10.3 更新 README、文档索引和路线图到实际 completed/validated 状态，保持 DevKit 历史证据原义并明确未执行后端为 not_run。
- [x] 10.4 增加文档相对链接、阶段状态、统计数值、命令、hash、双语示例和“非全程序安全结论”内容校验。

## 11. 全量质量与归档前验收

- [x] 11.1 将所有 P5 Python/C++ 自有执行文件和可执行头纳入质量枚举，审核排除项仅限第三方、生成元数据和纯测试输入，并为变更的声明头更新 hash 锁。
- [x] 11.2 在独立开发容器以全新输出目录运行全部 C++/Python 单元测试，确认正常、边界、异常、unknown/partial 路径均有有效断言。
- [x] 11.3 生成并校验项目整体、Python、C++ 及每个受影响模块的行/分支 hit/total，所有可用指标至少 90%，集成/真实工程/backend profile 不混入单元覆盖。
- [x] 11.4 独立运行离线四语言语料、真实工程 cold/warm、抽样、文档和 P1–P4 黄金兼容验收，使用新的持久报告目录并核对 semantic digest。
- [x] 11.5 运行 `openspec validate validate-and-scale-analysis --strict`、schema/链接/hash 校验和 `git diff --check`，任何失败、覆盖不足或必需证据缺失时保持任务未完成。
- [x] 11.6 在验证文档登记最终测试数、整体/语言/逐模块覆盖率、完整统计范围、排除理由、truth/真实工程/外部后端结果与报告位置，全部通过后才标记 change 可 sync/archive。
