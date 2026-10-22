## ADDED Requirements

### Requirement: KB 扫描 artifact 必须支持按格式下载
后端 API SHALL 支持按报告格式下载 KB 扫描 artifact，使前端无需先解析 artifact 列表中的 `artifactId` 即可下载 HTML、JSON 或日志。

#### Scenario: 按 HTML 格式下载 KB 扫描报告
- **WHEN** 已登录用户调用 `GET /api/kb-scans/{scanId}/artifacts:download?format=html`
- **THEN** 后端 SHALL 根据扫描运行所属项目校验访问权限
- **AND** 后端 SHALL 下载该扫描运行的 `SCAN_REPORT_HTML` artifact
- **AND** 响应 SHALL 使用安全文件名和 `text/html` content type
- **AND** 响应 MUST NOT 暴露服务器真实路径、源码工作副本路径或 scanner 输出目录

#### Scenario: 按 JSON 格式下载 KB 扫描结果
- **WHEN** 已登录用户调用 `GET /api/kb-scans/{scanId}/artifacts:download?format=json`
- **THEN** 后端 SHALL 根据扫描运行所属项目校验访问权限
- **AND** 后端 SHALL 下载该扫描运行的 `SCAN_RESULT_JSON` artifact
- **AND** 响应 SHALL 使用安全文件名和 `application/json` content type
- **AND** 响应 MUST NOT 暴露服务器真实路径、源码工作副本路径或 scanner 输出目录

#### Scenario: 按日志格式下载 KB 扫描日志
- **WHEN** 已登录用户调用 `GET /api/kb-scans/{scanId}/artifacts:download?format=log`
- **THEN** 后端 SHALL 根据扫描运行所属项目校验访问权限
- **AND** 后端 SHALL 下载该扫描运行的 `SCAN_LOG` artifact
- **AND** 响应 SHALL 使用安全文件名和 `text/plain` content type
- **AND** 响应 MUST NOT 暴露服务器真实路径、源码工作副本路径或 scanner 输出目录

#### Scenario: 下载格式不支持
- **WHEN** 用户调用按格式下载接口且 `format` 不是 `html`、`json` 或 `log`
- **THEN** 后端 SHALL 返回统一业务错误
- **AND** 后端 MUST NOT 返回 artifact 存储路径、扫描输出目录或内部异常细节

#### Scenario: 指定格式 artifact 不存在
- **WHEN** 用户调用按格式下载接口且该扫描运行没有对应格式 artifact
- **THEN** 后端 SHALL 返回与资源不存在一致的安全错误
- **AND** 后端 MUST NOT 暴露其他 artifact 是否存在或服务器真实路径

#### Scenario: 保留按 artifact ID 下载
- **WHEN** 已登录用户调用 `GET /api/kb-scans/{scanId}/artifacts/{artifactId}/download`
- **THEN** 后端 SHALL 继续按指定 artifact ID 下载文件
- **AND** 后端 SHALL 校验 artifact 属于该扫描运行并校验项目访问权限
- **AND** 响应 MUST NOT 暴露服务器真实路径、源码工作副本路径或 scanner 输出目录
