## Purpose

定义 RvPort 前端共享类型、常量与纯函数的复用边界，减少重复实现，同时保留各业务阶段可观察的领域语义。

## ADDED Requirements

### Requirement: Semantically equivalent frontend logic is shared

当多个前端模块对相同输入应用相同规则并期望相同输出时，应用 SHALL 通过类型化共享模块提供该常量或纯函数。共享模块 SHALL 不依赖 React 组件状态、Ant Design 渲染实例或领域 API 请求。

#### Scenario: Build drawers display shared data

- **WHEN** 构建相关 Drawer 展示通用任务状态、解析环境变量或格式化构建时间范围
- **THEN** 它们 SHALL 使用共享的类型化实现
- **AND** 空值、同日时间范围和键值解析的展示结果 SHALL 保持一致

### Requirement: Business-specific semantics remain local

应用 SHALL NOT 仅因名称或枚举值相似而合并具有不同领域文案、错误策略或交互副作用的实现。

#### Scenario: Stage-specific status text is rendered

- **WHEN** 不同业务阶段需要体现其专有状态语义
- **THEN** 阶段 SHALL 能够保留该语义
- **AND** 共享基础设施 SHALL 不覆盖或改变该文案
