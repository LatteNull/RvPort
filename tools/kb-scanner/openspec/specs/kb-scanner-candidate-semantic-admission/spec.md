# KB Scanner Candidate Semantic Admission Specification

## Purpose

定义候选事实与迁移分类分离、完整同范围语义证明准入、unknown 保留、精确重复覆盖，以及静态分析和容器验证边界。

## Requirements

### Requirement: 候选分类必须与事实采集分离

Scanner SHALL 保留原始 Evidence、NormalizedFact、基础图和 FactProofDemand；后续 Classifier SHALL 仅在完整、同范围语义排除 proof 存在时省略对应候选的迁移 Classification。无证明或不完整 SHALL 保持 unknown 或已有有效执行 proof 结论，MUST NOT 因业务名称黑名单过滤事实。内部允许的数据角色 SHALL 包括 algorithm、data_format、output_platform 和不强行断言业务领域的 non_execution_data；自动证明还须通过使用闭包、计数与引用一致性验证。

#### Scenario: 数据名称但没有自动证明

- **WHEN** _7Z_X86、BOOT_PLATFORM_X86、CKSUM_SHA512 或 CRC32 已被检测但没有完整角色证明
- **THEN** fact SHALL 保留，无法确定执行依赖时 SHALL 表达 unknown
- **AND** 人工识别的数据用途 MUST NOT 被伪装为 scanner 已有证明

#### Scenario: 完整 occurrence 数据角色证明

- **WHEN** has_semantic_role 指向允许的数据角色，且同 factId、subjectId、configuration、occurrence scopeComplete、原始 matchedEvidenceIds、完整连通且未截断 proof 和可核查闭包均匹配
- **THEN** Classifier SHALL 不为此 candidate 生成迁移 Classification，并保留 Observation、fact 和聚合 INFO 审计依据
- **AND** confirmed_local 执行依赖 MUST NOT 由候选排除门禁降级

#### Scenario: 排除输入不完整或冲突

- **WHEN** role/proof 为 partial、配置或 subject 不符、引用失效、scope 未闭合、存在 execution role 冲突、摘要与使用计数不符或超过查询预算
- **THEN** 该输入 MUST NOT 成为排除依据
- **AND** 系统 SHALL 保留未知/完整执行 proof 边界供后续机制补齐

### Requirement: 角色证明消费不得冒充自动用途识别

Scanner SHALL 区分证明 producer 与消费门禁，并仅在默认用途 Analyzer 实际生成闭包证明后声明自动用途识别。首版自动能力 SHALL 限于受支持的局部无逃逸纯数据使用，跨函数或外部机制不得伪装为已支持。数据格式支持、执行实现可移植性、是否存在 RISC-V codec SHALL 分开理解，MUST NOT 相互替代。

#### Scenario: 默认 libarchive 图没有完整 data-role proofs

- **WHEN** 固定项目实际分析仍无法产出完整 has_semantic_role 证明
- **THEN** 审校 SHALL 将相应事实标为仍无法判断，而非“用途排除已成功”
- **AND** 系统 MUST NOT 从缺少 RISC-V codec 推导宿主迁移失败

#### Scenario: 默认管线产出局部纯数据证明

- **WHEN** 真实语法输入完成采集、归一化及闭包查询，未使用人工注入 role
- **THEN** SHALL 将实际支持范围与 proof provenance 交给现有准入门禁验证
- **AND** 减少的 Finding 数不得被替代为所有算法、codec 或架构枚举已支持的声明

### Requirement: 重复覆盖必须精确到同一个 fact
Local Detector SHALL 仅在同一 NormalizedFact 的 confirmed matches 覆盖全部触发架构提示的完整 identifier 时省略重复 identifier candidate，保留原始事实/provenance。

#### Scenario: 部分覆盖
- **WHEN** 条件同时有已知 __i386__ 和未知 MY_X86_MODE
- **THEN** candidate SHALL 保留未知依据
- **AND** 不同 occurrence/configuration 或独立 enum selection MUST NOT 被一起去重

### Requirement: 新准入必须具有容器单元与真实项目门禁

每个新增或修改业务模块 SHALL 映射隔离单元，项目整体及每个受影响模块 SHALL 达到至少 90% line / 90% branch，统计包含未加载的自有代码；默认 V2/显式 V1、三个固定工件、两份 compiler facts 字节与静态执行边界 SHALL 保持。

#### Scenario: 固定 libarchive 验收

- **WHEN** 两个独立 scanner 进程以 2 CPU/2 GiB/无额外 swap 扫描经确认的固定 822 文件（保留旧 810 文件清单，追加 12 个 CMake 文件）
- **THEN** 每次 SHALL 在 300 秒内完成，并逐条审校原 55 条与全部新差异，同时以本 change 修改前实际输出为差异基线
- **AND** 未决项允许保持 unknown，不能靠减少数量或虚构用途证明通过

#### Scenario: 隔离单元覆盖验收

- **WHEN** 独立容器运行新的 producer/consumer 与受影响管线单元门禁
- **THEN** 正常、边界、异常和误排除反例 SHALL 有有效断言，并记录整体/逐模块行与分支覆盖率及报告位置
- **AND** 组件/CLI/真实性能测试 MUST NOT 替代隔离单元覆盖，失败或不足不得标记任务完成
