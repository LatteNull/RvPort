## MODIFIED Requirements

### Requirement: 源码部署任务必须绑定项目源码版本和环境
后端 SHALL 将源码部署作为构建验证任务内部准备能力，将指定项目的指定源码版本部署到项目当前运行环境配置中的源环境和目标环境。正式前端业务流程 MUST NOT 依赖单独的源码部署创建接口来启动构建。

#### Scenario: 构建任务执行时准备源码部署
- **WHEN** `BUILD_VALIDATION` worker 开始处理构建任务
- **AND** 当前源码版本在所需运行环境中缺少同环境配置版本的成功源码部署记录
- **THEN** 后端 SHALL 校验任务中的源码版本属于任务项目
- **AND** 后端 SHALL 读取任务绑定的环境和环境配置版本
- **AND** 后端 SHALL 校验所需源环境或目标环境已配置且已启用
- **AND** 后端 SHALL 在当前构建任务内创建 `source_deploy_runs` 记录并执行源码传输
- **AND** 后端 SHALL 将成功部署记录 ID 回填到 `build_runs.source_deploy_run_id`
- **AND** 后端 SHALL 继续在部署目录执行构建脚本

#### Scenario: 创建双环境构建时准备源码部署
- **WHEN** 项目当前运行环境配置包含 x86 原始环境和 RISC-V 目标环境
- **AND** 用户创建默认双环境构建验证
- **THEN** 后端 SHALL 分别创建两个 `BUILD_VALIDATION` 任务和构建记录
- **AND** 每个构建任务执行时 SHALL 为自身环境创建或复用源码部署记录
- **AND** 两个部署记录 SHALL 绑定同一个 `sourceRevisionId`
- **AND** 两个部署记录 SHALL 保存同一个环境配置版本
- **AND** 两个部署记录 SHALL 拥有各自基于环境工作目录生成的 `remote_path`

#### Scenario: 创建 source-only 构建时准备源码部署
- **WHEN** 用户创建 `buildScope=SOURCE_ONLY` 的构建验证
- **THEN** 后端 SHALL 只创建项目当前 source/x86 环境的构建任务和构建记录
- **AND** 该构建任务执行时 SHALL 为 source/x86 环境创建或复用源码部署记录
- **AND** 后端 MUST NOT 为 target/RISC-V 环境创建源码部署记录

#### Scenario: 拒绝跨项目源码部署
- **WHEN** 构建创建或执行过程需要准备源码部署
- **AND** `sourceRevisionId` 不属于 URL 中的 `projectId` 或项目运行环境配置引用了非法环境
- **THEN** 后端 SHALL 拒绝请求
- **AND** 后端 MUST NOT 创建任务、源码部署记录或队列消息

#### Scenario: 拒绝不可用源码工作副本
- **WHEN** 构建执行过程需要准备源码部署
- **AND** 源码版本缺少可读的后端本机工作副本
- **THEN** 后端 SHALL 返回 `SOURCE_REVISION_WORKING_COPY_NOT_FOUND`
- **AND** 错误响应 MUST NOT 暴露服务器本机源码路径
- **AND** 后端 MUST NOT 投递队列消息

### Requirement: 构建验证必须使用成功的源码部署作为远端输入
源码部署运行时 SHALL 为构建验证提供稳定的远端源码目录事实。构建验证任务 SHALL 在执行构建脚本前自动创建或复用源码部署步骤。

#### Scenario: 构建验证引用成功部署
- **WHEN** 后续构建验证任务需要在远端环境执行
- **THEN** 构建验证 SHALL 使用状态为 `SUCCEEDED` 的源码部署记录作为远端源码输入
- **AND** 构建验证运行目录 SHALL 基于 `source_deploy_runs.remote_path`
- **AND** 构建验证 MUST NOT 使用失败、取消、超时或仍在运行的部署记录作为输入

#### Scenario: 构建任务内隐式执行源码部署
- **WHEN** `BUILD_VALIDATION` worker 准备执行构建脚本
- **AND** 当前源码版本在所需环境下缺少成功源码部署记录
- **THEN** 后端 SHALL 在当前构建任务内执行源码部署
- **AND** 后端 SHALL 在部署成功后继续执行对应环境的构建脚本
- **AND** 前端 MUST NOT 被要求调用正式源码部署创建 API 才能开始构建

#### Scenario: 部署失败阻止对应环境构建
- **WHEN** 构建任务内部源码部署失败、取消或超时
- **THEN** 后端 MUST NOT 执行对应环境的构建脚本
- **AND** 后端 SHALL 将对应构建任务和构建运行标记为失败、取消或超时
- **AND** 错误响应或任务摘要 MUST NOT 暴露明文凭据或服务器本机路径

## REMOVED Requirements

### Requirement: 源码部署必须支持复用和强制重新部署
**Reason**: `force` 作为正式前端源码部署动作会把内部部署步骤重新暴露给业务流程。构建验证应按当前源码版本和当前运行环境配置版本自动复用成功部署；需要强制重新部署时应由构建创建请求或测试辅助接口表达。

**Migration**: 构建验证创建 API 负责按需复用或重新准备源码部署。测试和排障场景迁移到 `test-support` API。

### Requirement: 源码部署记录必须可作为多环境构建输入
**Reason**: 多环境构建仍需要保存 `source_deploy_runs` 关联，但正式构建 API 不应要求客户端传入源码部署记录 ID。

**Migration**: `build_runs.source_deploy_run_id` 保留为后端内部审计字段，由构建创建编排自动填充。
