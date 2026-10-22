## Purpose

为知识库扫描的单条 Finding 提供可理解、可追溯且可操作的详情视图，使用户能够从迁移结论定位到具体代码和证据，并在当前结果与历史记录中采取正确的后续动作。

## ADDED Requirements

### Requirement: Finding 详情形成连续的判断阅读路径

系统 SHALL 在知识库扫描 Drawer 的二级页面中，以迁移判断为主线展示 Finding 详情，并按“结论摘要、主要代码证据、判断依据、处理建议”的顺序组织信息。

#### Scenario: 展示完整的 Finding 详情

- **WHEN** Finding 详情加载成功且结构化结论与证据可用
- **THEN** 系统 SHALL 优先展示标题、原因、风险、阻塞性、可处理性、分析完整度和置信度
- **AND** 系统 SHALL 在结论之后展示主要代码位置、判断依据和建议下一步
- **AND** 系统 SHALL NOT 要求用户先阅读原始 JSON 才能理解结论

#### Scenario: 展示业务与分析状态

- **WHEN** Finding 同时包含业务状态和 Scanner 分析状态
- **THEN** 系统 SHALL 分别表达 Finding 的业务处理状态与分析完整度
- **AND** 系统 SHALL 将已知枚举转换为一致的简体中文语义
- **AND** 系统 SHALL NOT 将两类状态合并为一个含义不明的标签

### Requirement: 多命中位置与代码证据保持联动

系统 SHALL 使用 Finding 的主要命中位置作为默认代码上下文，并允许用户在同一详情页查看其他命中位置。

#### Scenario: 默认展示补充代码上下文的完整窗口

- **WHEN** 主要 occurrence 与 `/findings/{id}/code-context` 均可用
- **THEN** 系统 SHALL 默认展示代码上下文接口返回的全部行并高亮 Finding 命中范围
- **AND** 系统 SHALL NOT 以 occurrence 内嵌的更小窗口替代该默认视图

#### Scenario: 默认选择主要命中位置

- **WHEN** Finding 提供 `primaryOccurrenceId` 且该 ID 对应一个 occurrence
- **THEN** 系统 SHALL 默认选中该 occurrence
- **AND** 系统 SHALL 展示该位置的文件、行列范围和代码上下文

#### Scenario: 主要位置不可识别

- **WHEN** `primaryOccurrenceId` 缺失、无效或没有对应 occurrence
- **THEN** 系统 SHALL 按服务端返回顺序选择第一个有效位置
- **AND** 系统 SHALL NOT 以“后端待提供”等实现占位文案打断主要阅读路径

#### Scenario: 切换命中位置

- **WHEN** 用户选择另一个 occurrence
- **THEN** 系统 SHALL 同步更新文件位置、代码证据、配置、选择状态和该位置的原因信息
- **AND** 系统 SHALL 以可见选中态和可访问名称标识当前 occurrence

#### Scenario: 所选位置没有代码上下文

- **WHEN** 所选 occurrence 只有位置元数据而没有可展示的源码行
- **THEN** 系统 SHALL 保留文件和范围信息并说明该位置没有可用代码上下文
- **AND** 系统 SHALL 继续允许用户查看其他结构化证据和处理建议

### Requirement: 判断依据保持可追溯且能安全降级

系统 SHALL 使用结构化 `fact`、`conclusion`、`occurrences` 和 `evidenceChain` 解释 Finding 的事实来源与推理关系，并区分完整证据、不完整证据和无法判断。

#### Scenario: 选择带源码的证据步骤

- **WHEN** 用户选择的 evidence step 包含 `source.context.lines`
- **THEN** 系统 SHALL 在同一证据工作区切换到该步骤的文件、范围、代码与高亮
- **AND** 当该步骤源码位于另一文件时，工作区标题 SHALL 同步展示该文件与范围
- **AND** 系统 SHALL 提供返回主要代码上下文的入口

#### Scenario: 选择不带源码的证据步骤

- **WHEN** 用户选择 Classification、Assessment 或其他没有 `source` 的 evidence step
- **THEN** 系统 SHALL 保留最近一次有效代码视图并说明该步骤没有直接源码
- **AND** 系统 SHALL NOT 清空代码或伪造源码位置

### Requirement: 详情复用所属扫描上下文

系统 SHALL 复用进入详情前已经加载的当前或历史 scan，并避免为渲染 Finding 详情重复获取同一 scan。

#### Scenario: 从当前扫描结果进入详情

- **WHEN** 当前结果页已通过 latest 接口取得 scan 且用户打开 Finding
- **THEN** 系统 SHALL 复用该 scan 判断报告操作资格并提供 `sourceRevisionId`
- **AND** 系统 SHALL NOT 因进入详情再次调用 `GET /kb-scans/{scanId}`

#### Scenario: 展示完整证据路径

