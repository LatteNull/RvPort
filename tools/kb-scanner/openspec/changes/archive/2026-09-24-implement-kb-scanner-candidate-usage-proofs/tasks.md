## 1. 固定基线与人工 oracle

- [x] 1.1 在独立测试容器确认当前单元/回归基线，固定两份 compiler facts 哈希、当前 V1/V2/HTML/log 与无候选报告；记录固定 libarchive commit、文件数及扫描配置，不修改生产容器或本机依赖。
- [x] 1.2 建立版本化人工用途 oracle：局部闭合纯数据正例、仅名称/整数/字段不能证明、使用与定义范围、多 occurrence、数据 selector 控制 intrinsic/未知调用、混合用途和逃逸；将 libarchive 26 项列为审校对象而非运行时规则。
- [x] 1.3 固定支持语法、non_execution_data、配置身份及 usageProof 闭包合同，登记全部预计受影响模块到隔离 unit inventory，设置整体和逐模块 90% 行/90% 分支门禁。

## 2. 候选相关前端事实

- [x] 2.1 增加一次性轻量 usage inventory 与普通无属性函数的词法作用域绑定；通过 fake grammar 单测覆盖 shadowing、声明/读写/比较/控制体和字节范围，保留旧 Evidence 身份。
- [x] 2.2 补齐不支持语法、调用/return/取址/外部写入逃逸及预算记录，验证 Tree/Node/Point 安全与可选 Clang 冲突边界；同步异常和 UTF-8/CRLF 隔离测试。
- [x] 2.3 实现使用结构规范化、引用/span/configuration 校验与多 producer 合并，单测正常、悬空、跨配置和部分解析路径，不把错误记录变成完整用途证明。

- [x] 2.4 按 2026-09-23 用户确认的设计接入知识驱动的候选作用域采集；补无需求/稀疏/失败/配置和原始事实不变单测，重跑受影响验收，不沿用调整前结果。

## 3. 用途索引、闭包与证明生成

- [x] 3.1 实现 CandidateUsageDemand，复用现有 matcher 和知识索引，统一与 Local Detector 的 fact/subject/configuration/matchedEvidenceIds；单测无候选、聚合事实和多配置身份。
- [x] 3.2 实现共享 def-use/control/escape 索引与按作用域缓存的局部闭包；单测全使用穷尽、定义/使用责任差异、同名遮蔽、相关/无关语句、重复赋值和未知控制。
- [x] 3.3 实现完整 non_execution_data proof 与未知/冲突摘要，核查支持引用、使用计数和预算；单测空路径、截断、无效端点、多个角色与数据控制执行，不从无 intrinsic 推导安全。
- [x] 3.4 接入非执行用途 Entity/Relation/ProofPath，保留原基础图、confirmed facts 与既有 proof；单测稳定 ID、输入乱序、图查询隔离和跨配置拒绝。
- [x] 3.5 接入局部及扫描级记录/访问预算、查询缓存计数和无需求快速路径；单测每个预算边界与超限保留事实，不扩大原图额度。

## 4. 分类准入与默认管线

- [x] 4.1 强化 SemanticAdmissionIndex 对 role、精确根、scope 摘要、truncated、完整路径和引用计数的验证，接受 non_execution_data；补正常/边界/异常隔离单测，旧手工 proof fixture 更新为可核查完整合同。
- [x] 4.2 在默认 composite 接入用途 Analyzer 并隔离 Detector 的执行关联；补阶段顺序、failed/partial、无候选与新旧关系共存单测。
- [x] 4.3 验证仅省略 Classification、保留 Observation/fact/原 confirmed high/blocker；补全混合角色、多 occurrence、未知调用及评估不自动 ready 的单测，必要的 Assessor 修改同步登记覆盖。

## 5. 兼容投影与审计

- [x] 5.1 实现 V2 candidate-usage extension：保留 Finding 内自包含用途来源、顶层有界 excludedCandidates 审计及总数/省略数；补引用闭合、多个 namespace 共存和预算单测。
- [x] 5.2 补齐真实源码链、默认上下各 20 行、未知断点、双语说明及 HTML 安全转义；不得加入分类/评估/抽象 role 代码节点，所有受影响 projector/renderer 模块均有直接单测。
- [x] 5.3 更新扩展说明与合同示例，执行默认/显式 V2、显式 V1、三个工件及无候选字节对照；不改核心 schema、后端或前端，逐字段记录允许变化。

## 6. 组件、项目与性能验收

- [x] 6.1 真实 parser/默认 CLI 跑通自动证明正例，确认没有手工注入 role；运行宏重定义、模板、跨 TU、调用/return 逃逸、执行/数据混用、配置、错误节点与原生崩溃缩减反例。
- [x] 6.2 对固定 libarchive 两次独立扫描，逐项审校旧 55 项及当前基线全部变化，明确 26 项数据用途的已证范围和 unknown 原因；在 2 CPU/2 GiB/无额外 swap 下各轮不超过 300 秒，不要求全量消噪。
- [x] 6.3 按 2026-09-24 用户确认的口径，在独立 2 CPU/2 GiB/无 swap 容器完整测 10000/20000 局部引用稀疏/密集需求及预算触发；每个独立扫描须在 300 秒内正常完成，输出开关成本及旧相对门槛诊断、分阶段时间、访问/缓存计数、峰值 RSS 和报告体积。检查候选/事实完整与有界工作量，保存开启功能的新基线；同步补验收逻辑的正常/边界/异常单测和 ≥90% 行/分支覆盖，旧失败记录不改写。
- [x] 6.4 容器执行隔离单元覆盖门禁，纳入未加载的 kb_scanner/scripts/tools 全部自有源码，确认整体和每个受影响模块行/分支均 ≥90%；报告命令、计数、排除理由、覆盖率和持久报告位置，不用真实 parser 测试充数。
- [x] 6.5 执行完整回归（AVX、枚举、候选、架构家族、函数多版本、CMake/RPM/Autoconf、V1/V2、安全边界），复核原事实保存、两份 generated facts 哈希和未执行项目命令；测试/覆盖/性能失败不得标记完成。

## 7. 交付说明与阶段交接

- [x] 7.1 更新 candidate-semantic-admission 文档、开发计划和本 change verification：区分自动生成、仅消费、仍不支持的用途，保留旧审校账本；CC-0006 继续排最后。
- [x] 7.2 在 tools/kb-scanner 执行 OpenSpec strict、内容/链接/格式检查，确认全部任务与质量门槛完成后给出下一步同步归档命令；不自动归档、提交、推送或部署。
