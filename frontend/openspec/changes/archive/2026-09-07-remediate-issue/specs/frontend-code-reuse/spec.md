## ADDED Requirements

### Requirement: 阶段前置条件必须复用一致结构

多个 Stage Drawer 展示执行前置条件时 SHALL 复用共享前置条件展示结构，组件 SHALL 只接收页面已经转换完成的状态、事实和操作，不得自行请求领域 API。

#### Scenario: 展示多个前置条件

- **WHEN** readiness 返回一个或多个 prerequisite
- **THEN** 页面 SHALL 为每个条件展示名称和中文状态
- **AND** 恢复操作 SHALL 归属对应条件，不得只展示一个无法解释其他阻断项的总操作
- **AND** 条件数量变化时布局 SHALL 自适应换行，不依赖固定分割线

#### Scenario: 前置条件满足

- **WHEN** 当前操作需要的 prerequisite 均为 `SATISFIED`
- **THEN** 共享结构 SHALL 使用成功语义展示可执行状态
- **AND** 页面 MAY 继续展示当前源码、环境或构建等领域事实

### Requirement: 阶段页面状态必须复用 StageStateNotice

知识库扫描、依赖分析、评估报告、优化闭环和归档 SHALL 使用纯展示组件 `StageStateNotice` 表达 prerequisite、ready、processing、execution-error 和 request-error 状态。

#### Scenario: 前置条件不满足

- **WHEN** 页面判断当前操作不可执行
- **THEN** `StageStateNotice` SHALL 使用 prerequisite 语义展示全部相关条件及恢复入口
- **AND** 页面 SHALL NOT 同时展示普通暂无结果状态或不可执行的主操作

#### Scenario: 首次执行就绪

- **WHEN** readiness 满足且 latest 为 `EMPTY`
- **THEN** `StageStateNotice` SHALL 使用 ready 语义展示已满足事实和首次执行主操作

#### Scenario: 正在执行

- **WHEN** latest execution 为 `PENDING`、`QUEUED` 或 `RUNNING`
- **THEN** `StageStateNotice` SHALL 使用 processing 语义展示进度、消息和可用查看操作

#### Scenario: 最近执行失败

- **WHEN** latest execution 为 `FAILED`、`CANCELLED` 或 `TIMEOUT`
- **THEN** `StageStateNotice` SHALL 使用 execution-error 语义保留失败状态、原因和时间
- **AND** 业务重试 SHALL 使用“重新执行”类文案，不得与接口“重新加载”混淆

#### Scenario: 查询失败

- **WHEN** readiness 或 latest 请求失败
- **THEN** `StageStateNotice` SHALL 使用 request-error 语义展示失败原因和重新加载操作
- **AND** 页面 SHALL NOT 将接口失败呈现为业务执行失败

### Requirement: 阶段操作必须保持单一主次层级

阶段页面同时存在业务操作、重新执行和历史入口时 SHALL 保持一个明确的主操作。

#### Scenario: 展示操作组

- **WHEN** 当前页面存在多个操作
- **THEN** 核心业务操作 SHALL 是唯一主按钮
- **AND** 重新执行 SHALL 使用普通按钮
- **AND** 查看历史 SHALL 使用文字链接并排在操作组末尾
- **AND** 依赖分析存在自动修复时，“自动修复依赖” SHALL 是结果页唯一主按钮

### Requirement: 依赖分析必须提供受控自动修复入口

当前 Context 的成功依赖分析结果 MAY 提供自动修复操作，该操作 SHALL 只在当前 RISC-V 目标环境安装后端返回的候选软件包，不得暗示修改源码。

#### Scenario: 加载候选项

- **WHEN** 用户打开自动修复
- **THEN** frontend SHALL 请求 GET `/api/dependency-analyses/{analysisId}/auto-fix-candidates`
- **AND** 默认选择 SHALL 使用后端 `defaultSelected`
- **AND** 页面 SHALL 展示依赖、风险、安装包和选择依据

#### Scenario: 提交自动修复

- **WHEN** 用户确认至少一个候选项
- **THEN** frontend SHALL 请求 POST `/api/dependency-analyses/{analysisId}/auto-fixes`
- **AND** 默认 SHALL 设置 `rerunDependencyAnalysis=true`
- **AND** 用户 MAY 在提交前关闭修复后重新分析

#### Scenario: 历史分析或候选项不可用

- **WHEN** 分析不属于当前 Context、候选列表为空或候选请求失败
- **THEN** 页面 SHALL 禁止提交自动修复
- **AND** 历史分析 SHALL 保持只读
- **AND** 请求失败 SHALL 提供重新加载操作

### Requirement: 报告纳入状态必须在列表与详情保持一致

知识库 finding 与依赖分析结果 SHALL 在当前 Context 下提供互斥的单条“纳入报告 / 排除”操作，历史 Context 保持只读。

#### Scenario: 修改当前结果的纳入状态

- **WHEN** 用户对当前 finding 或依赖结果执行纳入或排除
- **THEN** 未纳入或已排除时 SHALL 只提供“纳入报告”
- **AND** 已纳入时 SHALL 只提供“排除”
- **AND** 更新成功 SHALL 同步刷新详情、来源列表、报告 readiness 和受影响的聚合结果

#### Scenario: 查看历史结果

- **WHEN** finding 或依赖结果不属于当前源码或当前环境配置
- **THEN** 列表和详情 Footer SHALL NOT 提供纳入或排除操作
- **AND** 页面 SHALL 明确其为历史只读记录

### Requirement: 共享记录标题必须表达真实返回层级

具有当前结果、历史列表和历史详情的 Drawer SHALL 使用共享记录标题表达当前位置，并在关闭后回到默认当前视图。

#### Scenario: 从历史详情返回

- **WHEN** 用户从历史列表进入详情
- **THEN** 返回操作 SHALL 回到历史列表
- **AND** 从最新结果进入的详情 SHALL 返回最新结果
- **AND** 页面 SHALL NOT 跳过真实上一层或保留上一次打开的错误路径
