## ADDED Requirements

### Requirement: 架构家族必须通过既有 extension 自包含展示且不伪造源码

V2 SHALL 使用现有 `extensions` 合同及 `org.rvport.kb-scanner.architecture-family` namespace 输出有界候选目录，并在相关 Finding 的 fact.extensions 内嵌必要家族上下文。核心 schemaVersion、必填字段和枚举 MUST 保持不变；单个 Finding 的解释 MUST NOT 依赖顶层目录或内部 snapshot。纯路径成员 MUST NOT 伪装成代码 fact、occurrence 或 step。

#### Scenario: 用户仅打开一个 intrinsic Finding

- **WHEN** 该 Finding 所在 source file 有架构家族候选
- **THEN** SHALL 在 Finding 内提供成员路径、角色依据、候选/绑定状态及范围，而无需查询顶层 catalog
- **AND** 原始 intrinsic 命中、真实源码链、上下各 20 行及双语 suggestion SHALL 保持

#### Scenario: 只有文件名无命中行

- **WHEN** 成员仅有文件系统路径依据或文件为空
- **THEN** SHALL 在 extension 描述路径，不填写虚假的第 1 行或高亮
- **AND** 不存在迁移 Finding 的家族 SHALL 仍通过有界顶层 extension 可读

#### Scenario: 引用和候选裁剪

- **WHEN** 家族成员或 proof 输出超过预算，或无法在 Finding 内闭合引用
- **THEN** SHALL 记录裁剪/未知原因与计数，仅输出可核查结构描述及有效引用
- **AND** MUST NOT 发布悬空 typed ref 或把未输出成员解释为不存在

#### Scenario: 已有其他 extension

- **WHEN** Finding 同时带有 RPM、Autoconf 或架构枚举补充
- **THEN** 新家族 extension SHALL 合并而非覆盖既有 namespace 内容

### Requirement: 家族展示必须保持双语与既有报告兼容

新增面向用户的候选解释 SHALL 同时提供中文与英文，HTML SHALL 安全转义路径并以中文呈现有界摘要。默认 V2、显式 V1 和 JSON/HTML/log 三个 artifact SHALL 保持；V1 MUST NOT 被强制加入路径-only 代码 Finding 或新增必填字段。

#### Scenario: 旧消费者或显式 V1

- **WHEN** 消费者忽略 extension 或用户选择 V1
- **THEN** 原有 Findings、源码位置和风险结论 SHALL 继续可消费，不要求新后端接入

#### Scenario: 恶意文件名与纯路径摘要

- **WHEN** 家族成员路径包含 HTML 特殊字符且没有代码位置
- **THEN** HTML SHALL 转义展示路径与候选说明，不执行内容、不生成虚假源码链接
