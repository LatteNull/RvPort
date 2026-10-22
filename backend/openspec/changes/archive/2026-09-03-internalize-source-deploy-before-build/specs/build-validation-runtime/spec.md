## MODIFIED Requirements

### Requirement: 构建验证必须基于成功源码部署创建
后端 SHALL 提供构建验证创建 API，并 SHALL 创建构建任务和构建运行。`BUILD_VALIDATION` worker SHALL 在执行构建脚本前基于项目当前运行环境配置自动创建或复用同源码版本、同环境配置版本下的源码部署记录。构建验证不再要求前端预先调用源码部署创建接口。

#### Scenario: 创建双环境构建验证
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/builds` 并提交构建脚本、可选源码版本和超时时间
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 后端 SHALL 读取项目当前运行环境配置
- **AND** 后端 SHALL 校验源环境和目标环境都已配置且已启用
- **AND** 后端 SHALL 为 source/x86 和 target/RISC-V 环境分别创建独立的 `BUILD_VALIDATION` 任务和 `build_runs` 记录
- **AND** 每个 `BUILD_VALIDATION` worker SHALL 在执行构建脚本前查找同源码版本、同环境配置版本下的可复用源码部署记录
- **AND** 对缺少成功部署的环境，worker SHALL 在当前构建任务内执行源码部署
- **AND** 对已经存在成功部署的环境，worker SHALL 直接复用对应 `source_deploy_runs` 记录
- **AND** 两条构建运行 SHALL 保存同一个环境配置版本
- **AND** 响应 SHALL 返回构建运行 ID、任务 ID、环境 ID、源码版本 ID、环境配置版本和初始状态

#### Scenario: 缺少成功部署时自动准备
- **WHEN** 当前运行环境下缺少源环境或目标环境的成功源码部署记录
- **THEN** 后端 SHALL 仍然创建对应环境的构建任务和构建运行
- **AND** `BUILD_VALIDATION` worker SHALL 在当前构建任务内自动执行源码部署
- **AND** 后端 MUST NOT 返回 `SOURCE_DEPLOYMENT_NOT_READY` 要求前端先手动部署
- **AND** 对应环境构建脚本 SHALL 在源码部署成功后开始执行

#### Scenario: 拒绝跨版本部署
- **WHEN** 存在成功源码部署记录但其环境配置版本不是当前项目运行环境配置版本
- **THEN** 后端 SHALL 将该部署记录视为非当前可用输入
- **AND** `BUILD_VALIDATION` worker SHALL 为当前环境配置版本自动创建或复用新的源码部署记录

#### Scenario: 任一环境部署或构建失败不阻止另一环境
- **WHEN** 双环境构建任务已经创建
- **THEN** 任一环境部署或构建失败 MUST NOT 阻止另一环境任务执行或写回结果
- **AND** 两侧部署和构建结果 SHALL 独立保存退出码、状态和日志引用

#### Scenario: 拒绝客户端指定源码部署记录
- **WHEN** 用户创建构建验证并提交 `sourceDeploymentIds`
- **THEN** 后端 SHALL 返回 `BUILD_SOURCE_DEPLOYMENTS_DEPRECATED`
- **AND** 后端 MUST NOT 使用客户端提交的源码部署记录作为构建输入

### Requirement: 构建验证必须支持前置 source-only 构建
构建验证运行时 SHALL 在保持默认双环境构建行为不变的前提下，支持用于依赖分析前置的 source/x86 单环境构建范围。

#### Scenario: 默认双环境构建
- **WHEN** 用户创建构建验证且未提交 `buildScope`
- **THEN** 后端 SHALL 使用 `BOTH` 作为默认构建范围
- **AND** 后端 SHALL 为 source/x86 和 target/RISC-V 创建构建运行
- **AND** 每个构建任务执行时 SHALL 自动准备或复用自身环境的源码部署
- **AND** 该行为 SHALL 与现有正式构建验证节点兼容

#### Scenario: 创建 source-only 构建
- **WHEN** 用户创建构建验证并提交 `buildScope=SOURCE_ONLY`
- **THEN** 后端 SHALL 只为项目当前 source/x86 环境创建构建运行
- **AND** 该构建任务执行时 SHALL 自动执行或复用 source 环境源码部署
- **AND** 后端 MUST NOT 为 target/RISC-V 环境创建源码部署或构建运行

#### Scenario: source-only 构建作为依赖分析前置
- **WHEN** source-only 构建成功
- **THEN** 构建运行 SHALL 保存源码版本、source 环境、环境配置版本、构建日志引用、构建脚本摘要和产物事实摘要
- **AND** 这些事实 SHALL 能被依赖分析任务引用

#### Scenario: 拒绝不支持的构建范围
- **WHEN** 构建创建请求提交 MVP 不支持的 `buildScope`
- **THEN** 后端 SHALL 返回统一参数校验错误
- **AND** 后端 MUST NOT 创建构建运行、任务或队列消息

#### Scenario: 正式构建验证仍使用双环境
- **WHEN** 前端进入正式构建验证节点
- **THEN** 前端 SHALL 默认调用 `buildScope=BOTH` 或省略该参数
- **AND** 后端 SHALL 同时验证 source/x86 和 target/RISC-V 构建结果

## ADDED Requirements

### Requirement: 构建任务必须暴露内部部署阶段状态
构建验证任务 SHALL 将内部源码部署阶段写入同一构建任务的进度、日志和结果状态，使前端无需理解源码部署业务接口也能展示进度。

#### Scenario: 推送内部部署阶段
- **WHEN** 构建任务开始执行源码部署步骤
- **THEN** worker SHALL 写入任务进度和 merged/stdout/stderr 日志
- **AND** 项目级 SSE SHALL 推送同一 `BUILD_VALIDATION` 任务的阶段状态
- **AND** 失败摘要 MUST NOT 暴露明文凭据或服务器本机路径

#### Scenario: 回填源码部署记录
- **WHEN** 构建任务复用或完成源码部署
- **THEN** worker SHALL 将实际使用的 `source_deploy_runs.id` 写入 `build_runs.source_deploy_run_id`
- **AND** 构建详情响应 SHALL 返回该 `sourceDeploymentId`
