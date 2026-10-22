# dependency-auto-fix-runtime Specification

## Purpose
TBD - created by archiving change add-dependency-auto-fix-runtime. Update Purpose after archive.
## Requirements
### Requirement: 依赖自动修复必须提供候选项查询
依赖自动修复运行时 SHALL 基于某次成功依赖分析结果提供可安装候选项查询，并 SHALL 返回默认选择状态、安装计划和不可修复原因。

#### Scenario: 查询自动修复候选项
- **WHEN** 已登录用户调用 `GET /api/dependency-analyses/{analysisId}/auto-fix-candidates`
- **THEN** 后端 SHALL 校验当前用户有权访问依赖分析所属项目
- **AND** 后端 SHALL 只从该依赖分析运行的结果项中派生候选项
- **AND** 响应 SHALL 支持分页、排序和按 `riskLevel`、`targetMatchStatus`、`dependencyType`、`keyword`、`defaultSelected`、`selectable` 过滤
- **AND** 每条候选项 SHALL 返回 `resultItemId`、`riskLevel`、`targetMatchStatus`、`sourceProviderPackage`、`sourceProviderVersion`、`targetProviderPackage`、`targetProviderVersion`、`installPackageName`、`installVersionConstraint`、`defaultSelected`、`selectable` 和 `reason`

#### Scenario: 中风险候选项默认选中
- **WHEN** 依赖分析结果 `riskLevel=MEDIUM`
- **AND** 目标环境或目标软件源已经确认存在 `targetProviderPackage`
- **THEN** 自动修复候选项 SHALL 设置 `defaultSelected=true`
- **AND** `installPackageName` SHALL 使用目标侧确认的包名
- **AND** `installVersionConstraint` SHALL 优先使用目标侧确认的可安装版本

#### Scenario: 高风险候选项只展示不默认选中
- **WHEN** 依赖分析结果 `riskLevel=HIGH`
- **AND** 该结果存在 `sourceProviderPackage`
- **THEN** 自动修复候选项 SHALL 设置 `defaultSelected=false`
- **AND** `installPackageName` SHALL 使用源侧 owner package 名称或目标侧已确认的同名包
- **AND** `installVersionConstraint` SHALL 表达源侧主版本约束或等效匹配策略

#### Scenario: 不可自动修复条目
- **WHEN** 依赖分析结果缺少可确认安装包名
- **OR** `riskLevel` 为 `CRITICAL`、`LOW`、`INFO` 或 `COMMENT`
- **THEN** 默认候选查询 MUST NOT 将该结果作为可选自动修复项返回
- **AND** 如果通过调试或显式过滤查看不可修复项，响应 SHALL 返回 `selectable=false` 和明确 `reason`

### Requirement: 依赖自动修复必须创建异步修复任务
依赖自动修复运行时 SHALL 根据用户提交的依赖分析结果项创建异步修复任务，并 SHALL 逐条固化安装计划快照。

#### Scenario: 创建依赖自动修复任务
- **WHEN** 已登录用户调用 `POST /api/dependency-analyses/{analysisId}/auto-fixes`
- **AND** 请求体包含一个或多个 `resultItemIds`
- **THEN** 后端 SHALL 校验当前用户有权访问依赖分析所属项目
- **AND** 后端 SHALL 校验每个 `resultItemId` 属于该依赖分析运行
- **AND** 后端 SHALL 校验依赖分析运行属于当前 active source revision 和当前 project runtime environment config version
- **AND** 后端 SHALL 创建 `DEPENDENCY_AUTO_FIX` 任务、自动修复运行记录和自动修复条目记录
- **AND** 任务输入 MUST NOT 包含明文凭据、完整 SSH 参数、完整远端命令或服务器真实路径

#### Scenario: 创建修复任务时拒绝过期分析
- **WHEN** 用户基于旧源码版本或旧环境配置版本的依赖分析运行创建自动修复任务
- **THEN** 后端 SHALL 返回明确业务错误
- **AND** 后端 MUST NOT 创建修复运行、任务或队列消息

#### Scenario: 创建修复任务时拒绝非法条目
- **WHEN** 请求中的 result item 不属于指定依赖分析运行
- **OR** 请求中的 result item 不满足自动修复候选规则
- **THEN** 后端 SHALL 返回明确业务错误
- **AND** 后端 MUST NOT 对非法条目创建安装计划

### Requirement: 依赖自动修复必须受控安装目标环境软件包
依赖自动修复 worker SHALL 在 target/RISC-V 环境中使用受控包管理器命令安装用户选择的软件包，并 SHALL 逐条记录安装结果。

