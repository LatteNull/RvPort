## ADDED Requirements

### Requirement: 候选分类必须与事实采集分离
Scanner SHALL 保留原始 Evidence、NormalizedFact、基础图和 FactProofDemand；后续 Classifier SHALL 仅在完整、同范围语义排除 proof 存在时省略对应候选的迁移 Classification。无证明或不完整 SHALL 保持 unknown 或已有有效执行 proof 结论，MUST NOT 因业务名称黑名单过滤事实。

#### Scenario: 数据名称但没有自动证明
- **WHEN** _7Z_X86、BOOT_PLATFORM_X86、CKSUM_SHA512 或 CRC32 已被检测但没有完整角色证明
- **THEN** fact SHALL 保留，无法确定执行依赖时 SHALL 表达 unknown
- **AND** 人工识别的数据用途 MUST NOT 被伪装为 scanner 已有证明

#### Scenario: 完整 occurrence 数据角色证明
- **WHEN** has_semantic_role relation 指向 algorithm/data_format/output_platform semantic_role Entity，且同 factId、subjectId、configuration、occurrence scopeComplete、原始 matchedEvidenceIds 和完整连通 proof 均匹配
- **THEN** Classifier SHALL 不为此 candidate 生成迁移 Classification，并保留 Observation、fact 和聚合 INFO 审计依据
- **AND** confirmed_local 执行依赖 MUST NOT 由候选排除门禁降级

#### Scenario: 排除输入不完整或冲突
- **WHEN** role/proof 为 partial、配置或 subject 不符、引用失效、scope 未闭合、存在 execution role 冲突或超过查询预算
- **THEN** 该输入 MUST NOT 成为排除依据
- **AND** 系统 SHALL 保留未知/完整执行 proof 边界供后续机制补齐

### Requirement: 角色证明消费不得冒充自动用途识别
本 change SHALL 明确只实现内部语义证明消费合同，不新增跨函数用途推理或后续外部机制接入。数据格式支持、执行实现可移植性、是否存在 RISC-V codec SHALL 分开理解，MUST NOT 相互替代。

#### Scenario: 默认 libarchive 图没有 data-role proofs
- **WHEN** 固定项目现有分析没有产出 has_semantic_role 证明
- **THEN** 审校 SHALL 将相应事实标为仍无法判断，而非“用途排除已成功”
- **AND** 系统 MUST NOT 从缺少 RISC-V codec 推导宿主迁移失败

### Requirement: 重复覆盖必须精确到同一个 fact
Local Detector SHALL 仅在同一 NormalizedFact 的 confirmed matches 覆盖全部触发架构提示的完整 identifier 时省略重复 identifier candidate，保留原始事实/provenance。

#### Scenario: 部分覆盖
- **WHEN** 条件同时有已知 __i386__ 和未知 MY_X86_MODE
- **THEN** candidate SHALL 保留未知依据
- **AND** 不同 occurrence/configuration 或独立 enum selection MUST NOT 被一起去重

### Requirement: 新准入必须具有容器单元与真实项目门禁
每个修改业务模块 SHALL 映射隔离单元并达到至少 90% line / 80% branch；默认 V2/显式 V1、三个固定工件、两份 compiler facts 字节与静态执行边界 SHALL 保持。

#### Scenario: 固定 libarchive 验收
- **WHEN** 两个独立 scanner 进程以 2 CPU/2 GiB/无额外 swap 扫描固定 810 文件
- **THEN** 每次 SHALL 在 300 秒内完成，并逐条审校原 55 条与全部新差异
- **AND** 未决项允许保持 unknown，不能靠减少数量或虚构用途证明通过
