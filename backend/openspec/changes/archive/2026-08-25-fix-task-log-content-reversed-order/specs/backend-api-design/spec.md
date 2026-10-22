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
- **AND** 不传参数时每类默认返回最新展示页最多 100 行
- **AND** 响应 MUST NOT 返回服务器真实日志文件路径

#### Scenario: 读取单类或多类不同 offset
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/log-content?types=merged,stdout&mergedOffset=0&stdoutOffset=100&mergedLines=100&stdoutLines=50`
- **THEN** API SHALL 只返回请求的日志类型
- **AND** 每个日志类型 SHALL 使用自己的 offset 和 lines
- **AND** offset SHALL 表示按前端展示顺序跳过的行数
- **AND** `offset=0` SHALL 返回该日志类型的最新展示页
- **AND** 未设置单类 lines 时 SHALL 使用全局 `lines` 或默认值

#### Scenario: 倒序日志内容读取
- **WHEN** 日志文件物理内容为最新日志在文件头、较早日志在文件尾
- **THEN** `GET /api/tasks/{taskId}/log-content?types=merged&mergedOffset=0` SHALL 返回文件头部对应的最新展示页
- **AND** `mergedOffset` 增大时 SHALL 返回更旧的日志页

#### Scenario: 下载日志文件
- **WHEN** 前端调用 `GET /api/tasks/{taskId}/logs/{logId}/download`
- **THEN** API SHALL 校验日志属于该任务
- **AND** API SHALL 通过受控下载返回日志内容
- **AND** API MUST NOT 接受客户端传入服务器文件路径作为下载参数