#### Scenario: 执行中风险包安装
- **WHEN** `DEPENDENCY_AUTO_FIX` worker 处理中风险候选项
- **THEN** worker SHALL 使用目标侧确认的 package name 和 version constraint 生成安装计划
- **AND** worker SHALL 在目标环境执行安装前查询包是否存在
- **AND** 查询和安装输出 SHALL 写入任务日志
- **AND** 安装成功后对应修复条目 SHALL 标记为 `SUCCEEDED`

#### Scenario: 执行高风险包安装
- **WHEN** `DEPENDENCY_AUTO_FIX` worker 处理高风险候选项
- **THEN** worker SHALL 使用 source provider package 和 source provider major version 尝试匹配目标源
- **AND** 未找到满足主版本约束的目标包时，该条目 SHALL 标记为 `FAILED` 或 `SKIPPED_UNAVAILABLE`
- **AND** worker MUST NOT 因单个高风险条目不可安装而中断其他条目安装

#### Scenario: 已安装或已满足的包
- **WHEN** worker 执行安装前发现目标环境已经安装满足计划的包
- **THEN** 对应条目 SHALL 标记为 `SKIPPED_ALREADY_SATISFIED`
- **AND** 该条目 SHALL 计入已满足统计

#### Scenario: 不支持的包管理器
- **WHEN** target 环境的 package manager 不在后端支持列表中
- **THEN** 修复任务 SHALL 失败并返回明确业务错误
- **AND** 后端 SHALL 保留修复运行记录、任务日志和失败摘要
- **AND** 后端 MUST NOT 尝试执行未受控的安装命令

#### Scenario: 安装命令安全校验
- **WHEN** 安装计划包含包名或版本约束
- **THEN** worker SHALL 对包名和版本约束执行白名单校验
- **AND** 包名或版本约束包含空白、换行、shell 元字符或命令替换时，worker MUST 拒绝执行
- **AND** 拒绝执行的条目 SHALL 标记为 `FAILED` 并记录脱敏原因

### Requirement: 依赖自动修复完成后必须自动重新分析
依赖自动修复运行时 SHALL 在目标环境安装完成后自动触发新的依赖分析，用于验证修复效果。

#### Scenario: 修复成功后创建新的依赖分析
- **WHEN** 自动修复任务至少有一个条目 `SUCCEEDED` 或 `SKIPPED_ALREADY_SATISFIED`
- **THEN** 后端 SHALL 创建新的 `DEPENDENCY_ANALYSIS` 任务
- **AND** 新依赖分析 SHALL 使用当前 active source revision、当前 target environment 和当前 environment config version
- **AND** 自动修复运行记录 SHALL 保存 `rerunDependencyAnalysisRunId` 和 `rerunDependencyAnalysisTaskId`

#### Scenario: 所有条目失败时不重跑分析
- **WHEN** 自动修复任务所有条目均失败或不可安装
- **THEN** 后端 SHALL 将自动修复运行标记为失败或部分失败终态
- **AND** 后端 MUST NOT 自动创建新的依赖分析任务
- **AND** 响应或运行详情 SHALL 返回失败统计和主要失败原因

#### Scenario: 重跑依赖分析创建失败
- **WHEN** 软件包安装成功但创建重跑依赖分析任务失败
- **THEN** 自动修复运行 SHALL 保留安装成功状态和重跑失败摘要
- **AND** 后端 MUST NOT 回滚已经在目标环境安装的软件包

### Requirement: 依赖自动修复必须可查询运行和条目
依赖自动修复运行时 SHALL 提供修复运行详情、条目分页列表和项目级历史查询。

#### Scenario: 查询修复运行详情
- **WHEN** 用户调用 `GET /api/dependency-auto-fixes/{autoFixRunId}`
- **THEN** 后端 SHALL 校验项目访问权限
- **AND** 响应 SHALL 返回修复运行状态、统计、关联依赖分析、目标环境、源码版本、任务 ID、重跑依赖分析 ID 和 summary

#### Scenario: 查询修复条目列表
- **WHEN** 用户调用 `GET /api/dependency-auto-fixes/{autoFixRunId}/items`
- **THEN** 后端 SHALL 返回分页列表
- **AND** 列表 SHALL 支持按 `status`、`riskLevel`、`targetMatchStatus`、`installPackageName` 和关键字过滤
- **AND** 列表 SHALL 支持稳定排序白名单

#### Scenario: 查询项目修复历史
- **WHEN** 用户调用 `GET /api/projects/{projectId}/dependency-auto-fixes`
- **THEN** 后端 SHALL 校验项目访问权限
- **AND** 响应 SHALL 默认返回当前 active source revision 和当前环境配置版本下的修复运行
- **AND** 用户显式请求历史上下文时 SHALL 可以查看历史修复运行
