## ADDED Requirements

### Requirement: 构建和 KB API 必须返回 compile database 使用摘要
后端 API SHALL 在构建详情和 KB 扫描详情中返回安全的 compile database 使用摘要，使前端能展示扫描是否使用了真实构建上下文。

#### Scenario: 构建详情返回 compile database 摘要
- **WHEN** 用户调用 `GET /api/builds/{buildId}`
- **THEN** 响应 SHALL 包含 compile database 可用状态、stored artifact ID、sha256、size bytes、command count 和来源摘要
- **AND** 响应 MUST NOT 返回完整 compile database、远端工作目录、服务器真实路径、bucket 或 object key

#### Scenario: KB 扫描详情返回 compile database 使用情况
- **WHEN** 用户调用 `GET /api/kb-scans/{scanId}`
- **THEN** 响应 SHALL 包含 `compileCommands` 摘要
- **AND** 摘要 SHALL 表达 `USED`、`NOT_AVAILABLE` 或 `FALLBACK`
- **AND** 当状态为 `USED` 时，摘要 SHALL 包含来源 build run ID、stored artifact ID、sha256 和 command count
- **AND** 当状态不是 `USED` 时，摘要 SHALL 包含安全原因码

#### Scenario: KB 创建接口不要求前端提交 compile database
- **WHEN** 用户调用 `POST /api/projects/{projectId}/kb-scans`
- **THEN** 请求体 MUST NOT 要求提交 compile database 路径、文件或 artifact ID
- **AND** 后端 SHALL 在 worker 执行阶段自动解析可用构建上下文

#### Scenario: 无权限访问摘要
- **WHEN** 用户无权访问构建运行或 KB 扫描所属项目
- **THEN** 后端 SHALL 返回与资源不存在一致的安全错误
- **AND** 后端 MUST NOT 暴露 compile database artifact 是否存在
