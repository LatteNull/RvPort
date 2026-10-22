## MODIFIED Requirements

### Requirement: 构建 API 必须支持任务级环境变量
构建验证 API SHALL 允许前端为单次构建任务传入环境变量，并 SHALL 在远程构建命令或脚本执行时注入这些变量。

#### Scenario: 创建带环境变量的构建任务
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/builds` 且请求包含 `environmentVariables`
- **THEN** 后端 SHALL 校验用户有权访问该项目
- **AND** 后端 SHALL 校验源码版本和执行环境属于该项目
- **AND** 后端 SHALL 校验环境变量名格式、数量、单值长度和总大小
- **AND** 后端 SHALL 将环境变量作为任务级运行参数传递给 worker
- **AND** 环境变量 MUST NOT 写入正式环境配置、凭据表或系统配置

#### Scenario: 构建环境变量脱敏
- **WHEN** 后端返回构建详情、构建列表、任务事件、SSE data、审计摘要或错误信息
- **THEN** 后端 MUST NOT 返回环境变量明文值
- **AND** 名称包含 `TOKEN`、`PASSWORD`、`SECRET`、`KEY` 或 `PASS` 的变量 MUST 被视为敏感变量
- **AND** 后端 SHOULD 只返回环境变量名称、是否已配置和遮蔽摘要

#### Scenario: 构建环境变量非法
- **WHEN** 构建创建请求包含非法变量名、空变量名、超过长度限制的值或超过数量限制的变量集合
- **THEN** API SHALL 返回统一参数校验错误
- **AND** 后端 MUST NOT 创建构建运行记录
- **AND** 后端 MUST NOT 创建或投递构建任务

#### Scenario: 构建详情不暴露任务输入快照
- **WHEN** 已登录用户查询构建详情或项目构建列表
- **THEN** 响应 SHALL 返回构建运行摘要、状态、退出码、日志引用和脱敏环境变量摘要
- **AND** 响应 MUST NOT 返回 `tasks.input_snapshot` 原文
- **AND** 响应 MUST NOT 返回服务器真实路径、明文凭据或环境变量明文值
