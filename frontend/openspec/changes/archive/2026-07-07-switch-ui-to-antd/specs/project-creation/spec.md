## MODIFIED Requirements

### Requirement: Shared business modal shell

前端 SHALL 提供可复用的业务弹窗外壳，用于承载与默认 Ant Design Modal 视觉不同的业务弹窗。

#### Scenario: Business modal renders

- **WHEN** 业务弹窗展示
- **THEN** 它 SHALL 使用 Ant Design Modal 行为，同时应用项目弹窗的 header、body spacing、footer actions、默认宽度、关闭入口和遮罩视觉约定

#### Scenario: Business modal width is overridden

- **WHEN** 功能向共享业务弹窗外壳传入 modal width
- **THEN** 外壳 SHALL 将该 width 透传给 Ant Design Modal，而不是强制使用单一全局宽度

#### Scenario: Business modal remains generic

- **WHEN** 功能使用共享业务弹窗外壳
- **THEN** 外壳 SHALL NOT 包含项目专属表单字段、API 调用或 query invalidation 逻辑

### Requirement: Create project form

新建项目弹窗 SHALL 使用 Ant Design Form 控件采集 MVP 项目创建字段。

#### Scenario: Create project form opens with defaults

- **WHEN** 新建项目弹窗打开
- **THEN** 表单 SHALL 展示空的项目名称和项目描述字段，源架构默认 `x86_64`，目标架构默认 `riscv64`，源码输入方式默认稍后在源码管理页导入

#### Scenario: Create project form follows modal design

- **WHEN** 新建项目弹窗在桌面视口渲染
- **THEN** 弹窗 SHALL 对齐 Figma 节点 `14:296`，使用 800px 弹窗宽度、单列表单字段、分区标题和 footer action row

#### Scenario: Required project name is missing

- **WHEN** 用户提交未填写项目名称的新建项目表单
- **THEN** Ant Design Form validation SHALL 阻止提交，并展示字段校验消息
