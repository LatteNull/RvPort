## ADDED Requirements

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
