## Purpose

定义项目当前运行环境配置能力：在环境管理中集中维护源环境和目标环境，并作为 SBOM、源码部署、构建验证、自动化测试等远程运行节点的统一环境来源。

## Requirements
### Requirement: 项目必须维护当前运行双环境配置
后端 SHALL 为每个项目维护当前运行环境配置，包含源环境和目标环境，并 SHALL 使用该配置作为所有远程运行节点的环境事实来源。

#### Scenario: 查询项目运行环境配置
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/runtime-environments`
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 响应 SHALL 返回源环境摘要、目标环境摘要、版本号、更新时间和是否已满足双环境运行条件
- **AND** 若源环境或目标环境缺失，响应 SHALL 明确返回缺失项

#### Scenario: 局部设置源环境
- **WHEN** 已登录用户调用 `PATCH /api/projects/{projectId}/runtime-environments` 并只提交 `sourceEnvironmentId`
- **THEN** 后端 SHALL 校验源环境属于该项目且已启用
- **AND** 后端 SHALL 更新源环境并保留已有目标环境
- **AND** 后端 SHALL 递增运行环境配置版本

#### Scenario: 局部设置目标环境
- **WHEN** 已登录用户调用 `PATCH /api/projects/{projectId}/runtime-environments` 并只提交 `targetEnvironmentId`
- **THEN** 后端 SHALL 校验目标环境属于该项目且已启用
- **AND** 后端 SHALL 更新目标环境并保留已有源环境
- **AND** 后端 SHALL 递增运行环境配置版本

#### Scenario: 同时设置双环境
- **WHEN** 已登录用户调用运行环境配置更新接口并同时提交源环境和目标环境
- **THEN** 后端 SHALL 在同一事务中校验并保存两个环境
- **AND** 后端 SHALL 递增一次运行环境配置版本
- **AND** 响应 SHALL 表示项目已满足双环境运行条件

#### Scenario: 拒绝非法运行环境
- **WHEN** 请求提交不存在、跨项目、禁用或角色不匹配的环境
- **THEN** 后端 SHALL 返回统一错误
- **AND** 后端 MUST NOT 保存部分非法配置

### Requirement: 远程运行节点必须要求双环境完整
SBOM、源码部署、构建验证、自动化测试以及后续依赖远程环境的节点 SHALL 在创建任务前校验项目运行环境配置完整。

#### Scenario: 双环境缺失时拒绝运行
- **WHEN** 用户创建依赖远程环境的运行任务
- **AND** 项目运行环境配置缺少源环境或目标环境
- **THEN** 后端 SHALL 返回 `PROJECT_RUNTIME_ENVIRONMENTS_REQUIRED` 或等效业务错误
- **AND** 后端 MUST NOT 创建任务、运行记录或队列消息

#### Scenario: 使用当前环境配置运行
- **WHEN** 项目运行环境配置包含源环境和目标环境
- **THEN** 后端 SHALL 使用该配置创建远程运行任务
- **AND** 运行记录 SHALL 保存当时的运行环境配置版本
- **AND** 任务输入快照 SHALL 保存环境 ID 和环境配置版本

#### Scenario: 环境配置变更后结果过期
- **WHEN** 用户更新项目运行环境配置
- **THEN** 后端 SHALL 递增配置版本
- **AND** 旧版本下创建的 SBOM、源码部署、构建验证和自动化测试结果 SHALL 保留历史记录
- **AND** 后端 SHALL 在查询响应中标识这些结果不属于当前运行环境配置

#### Scenario: 源码更新不影响环境检测
- **WHEN** 用户上传新源码或执行 Git 同步并激活新源码版本
- **THEN** 后端 SHALL 不改变项目运行环境配置版本
- **AND** 后端 SHALL 不要求重新执行环境连接测试或环境采集
- **AND** 源码相关分析、部署、构建、测试和报告 SHALL 基于新源码版本重新运行

### Requirement: 项目运行环境必须支持依赖分析环境来源
项目运行环境配置 SHALL 继续维护 source 和 target 双环境，并 SHALL 为依赖分析提供 source 构建环境与 target 能力查询环境。

#### Scenario: 依赖分析读取双环境配置
- **WHEN** 用户创建依赖分析任务
- **THEN** 后端 SHALL 读取项目当前运行环境配置
- **AND** source 环境 SHALL 用于定位成功 x86 构建事实
- **AND** target 环境 SHALL 用于执行 RISC-V 能力查询

#### Scenario: 缺少目标环境时拒绝依赖分析
- **WHEN** 项目运行环境配置缺少 source 或 target 环境
- **THEN** 后端 SHALL 返回运行环境未配置完整错误
- **AND** 后端 MUST NOT 创建依赖分析运行、任务或队列消息

#### Scenario: 环境配置变更后依赖分析过期
- **WHEN** 用户更新项目运行环境配置
- **THEN** 旧环境配置版本下的依赖分析结果 SHALL 保留历史记录
- **AND** 查询响应 SHALL 标识这些结果不属于当前运行环境配置版本

### Requirement: 运行环境更新必须使依赖环境的当前节点结果失效
项目运行环境配置变更后，依赖远端环境的节点结果 SHALL 被视为非当前结果，但历史记录 SHALL 保留可查。

#### Scenario: 更新运行环境版本
- **WHEN** 用户更新项目当前 source/x86 或 target/RISC-V 运行环境
- **THEN** 后端 SHALL 递增项目运行环境配置版本
- **AND** 后续构建验证、源码部署、依赖分析和自动化测试 SHALL 使用新的运行环境配置版本

#### Scenario: 旧环境版本记录不再作为当前结果
- **WHEN** 节点记录保存的 `environmentConfigVersion` 小于当前项目运行环境配置版本
- **THEN** 当前节点列表默认 MUST NOT 返回该记录
- **AND** 该记录详情或历史列表 SHALL 标明 `currentRuntimeEnvironment=false`
- **AND** 该记录 SHALL 包含 `RUNTIME_ENVIRONMENT_CHANGED` 或等效陈旧原因

#### Scenario: 历史记录仍可查询
- **WHEN** 用户显式请求历史运行环境版本或设置 `includeStale=true`
- **THEN** 后端 SHALL 允许返回旧环境版本下的节点记录
- **AND** 后端 MUST 继续执行项目访问权限校验

### Requirement: 单环境配置版本必须参与项目运行 Context 生命周期
项目运行环境管理 SHALL 将当前 source 和 target 环境的有效配置版本纳入项目 Context 生命周期。

#### Scenario: 当前 source 环境有效配置变化
- **WHEN** 当前项目选中的 source 环境 `configVersion` 递增
- **THEN** 后端 SHALL 递增该项目的 `runtimeEnvironmentVersion`
- **AND** 依赖运行环境的当前构建、依赖分析、测试、报告、优化和归档结果 SHALL 变为旧 Context 历史事实

#### Scenario: 当前 target 环境有效配置变化
- **WHEN** 当前项目选中的 target 环境 `configVersion` 递增
- **THEN** 后端 SHALL 递增该项目的 `runtimeEnvironmentVersion`
- **AND** 后端 SHALL 要求当前双环境重新完成所需连接测试后才恢复就绪

#### Scenario: 非当前环境变化
- **WHEN** 某环境没有被项目选为当前 source 或 target
- **AND** 该环境有效配置发生变化
- **THEN** 后端 SHALL 递增该环境自身 `configVersion`
- **AND** 后端 MUST NOT 因此递增无引用项目的 `runtimeEnvironmentVersion`

#### Scenario: 当前环境变化发送 Context 事件
- **WHEN** 当前环境有效配置变化导致项目 `runtimeEnvironmentVersion` 递增
- **THEN** 后端 SHALL 为受影响项目追加 `project.context.changed` 事件
- **AND** 事件 SHALL 包含新的运行环境版本和受影响资源标识

#### Scenario: 同一请求同时更新双环境
- **WHEN** 一个操作同时改变当前 source 和 target 环境的有效配置
- **THEN** 每个环境 SHALL 分别递增自身 `configVersion`
- **AND** 同一项目的 `runtimeEnvironmentVersion` SHALL 在该业务操作中只递增一次
