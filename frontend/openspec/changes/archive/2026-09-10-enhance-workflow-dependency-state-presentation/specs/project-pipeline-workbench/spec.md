## ADDED Requirements

### Requirement: 项目执行上下文展示最近任务

项目流水线工作台 SHALL 使用 Overview V2 的 `recentTasks` 展示当前或最近任务，而不是重复展示 Workflow 推荐阶段。

#### Scenario: 存在活动任务

- **WHEN** `recentTasks` 包含 `RUNNING`、`QUEUED` 或 `PENDING` 任务
- **THEN** 执行上下文 SHALL 优先展示活动任务的类型、状态、进度和消息

#### Scenario: 仅存在终态任务

- **WHEN** `recentTasks` 不包含活动任务但至少包含一条终态任务
- **THEN** 执行上下文 SHALL 展示列表中的第一条最近任务及其终态和消息

#### Scenario: 不存在任务

- **WHEN** `recentTasks` 为空
- **THEN** 执行上下文 SHALL 显示尚无任务记录的空状态

#### Scenario: 查看最近任务列表

- **WHEN** 用户点击执行上下文中的“最近任务 N”入口
- **THEN** 系统 SHALL 按后端返回顺序展示最多五条任务的类型、状态、时间和消息
- **AND** 活动任务 SHALL 额外展示当前标记和执行进度

### Requirement: Workflow 前端辅助状态

项目流水线工作台 SHALL 根据前端固定的节点前置关系和 Overview 阶段事实状态，为尚未执行的节点推导展示用辅助状态。

#### Scenario: 节点前置阶段均已完成

- **WHEN** 节点自身为 `PENDING` 且所有展示级前置节点均为 `DONE`
- **THEN** 前端 SHALL 将该节点的辅助状态推导为 `READY`

#### Scenario: 节点等待前置阶段

- **WHEN** 节点自身为 `PENDING`，且至少一个前置节点尚未 `DONE`
- **AND** 不存在已失败或已被阻塞的前置节点
- **THEN** 前端 SHALL 将该节点的辅助状态推导为 `WAITING`
- **AND** SHALL 保留尚未完成的直接前置节点，用于用户可见说明

#### Scenario: 节点因前置阶段被阻塞

- **WHEN** 节点自身为 `PENDING`，且任一前置节点为 `BLOCKED` 或其辅助状态为 `BLOCKED`
- **THEN** 前端 SHALL 将该节点的辅助状态推导为 `BLOCKED`
- **AND** SHALL 将阻塞语义继续传递到尚未执行的后续节点

#### Scenario: 节点已进入自身生命周期

- **WHEN** 节点状态为 `RUNNING`、`DONE` 或 `BLOCKED`
- **THEN** 前端 SHALL 优先展示后端节点事实状态
- **AND** 节点事实状态图标 SHALL NOT 被前端辅助状态替换

#### Scenario: 阻塞传播经过已有事实状态的节点

- **WHEN** 任一节点存在阻塞根节点
- **THEN** 前端 SHALL 将阻塞展示状态传播到尚未执行的后续前向节点
- **AND** 传播 SHALL 在 `RUNNING` 或 `DONE` 节点处停止
- **AND** 已运行或已完成节点 SHALL 保持其事实状态和原有视觉

#### Scenario: 反馈连线不参与前置判断

- **WHEN** Workflow 包含 `manual -> assets` 或 `optimize -> assets` 等 feedback edge
- **THEN** 前端 SHALL NOT 将 feedback edge 的源节点视为目标节点的必需前置

#### Scenario: 辅助状态不作为执行依据

- **WHEN** 用户打开阶段 Drawer 或尝试发起任务
- **THEN** 前端 SHALL NOT 使用 Workflow 辅助状态替代后端 readiness 或任务创建接口的权威校验

### Requirement: Workflow 依赖语义展示

项目流水线工作台 SHALL 通过连线、节点卡片和动态说明表达节点之间的完成、运行、等待和阻塞语义。

#### Scenario: 桌面画布展示依赖状态

- **WHEN** 用户在桌面视口查看 Workflow
- **THEN** 完成、运行、等待和阻塞路径 SHALL 使用可区分的连线样式
- **AND** 节点 SHALL 只使用一个图标表达后端返回的节点自身状态
- **AND** 节点第二行 SHALL 展示可开始、等待对象或阻塞来源等动态说明

#### Scenario: 尚未执行的前向链路展示阻塞

- **WHEN** 任一节点事实状态为 `BLOCKED`
- **THEN** 从该节点开始、直至事实状态边界的尚未执行节点和连线 SHALL 使用红色阻塞样式
- **AND** feedback edge SHALL 保持独立的回流样式

#### Scenario: 并行分析输入汇合

- **WHEN** 知识库扫描和依赖分析连接到评估报告
- **THEN** 画布 SHALL 在评估报告前展示单一输入汇合点
- **AND** 汇合点 SHALL 以 `n/2` 显示已完成的直接输入数量

#### Scenario: 窄屏列表展示依赖状态

- **WHEN** 用户在窄屏查看 Workflow 列表
- **THEN** 列表 SHALL 直接展示节点的辅助状态文案
- **AND** SHALL NOT 要求用户通过 hover 获取关键等待或阻塞信息

#### Scenario: Workflow 节点不展示固定业务副标题

- **WHEN** Workflow 节点渲染
- **THEN** 节点 SHALL 展示节点名称、事实状态标记和动态状态说明
- **AND** SHALL NOT 展示固定业务副标题

#### Scenario: Workflow 区分主路径和处理支路

- **WHEN** 页面展示评估之后的阶段
- **THEN** 构建验证、自动化测试和归档 SHALL 保持水平主路径
- **AND** 人工修复和优化处理 SHALL 对齐在对应源节点下方并从源节点底部引出
- **AND** 自动化测试到归档的主路径 SHALL 保持与其他主路径相近的紧凑间距
- **AND** 返回源码管理的 feedback edge SHALL 显示回流语义文案

#### Scenario: Workflow 使用主题分组框

- **WHEN** 页面在桌面视口渲染 Workflow 分组
- **THEN** 画布 SHALL 使用“基础准备”、“扫描与分析”、“评估与处理”和“验证与交付”分组框
- **AND** 分组框 SHALL 使用可区分的低饱和主题色、实体边界和标题标识
