## Why

当前源码压缩包上传受 Spring/Tomcat 默认 multipart 1MiB 限制，导致真实源码包上传直接失败；同时 Git 同步对用户输入的仓库 URL 过于字面化，常见的无 `.git` 结尾仓库地址需要人工调整后才能稳定使用。现在前后端联调已经进入真实源码接入阶段，需要先解决这两个输入兼容性问题。

## What Changes

- 将源码包上传的后端 multipart 单文件大小和请求总大小提升到 10GB，并支持通过环境变量覆盖。
- 在 Docker Compose 后端服务中暴露对应上传大小配置，保证容器运行环境与应用配置一致。
- 若请求经前端 nginx 代理进入后端，前端代理也需要允许 10GB 请求体，避免代理层先拦截大文件上传。
- Git 同步 API 在保存任务输入前规范化 Git URL：常见 HTTP(S) 和 SSH scp 风格仓库 URL 缺少 `.git` 后缀时自动补齐，已有 `.git` 后缀保持不变。
- 保留现有安全边界：Git URL 内嵌用户名、密码或 token 仍然拒绝；源码来源锁定、项目权限校验和响应路径脱敏不变。
- 补充单元测试和 E2E 覆盖，验证大文件配置、Git URL 规范化和异常边界。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `backend-api-design`: 源码上传 API 明确支持最大 10GB 源码压缩包，Git 同步 API 明确兼容缺少 `.git` 后缀的常见仓库 URL。
- `project-source-environment`: 源码输入能力补充上传大小配置要求和 Git URL 规范化行为。

## Impact

- 影响后端配置：`application.yml`、Docker Compose 后端环境变量，以及可能的前端 nginx 代理配置。
- 影响源码领域代码：`GitUrlValidator` 和 Git 同步任务输入。
- 影响测试：Git URL validator/service 单元测试、配置测试、源码 E2E case。
- 不变更数据库 schema，不改变源码来源锁定模型，不改变凭据存储和脱敏策略。
