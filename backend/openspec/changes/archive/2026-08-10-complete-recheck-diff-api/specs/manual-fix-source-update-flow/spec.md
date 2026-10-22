## MODIFIED Requirements

### Requirement: latest compare API
系统 SHALL 提供项目级 latest compare API，由后端基于项目源码版本关系选择当前版本和上一可比较版本，并返回基于已确认迁移输入生成的复检差异状态。

#### Scenario: 获取 latest compare
- **WHEN** 用户调用 `GET /api/projects/{projectId}/source/compare/latest`
- **THEN** 系统 MUST 校验当前用户对项目有访问权限
- **AND** 系统 MUST 使用项目 active 源码版本作为 `currentRevision`
- **AND** 系统 MUST 使用同项目中早于当前版本的最近可比较源码版本作为 `previousRevision`
- **AND** 系统 MUST 返回当前版本相对上一版本的复检差异状态

#### Scenario: 只有一个源码版本
- **WHEN** 项目只有一个可用源码版本
- **THEN** latest compare 响应 MUST 返回 `previousRevision=null`
- **AND** 响应 MUST 返回 `emptyReason=NO_PREVIOUS_REVISION`
- **AND** 响应 MUST 返回空差异摘要和空差异列表入口

#### Scenario: 比较结果已生成
- **WHEN** 当前版本和上一版存在已完成的复检记录
- **THEN** latest compare 响应 MUST 返回复检状态、差异摘要和分页差异项入口信息
- **AND** 差异摘要 MUST 基于 `diff_items` 统计 `RESOLVED`、`UNCHANGED`、`NEW`、`CHANGED`

#### Scenario: 比较结果尚未生成
- **WHEN** 当前版本和上一版存在但没有可用复检记录
- **THEN** latest compare 响应 MUST 返回 `status=NOT_STARTED`
- **AND** 响应 MUST 包含 current/previous 源码版本摘要
- **AND** 响应 MUST NOT 自动创建复检任务

#### Scenario: 比较任务运行中
- **WHEN** 当前版本和上一版的复检任务正在运行
- **THEN** latest compare 响应 MUST 返回 `status=RUNNING`
- **AND** 响应 MUST 返回关联任务 ID，供前端结合 SSE 展示进度

#### Scenario: 越权访问 latest compare
- **WHEN** 用户访问无权限项目的 latest compare API
- **THEN** 系统 MUST 返回安全错误
- **AND** 响应 MUST NOT 暴露项目或源码版本是否存在

## ADDED Requirements

### Requirement: 复检任务必须基于已确认迁移输入创建
系统 SHALL 提供复检任务创建 API，对比两个源码版本下人工确认后的迁移输入 reference，并异步生成复检差异记录。

#### Scenario: 创建显式版本复检任务
- **WHEN** 用户调用 `POST /api/projects/{projectId}/rechecks` 并传入 `baseSourceRevisionId` 与 `targetSourceRevisionId`
- **THEN** 系统 MUST 校验当前用户对项目有访问权限
- **AND** 系统 MUST 校验两个源码版本属于同一项目
- **AND** 系统 MUST 创建或复用对应的复检任务
- **AND** 响应 MUST 返回 `TaskResponse`

#### Scenario: 创建 latest 复检任务
- **WHEN** 用户调用 `POST /api/projects/{projectId}/rechecks/latest`
- **THEN** 系统 MUST 使用项目 active 源码版本作为 target
- **AND** 系统 MUST 选择同项目中早于 target 的最近可比较源码版本作为 base
- **AND** 系统 MUST 创建或复用对应的复检任务

#### Scenario: 没有可比较源码版本
- **WHEN** 用户创建 latest 复检任务但项目没有 previous source revision
- **THEN** 系统 MUST 返回 `SOURCE_REVISION_PREVIOUS_NOT_FOUND`
- **AND** 系统 MUST NOT 创建任务

#### Scenario: 复检只读取已确认迁移输入
- **WHEN** 复检任务开始执行
- **THEN** 系统 MUST 只读取 base/target 源码版本下 `CONFIRMED` 状态的迁移输入 reference
- **AND** 系统 MUST NOT 使用 `CANDIDATE` 或 `EXCLUDED` 迁移输入生成差异
- **AND** 系统 MUST NOT 使用未进入迁移输入的原始扫描结果生成差异

#### Scenario: 重复创建复检任务
- **WHEN** 同一项目、base 源码版本和 target 源码版本已经存在 `PENDING`、`QUEUED`、`RUNNING` 或 `SUCCEEDED` 复检记录
- **THEN** 系统 MUST 返回已有任务或已有复检记录
- **AND** 系统 MUST NOT 重复生成并发复检任务

