## MODIFIED Requirements

### Requirement: 构建验证必须基于成功源码部署创建
后端 SHALL 提供构建验证创建 API，并 SHALL 基于项目当前运行环境配置找到同源码版本、同环境配置版本下的成功源码部署记录作为远端源码输入。

#### Scenario: 创建双环境构建验证
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/builds` 并提交构建脚本、可选源码版本和超时时间
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 后端 SHALL 读取项目当前运行环境配置
- **AND** 后端 SHALL 校验源环境和目标环境都已配置且已启用
- **AND** 后端 SHALL 查找同源码版本、同环境配置版本下两条成功源码部署记录
- **AND** 后端 SHALL 为每条源码部署记录创建独立的 `BUILD_VALIDATION` 任务和 `build_runs` 记录
- **AND** 两条构建运行 SHALL 保存同一个环境配置版本
- **AND** 响应 SHALL 返回构建运行 ID、任务 ID、环境 ID、源码版本 ID、源码部署 ID、环境配置版本和初始状态

#### Scenario: 缺少成功部署时拒绝构建
- **WHEN** 当前运行环境下缺少源环境或目标环境的成功源码部署记录
- **THEN** 后端 SHALL 返回 `SOURCE_DEPLOYMENT_NOT_READY` 或等效明确业务错误
- **AND** 后端 MUST NOT 创建构建任务、构建运行或队列消息

#### Scenario: 拒绝跨版本部署
- **WHEN** 存在成功源码部署记录但其环境配置版本不是当前项目运行环境配置版本
- **THEN** 后端 SHALL 将该部署记录视为非当前可用输入
- **AND** 后端 MUST NOT 使用该部署记录创建构建运行

#### Scenario: 任一环境构建失败不阻止另一环境
- **WHEN** 双环境构建任务已经创建
- **THEN** 任一环境构建失败 MUST NOT 阻止另一环境任务执行或写回结果
- **AND** 两侧构建结果 SHALL 独立保存退出码、状态和日志引用
