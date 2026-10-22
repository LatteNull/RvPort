## ADDED Requirements

### Requirement: 两项迁移风险分析的阶段入口

前端 SHALL 为强弱内存序分析与浮点精度扫描提供独立阶段入口，并在 Workflow Drawer 与 Step Panel 复用对应阶段业务内容。

#### Scenario: 查看分析阶段

- **WHEN** 用户点击任一新分析节点、Step 导航或访问其有效深链接
- **THEN** 页面 SHALL 在当前视图的阶段载体中展示该分析
- **AND** 打开阶段 SHALL NOT 自动创建任务

### Requirement: 分析阶段沿用既有状态体系

两项分析 SHALL 沿用既有阶段事实状态与展示辅助状态，不新增能力占位状态。

#### Scenario: 展示分析阶段事实

- **WHEN** Overview 返回新分析阶段事实
- **THEN** 节点及阶段内容 SHALL 展示对应的 `PENDING`、`RUNNING`、`DONE` 或 `BLOCKED` 状态
- **AND** SHALL 复用现有前置条件辅助状态，不伪造执行结果

#### Scenario: 分析尚未执行

- **WHEN** 阶段尚无执行记录或结果
- **THEN** 页面 SHALL 展示真实空状态、输入说明及 readiness 允许的创建操作
- **AND** SHALL NOT 以接口开发进度替代业务阶段状态

#### Scenario: 分析请求失败

- **WHEN** 分析接口返回权限、网络或业务失败
- **THEN** 页面 SHALL 按真实失败语义显示错误与适用恢复路径
- **AND** SHALL NOT 将请求失败转换成虚构的能力状态

### Requirement: 按后端契约执行分析

前端 SHALL 使用已确认的 stage ID、请求、响应、readiness 与任务事件契约，遵循 request-client 与 project-stage-runtime 的共享边界。

#### Scenario: 前置输入不可用

- **WHEN** readiness 表明当前源码、x86 构建、分析工具不满足条件，或创建接口表明共享 BC 不可用
- **THEN** 页面 SHALL 展示后端提供的原因和适用的上游处理入口
- **AND** SHALL NOT 仅凭 x86 构建成功或画布辅助状态允许扫描

#### Scenario: 用户主动启动分析

- **WHEN** 接口已接入且用户明确发起分析
- **THEN** 页面 SHALL 调用真实创建接口并依据服务端任务标识展示执行状态
- **AND** SHALL 处理进行中、失败及终态，通过既有任务事件机制刷新相关数据

### Requirement: 专项分析使用真实数据

两项分析 SHALL 使用后端正式接口，不以示例数据填充空记录或请求失败。

#### Scenario: 真实接口已发布

- **WHEN** 用户查看任一专项分析
- **THEN** 页面 SHALL 使用 `memory-order-analysis` 或 `floating-point-analysis` 的正式阶段 ID 查询最新执行、readiness 和分页历史
- **AND** SHALL 将完整工具证据保留在详情中，后端未提供源码片段时明确提示缺失

#### Scenario: 结果纳入报告

- **WHEN** 用户确认当前源码的已发布 finding 或 source candidate
- **THEN** 前端 SHALL 使用 `MEMORY_ORDER_FINDING` 或 `FLOATING_POINT_FINDING` 的既有报告输入操作
- **AND** SHALL NOT 自动确认候选或将旧源码结果加入当前报告

### Requirement: 分析风险与完整性独立表达

前端 SHALL 分别展示执行状态、结果完整性及风险结论，并保留后端提供的未知、跳过、失败和源码证据。

#### Scenario: 返回部分分析结果

- **WHEN** 扫描结果包含 partial、unknown、skipped 或 failed 的分析范围
- **THEN** 页面 SHALL 显示已分析与未确定的范围，不将未知项隐藏为成功

#### Scenario: 没有风险发现

- **WHEN** 结果返回零 finding
- **THEN** 页面 SHALL 展示真实空结果与分析边界
- **AND** SHALL NOT 将零 finding 表达为全程序安全或迁移无风险

#### Scenario: 查看执行历史与源码证据

- **WHEN** 用户查看历史分析或风险详情
- **THEN** 页面 SHALL 显示后端给出的源码版本、新鲜度及证据
- **AND** SHALL 沿用阶段共享的日志、正文滚动及列表详情往返规则
