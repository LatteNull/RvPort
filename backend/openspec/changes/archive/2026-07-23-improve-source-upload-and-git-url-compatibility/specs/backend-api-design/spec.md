## ADDED Requirements

### Requirement: 源码上传 API 必须支持 10GB 压缩包请求
后端源码上传 API SHALL 支持最大 10GB 的源码压缩包 multipart 上传，并 SHALL 通过环境变量允许部署时覆盖上限。

#### Scenario: 上传不超过 10GB 的源码包
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/sources/archive` 并上传大小不超过 10GB 的受支持源码压缩包
- **THEN** 后端 SHALL 允许 multipart 请求进入源码上传处理流程
- **AND** 后端 SHALL 继续执行项目访问权限校验、源码来源锁定校验、文件格式校验和路径安全校验
- **AND** API 响应 MUST NOT 返回 `archivePath`、`workingCopyPath` 或服务器真实路径

#### Scenario: 上传超过配置上限的源码包
- **WHEN** 用户上传的源码包大小超过后端配置的 multipart 单文件或请求总大小上限
- **THEN** 后端 SHALL 返回统一错误响应
- **AND** 响应 MUST NOT 暴露服务器临时路径、容器内部路径或 multipart parser 内部堆栈

#### Scenario: 通过环境变量覆盖上传上限
- **WHEN** 部署环境设置源码上传 multipart 大小上限环境变量
- **THEN** 后端 SHALL 使用环境变量值覆盖默认 10GB 限制
- **AND** 未设置环境变量时 SHALL 使用 10GB 作为默认上限

### Requirement: Git 同步 API 必须兼容无 .git 后缀仓库 URL
后端 Git 同步 API SHALL 在创建任务前规范化常见 Git 仓库 URL，使缺少 `.git` 后缀的 HTTP(S) 或 SSH 仓库 URL 可以自动兼容。

#### Scenario: HTTP Git URL 自动补齐 .git
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/sources/git-sync` 且 `gitUrl` 为 `https://example.com/org/repo`
- **THEN** 后端 SHALL 将任务输入中的 `gitUrl` 规范化为 `https://example.com/org/repo.git`
- **AND** 后端 SHALL 使用规范化后的 URL 创建 Git 同步任务
- **AND** 响应和日志 MUST NOT 暴露明文凭据

#### Scenario: 已有 .git 后缀保持不变
- **WHEN** 用户提交的 `gitUrl` 已经以 `.git` 结尾
- **THEN** 后端 SHALL 保持该 URL 不重复追加 `.git`
- **AND** 后端 SHALL 继续执行内嵌凭据校验

#### Scenario: SSH scp 风格 Git URL 自动补齐 .git
- **WHEN** 用户提交的 `gitUrl` 为 `git@example.com:org/repo`
- **THEN** 后端 SHALL 将任务输入中的 `gitUrl` 规范化为 `git@example.com:org/repo.git`
- **AND** 后端 SHALL 使用规范化后的 URL 创建 Git 同步任务

#### Scenario: Git URL 内嵌凭据仍被拒绝
- **WHEN** 用户提交的 HTTP(S) Git URL 包含用户名、密码或 token
- **THEN** 后端 SHALL 返回 `GIT_URL_CONTAINS_CREDENTIAL`
- **AND** 后端 MUST NOT 创建源码导入记录、任务或凭据

#### Scenario: 不识别或不适合规范化的 Git URL
- **WHEN** 用户提交的 Git URL 带 query、fragment 或不属于可安全识别的仓库 URL 形式
- **THEN** 后端 MAY 保持原 URL 不做 `.git` 自动补齐
- **AND** 后端 SHALL 继续执行非空和安全校验
