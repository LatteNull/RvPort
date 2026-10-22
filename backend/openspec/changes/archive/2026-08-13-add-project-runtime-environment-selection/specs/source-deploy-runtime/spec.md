## MODIFIED Requirements

### Requirement: 源码部署任务必须绑定项目源码版本和环境
后端 SHALL 提供源码部署创建 API，将指定项目的指定源码版本部署到项目当前运行环境配置中的源环境和目标环境，并 SHALL 使用异步任务运行时执行。

#### Scenario: 创建源码部署任务
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/source-deployments` 并提交 `sourceRevisionId`
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 后端 SHALL 校验源码版本属于 URL 中的 `projectId`
- **AND** 后端 SHALL 读取项目当前运行环境配置
- **AND** 后端 SHALL 校验源环境和目标环境都已配置且已启用
- **AND** 后端 SHALL 为每个需要新部署的环境创建任务类型为 `SOURCE_DEPLOY` 的 `tasks` 记录
- **AND** 后端 SHALL 为每个环境创建或复用对应 `source_deploy_runs` 记录
- **AND** 后端 SHALL 投递新创建的任务 ID 到 RabbitMQ
- **AND** 响应 SHALL 返回源码部署项列表，每项包含任务 ID、任务类型、初始状态、环境 ID、源码部署 ID 和环境配置版本

#### Scenario: 创建双环境源码部署任务
- **WHEN** 项目当前运行环境配置包含 x86 原始环境和 RISC-V 目标环境
- **THEN** 后端 SHALL 分别为两个环境创建或复用源码部署记录
- **AND** 两个部署记录 SHALL 绑定同一个 `sourceRevisionId`
- **AND** 两个部署记录 SHALL 保存同一个环境配置版本
- **AND** 两个部署记录 SHALL 拥有各自基于环境工作目录生成的 `remote_path`

#### Scenario: 拒绝跨项目源码部署
- **WHEN** 用户调用源码部署创建 API
- **AND** `sourceRevisionId` 不属于 URL 中的 `projectId` 或项目运行环境配置引用了非法环境
- **THEN** 后端 SHALL 拒绝请求
- **AND** 后端 MUST NOT 创建任务、源码部署记录或队列消息

#### Scenario: 拒绝不可用源码工作副本
- **WHEN** 用户创建源码部署任务
- **AND** 源码版本缺少可读的后端本机工作副本
- **THEN** 后端 SHALL 返回 `SOURCE_REVISION_WORKING_COPY_NOT_FOUND`
- **AND** 错误响应 MUST NOT 暴露服务器本机源码路径
- **AND** 后端 MUST NOT 投递队列消息
