## MODIFIED Requirements

### Requirement: 任务日志 API 不暴露服务器路径
任务日志 API SHALL 通过任务日志资源提供元数据分页、内容分段读取和受控下载能力，并 SHALL 隐藏服务器真实文件路径。

#### Scenario: 查询日志元数据
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/logs`
- **THEN** API SHALL 返回日志 ID、日志类型、大小、摘要和创建时间
- **AND** 响应 MUST NOT 返回 `file_path` 或服务器真实路径

#### Scenario: 读取日志内容
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/log-content`
- **THEN** API SHALL 返回完成态日志内容响应
- **AND** 响应 SHALL 支持 `merged`、`stdout`、`stderr` 三类日志
- **AND** 不传参数时每类默认返回最后 100 行
- **AND** 响应 MUST NOT 返回服务器真实日志文件路径

#### Scenario: 读取单类或多类不同 offset
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/log-content?types=merged,stdout&mergedOffset=0&stdoutOffset=100&mergedLines=100&stdoutLines=50`
- **THEN** API SHALL 只返回请求的日志类型
- **AND** 每个日志类型 SHALL 使用自己的 offset 和 lines
- **AND** 未设置单类 lines 时 SHALL 使用全局 `lines` 或默认值

#### Scenario: 下载日志文件
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/logs/{logId}/download`
- **THEN** API SHALL 校验日志属于该任务
- **AND** API SHALL 通过受控下载返回日志内容
- **AND** API MUST NOT 接受客户端传入服务器文件路径作为下载参数

### Requirement: 构建验证 API 必须使用源码部署引用
后端 API SHALL 提供构建验证创建、列表、详情和取消能力，并 SHALL 使用当前运行环境下的源码部署记录作为构建输入。

#### Scenario: 创建构建验证请求
- **WHEN** 前端调用构建验证创建接口
- **THEN** 后端 SHALL 校验项目访问权限、源码版本、当前运行环境配置和成功源码部署记录
- **AND** 后端 SHALL 创建构建任务和构建运行记录

#### Scenario: 构建详情响应
- **WHEN** 前端查询构建详情
- **THEN** 响应 SHALL 包含构建运行 ID、任务 ID、环境摘要、源码版本摘要、状态、退出码、失败分类、merged/stdout/stderr 日志 ID 和时间字段
- **AND** 响应 MUST NOT 返回完整构建脚本明文、明文凭据或服务器本机路径

#### Scenario: 构建实时状态
- **WHEN** 构建任务运行中
- **THEN** 前端 SHALL 通过项目级 SSE 观察任务状态变化
- **AND** 运行中密集日志 SHALL 使用任务级日志 SSE
- **AND** 构建完成后历史日志 SHALL 使用任务日志内容读取 API

#### Scenario: 读取项目概览
- **WHEN** 前端读取项目概览
- **THEN** 概览 SHALL 能返回构建验证摘要和最新任务事件 baseline
