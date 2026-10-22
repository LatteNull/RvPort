## Purpose

定义项目优化闭环节点如何汇总当前源码的构建与测试验证结论、展示历史优化轮次，并引导用户执行唯一合理的后续动作。

## Requirements

### Requirement: Optimization cycle overview

系统 SHALL 使用 `optimize` readiness 与 `optimization-cycles/latest` 展示当前轮次；CURRENT、STALE、EMPTY 和失败语义遵循 project-stage-runtime。

#### Scenario: Current cycle is available

- **WHEN** a user opens the optimization-closure node for a project with an active optimization cycle
- **THEN** the Drawer shows the cycle number, source revision, status, and available stage summaries

#### Scenario: Current cycle is unavailable

- **WHEN** a user opens the optimization-closure node for a project without an optimization cycle
- **THEN** Drawer SHALL 按 readiness 与 freshness 展示实际缺失条件或当前轮次不可用状态，不将所有空结果都解释为未导入源码

### Requirement: Optimization cycle history and detail

The system SHALL provide a server-paginated list of optimization cycles and an in-Drawer detail view for a selected cycle.

#### Scenario: User filters or pages cycle history

- **WHEN** a user changes a supported history filter or page
- **THEN** the system requests and displays the corresponding server page

#### Scenario: User opens a cycle detail

- **WHEN** a user selects a cycle from the history list
- **THEN** the Drawer switches to that cycle's detailed stage summary without opening a nested overlay

### Requirement: Optimization stage navigation

The system SHALL provide navigation from optimization summaries to executable downstream stages without creating optimization tasks.

#### Scenario: User needs another build or test run

- **WHEN** a cycle summary shows missing or unsuccessful build or test results
- **THEN** the Drawer provides navigation to the relevant existing validation stage

#### Scenario: User is ready to deliver

- **WHEN** 当前轮次的构建、测试及双端结果比较均满足交付条件
- **THEN** the Drawer provides navigation to the archive stage

### Requirement: 优化闭环必须回答本轮是否收敛

优化闭环 SHALL 使用 `optimize` readiness 和 `optimization-cycles/latest` 组织本轮结论、闭环进度、问题收敛、验证结果和待处理事项。

#### Scenario: 当前轮次存在

- **WHEN** optimization latest 为 `CURRENT`
- **THEN** 页面 SHALL 展示轮次、源码版本、结论原因、开始时间和历史入口
- **AND** 双端结果比较未通过、失败或无法判断时 SHALL NOT 提供进入归档的主操作
- **AND** Footer SHALL 只保留由本轮结论决定的一个主操作
