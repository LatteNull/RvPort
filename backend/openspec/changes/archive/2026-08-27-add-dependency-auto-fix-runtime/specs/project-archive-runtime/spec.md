## ADDED Requirements

### Requirement: 归档必须兼容依赖自动修复制品登记
项目归档运行时 SHALL 允许依赖自动修复节点在产生报告或摘要制品时登记归档候选，并 SHALL 在无制品时保持现有归档行为不变。

#### Scenario: 登记依赖自动修复归档候选
- **WHEN** 依赖自动修复任务生成 HTML、JSON 或摘要制品
- **THEN** 后端 SHALL 按全局归档规则登记归档候选
- **AND** 候选 SHALL 关联项目、源码版本、任务、自动修复运行和制品引用
- **AND** 候选的 `nodeType` 或等效字段 SHALL 表达依赖自动修复节点

#### Scenario: 无制品时不登记候选
- **WHEN** 依赖自动修复任务只产生运行记录、条目记录和任务日志
- **THEN** 后端 MAY 不登记归档候选
- **AND** 项目归档 MUST NOT 因没有依赖自动修复制品而失败
