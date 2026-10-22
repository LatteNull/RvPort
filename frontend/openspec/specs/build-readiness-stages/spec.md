# build-readiness-stages Specification

## Purpose

定义 x86-build 节点的单端构建配置、readiness、分页记录和日志。依赖分析由 dependency-analysis 独立定义。

## Requirements

### Requirement: 当前源码的 x86 构建

x86 构建 SHALL 使用 `x86-build` readiness 的 `ACTIVE_SOURCE` 与 `SOURCE_ENVIRONMENT`，提交 `SOURCE_ONLY` 范围的构建任务。

#### Scenario: 提交构建

- **WHEN** 前置条件满足且用户提交合法命令、超时和环境变量
- **THEN** 页面 SHALL 使用 readiness Context 的源码版本创建 x86 构建
- **AND** 每个构建任务自行准备源码，不要求用户先提交独立源码部署任务

#### Scenario: 前置条件不可用

- **WHEN** 当前源码或源环境未满足条件
- **THEN** 页面 SHALL 展示对应状态和前往源码或环境管理的恢复入口

### Requirement: x86 构建必须以记录表作为主视图

x86 构建 SHALL 展示当前 readiness Context 下的 `SOURCE_ONLY` 分页记录，并使用 `SOURCE_ONLY latest` 标记当前记录和初始化最近一次构建命令。

#### Scenario: 打开 x86 构建

- **WHEN** x86 构建 Drawer 打开
- **THEN** 页面 SHALL 并行读取 `x86-build` readiness、分页构建记录和 `SOURCE_ONLY latest`
- **AND** latest `result.id` 对应的表格行 SHALL 标记“当前”
- **AND** latest 为 `CURRENT` 时 SHALL 优先使用最近一次 `command` 初始化配置
- **AND** 当前 Context 无构建记录时 SHALL 使用默认命令
- **AND** 异步 latest 刷新 SHALL NOT 覆盖用户已经编辑的命令

#### Scenario: 筛选构建记录

- **WHEN** 用户选择任务状态
- **THEN** List 请求 SHALL 附加 `status` 并将其纳入 Query Key
- **AND** 清除筛选 SHALL 仍保持当前源码、当前源环境和 `SOURCE_ONLY` 范围
- **AND** 状态、创建时间、日志和取消操作 SHALL 保持独立列

### Requirement: x86 构建日志与取消

构建记录 SHALL 支持进入共享任务日志视图和确认取消非终态任务，任务状态刷新遵循 project-stage-runtime。

#### Scenario: 查看日志或取消

- **WHEN** 用户选择记录的日志或确认取消
- **THEN** 页面 SHALL 展示该记录的 task-log-viewer，或提交该记录的取消请求
- **AND** 取消请求成功 SHALL 只提示请求已提交，不伪造终态
