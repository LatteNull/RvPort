## ADDED Requirements

### Requirement: 用途说明与候选排除审计必须使用既有扩展合同

V2 SHALL 在 `org.rvport.kb-scanner.candidate-usage` extension 内提供有界用途摘要。保留的 Finding SHALL 自包含当前事实用途与来源；被排除的候选 SHALL 通过顶层 excludedCandidates 审计表达，不伪造 low Finding。核心 schemaVersion、required 字段和枚举 MUST 保持不变。

#### Scenario: 查看一个未知候选

- **WHEN** 用途闭包有局部数据来源但仍缺调用、配置或逃逸证据
- **THEN** 单个 Finding SHALL 包含可验证的本地来源、unknown 原因和预算信息，而无需另查顶层目录
- **AND** 不增加 classification/assessment/抽象 role 代码节点，不把未知链展示为完整执行证明

#### Scenario: 候选已从迁移分类排除

- **WHEN** 完整纯数据证明使对应 Classification 被省略
- **THEN** 顶层扩展 SHALL 保留有界事实根、配置、原因及真实来源，并区分排除总数、展示数和省略数
- **AND** 原 Observation 与 Fact SHALL 保留，审计不得依赖悬空内部 typed ref 或暗示项目已 ready

### Requirement: 用途展示必须双语有界并保持旧工件兼容

新增用户可见说明 SHALL 同时提供中文和英文，HTML SHALL 默认中文并安全转义；真实代码来源 SHALL 保持默认上下各 20 行和命中高亮，并受现有硬预算约束。默认 V2、显式 V1 与三个 artifact SHALL 保持，V1 不新增必填字段。

#### Scenario: 多用途或来源裁剪

- **WHEN** 多 occurrence、闭包来源或排除审计超过展示上限
- **THEN** SHALL 显式记录裁剪和计数，保留必要事实锚点，不用展示裁剪改变已验证结论
- **AND** 不得复制其他 Evidence 位置或自动合并不同配置

#### Scenario: 合同与报告差异验收

- **WHEN** 执行固定输入新旧 V1/V2/HTML/log 对照
- **THEN** SHALL 逐字段解释实际分类/证据/审计变化，更新扩展文档和合同示例，保留原人工 ledger
- **AND** 无候选输入报告 SHALL 不因本能力变化，事实资产哈希、静态边界与旧消费者忽略 extension 的能力 SHALL 保持