### Requirement: 复检差异必须使用稳定 issue identity 和匹配置信度
系统 SHALL 为迁移输入生成稳定 issue identity，并在复检时结合 exact fingerprint 与规则化模糊匹配判断 old/new 是否为同一 issue。

#### Scenario: 代码类 finding 行号变化
- **WHEN** base 和 target 中两个代码类 finding 的行号不同
- **AND** 二者具有相同 `sourceType`、`ruleId`、相对路径、符号名和 normalized anchor
- **THEN** 系统 MUST 将二者匹配为同一 issue
- **AND** 系统 MUST NOT 仅因行号变化生成 `RESOLVED` 与 `NEW`

#### Scenario: exact fingerprint 匹配
- **WHEN** base 和 target 中两个迁移输入具有相同 stable fingerprint
- **THEN** 系统 MUST 使用 `matchConfidence=HIGH`
- **AND** 系统 MUST 使用 `matchReason=EXACT_FINGERPRINT`

#### Scenario: 模糊匹配
- **WHEN** exact fingerprint 未匹配成功
- **AND** base 和 target 中两个迁移输入满足同来源类型下的规则化模糊匹配条件
- **THEN** 系统 MUST 将二者匹配为同一 issue
- **AND** 系统 MUST 记录 `matchConfidence` 和 `matchReason`

#### Scenario: 无匹配项
- **WHEN** base 迁移输入无法在 target 中找到匹配项
- **THEN** 系统 MUST 生成 `RESOLVED` 差异项
- **WHEN** target 迁移输入无法在 base 中找到匹配项
- **THEN** 系统 MUST 生成 `NEW` 差异项

### Requirement: 复检差异项必须表达修复、新增、仍存在和变化
系统 SHALL 为每条复检差异生成明确的 `diffStatus`，并保存 old/new 两侧快照以供前端审计。

#### Scenario: 问题已修复
- **WHEN** base 中存在已确认迁移输入且 target 中不存在匹配项
- **THEN** 系统 MUST 创建 `diffStatus=RESOLVED` 的差异项
- **AND** 差异项 MUST 包含 `oldSourceId`
- **AND** 差异项 MUST NOT 包含 `newSourceId`

#### Scenario: 问题新增
- **WHEN** target 中存在已确认迁移输入且 base 中不存在匹配项
- **THEN** 系统 MUST 创建 `diffStatus=NEW` 的差异项
- **AND** 差异项 MUST 包含 `newSourceId`
- **AND** 差异项 MUST NOT 包含 `oldSourceId`

#### Scenario: 问题仍存在
- **WHEN** base 和 target 中两个迁移输入匹配为同一 issue
- **AND** 二者核心展示字段和风险字段未发生变化
- **THEN** 系统 MUST 创建 `diffStatus=UNCHANGED` 的差异项

#### Scenario: 问题发生变化
- **WHEN** base 和 target 中两个迁移输入匹配为同一 issue
- **AND** 二者风险、位置、标题、建议或来源快照中的关键字段发生变化
- **THEN** 系统 MUST 创建 `diffStatus=CHANGED` 的差异项

### Requirement: 复检差异查询必须支持列表和详情
系统 SHALL 提供复检差异项分页列表和单条详情 API，列表用于表格展示，详情用于查看 old/new 两侧来源信息。

#### Scenario: 分页查询差异项列表
- **WHEN** 用户调用 `GET /api/rechecks/{recheckRunId}/diff-items`
- **THEN** 系统 MUST 校验当前用户对该复检所属项目有访问权限
- **AND** 响应 MUST 支持按 `diffStatus`、`sourceType`、`severity`、`matchConfidence` 过滤
- **AND** 响应 MUST 支持分页、排序
- **AND** 每条列表项 MUST 返回 `title`、`locationLabel`、`recommendation`、`confirmationStatus`、`matchConfidence` 和 `matchReason`

#### Scenario: 查询单条差异详情
- **WHEN** 用户调用 `GET /api/rechecks/{recheckRunId}/diff-items/{diffItemId}`
- **THEN** 系统 MUST 校验当前用户对该复检所属项目有访问权限
- **AND** 系统 MUST 校验差异项属于该复检
- **AND** 响应 MUST 返回 `oldItem` 与 `newItem` 快照
- **AND** `RESOLVED` 差异 MUST 只包含 `oldItem`
- **AND** `NEW` 差异 MUST 只包含 `newItem`
- **AND** `UNCHANGED` 和 `CHANGED` 差异 MUST 同时包含 `oldItem` 与 `newItem`

#### Scenario: 差异详情越权访问
- **WHEN** 用户访问无权限项目的复检差异详情
- **THEN** 系统 MUST 返回安全错误
- **AND** 响应 MUST NOT 暴露复检或差异项是否存在