- **WHEN** `evidenceChain.primaryPath` 可以解析为有序步骤
- **THEN** 系统 SHALL 按主路径顺序展示步骤
- **AND** 每一步 SHALL 展示其标题、依据和完整度
- **AND** 左侧路径中的长标题与依据 SHALL 单行省略，当前选中步骤的完整内容 SHALL 在右侧代码区展示
- **AND** 系统 SHALL NOT 在主要界面展示可能增加理解成本的内部关系枚举

#### Scenario: 主路径缺失但存在证据步骤

- **WHEN** `primaryPath` 缺失或无法解析且 `steps` 非空
- **THEN** 系统 SHALL 使用服务端步骤顺序展示可用证据
- **AND** 系统 SHALL 明确该展示不代表已确认的完整主路径

#### Scenario: 证据存在断点或预算截断

- **WHEN** 证据链包含 `breaks` 或 `budget.truncated=true`
- **THEN** 系统 SHALL 在判断依据附近说明断点阶段、可理解的原因和结论可能不完整
- **AND** 系统 SHALL NOT 将不完整证据展示为确定结论

#### Scenario: 结构化字段缺失

- **WHEN** Finding 的部分结构化字段为空但旧版投影字段或原始 `evidence` 中存在等价信息
- **THEN** 系统 SHALL 使用明确且可测试的兼容优先级展示可用信息
- **AND** 系统 SHALL 对无法恢复的信息使用中性缺失说明，不展示内部字段名或开发占位语

### Requirement: 详情操作符合当前与历史上下文

系统 SHALL 在 Finding 详情中清楚表达处理建议和报告纳入状态，并仅允许当前 Context 的结果改变报告输入。

#### Scenario: 操作当前 Finding

- **WHEN** 用户查看当前 Context 的 Finding 详情
- **THEN** 系统 SHALL 在处理建议附近提供互斥的“纳入报告 / 排除”操作及当前状态
- **AND** 空间允许时处理建议、报告状态与操作 SHALL 位于同一行动行，窄屏可自然换行
- **AND** 操作成功后 SHALL 刷新或校准当前 Finding、所属结果列表和报告 readiness

#### Scenario: 查看历史 Finding

- **WHEN** 用户从历史扫描记录进入 Finding 详情
- **THEN** 系统 SHALL 显示只读标识和当时的 Finding 内容
- **AND** 系统 SHALL NOT 提供会改变当前报告输入的操作

### Requirement: 诊断信息不干扰主要任务

系统 SHALL 将原始扫描数据保留为次级诊断入口，并为详情请求与代码上下文请求提供独立的加载和失败反馈。

#### Scenario: 紧凑展示决策与证据

- **WHEN** 用户打开 Finding 详情
- **THEN** 风险、阻塞性与置信度 SHALL 在头部同一决策信息区展示
- **AND** 判断置信度的标签与数值 SHALL 单行展示
- **AND** 代码查看器、位置选择与判断路径 SHALL 共享一个“证据工作区”标题，不重复展示同层级的“代码证据”标题
- **AND** 宽屏下判断路径与代码面板 SHALL 等高，窄屏下 SHALL 取消等高限制
- **AND** 判断路径 SHALL 随内容自然展开而不设置内部滚动区域
- **AND** 证据双栏 SHALL 具有 400px 最小高度，右侧 Monaco SHALL 填充可用高度
- **AND** 当前位置状态和命中位置 SHALL 在标题右侧单行展示

#### Scenario: 按需查看扫描事实

- **WHEN** Finding 详情初次展示
- **THEN** 扫描事实 SHALL 默认折叠并提供可访问的展开入口
- **AND** 用户展开后 SHALL 能查看规则、事实、位置状态和发现时间
- **AND** 扫描事实 SHALL 位于建议下一步之后并使用无边框的次级样式

#### Scenario: 查看原始扫描数据

- **WHEN** 用户主动展开原始扫描数据
- **THEN** 系统 SHALL 以只读、格式化的方式展示原始 `evidence`
- **AND** 原始数据入口 SHALL 默认折叠并位于主要内容之后
- **AND** 原始数据入口 SHALL 与扫描事实使用一致的标题、图标和展开收起反馈
- **AND** 原始 JSON 代码块 SHALL 设置最大高度并在超出时内部滚动
- **AND** 滚动 SHALL 发生在 CodeMirror 编辑器内部而不是折叠面板外层
- **AND** CodeMirror SHALL 填充一个具有确定高度的视口，内容不得反向撑高该视口

#### Scenario: 详情请求失败

- **WHEN** Finding 详情请求失败
- **THEN** 系统 SHALL 展示可理解的请求失败状态以及返回上一级或重试的恢复路径
- **AND** 系统 SHALL NOT 渲染不完整的详情骨架冒充成功结果

#### Scenario: 代码上下文请求失败

- **WHEN** Finding 详情已加载但补充代码上下文请求失败
- **THEN** 系统 SHALL 保留其余详情内容并在代码区域说明上下文不可用
- **AND** 系统 SHALL NOT 将局部失败升级为整个详情页失败
