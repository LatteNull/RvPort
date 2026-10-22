## Context

源码包上传现在没有显式 multipart 配置，Spring Boot/Tomcat 使用默认 1MiB 单文件限制。真实源码包上传时会在进入 `SourceService.uploadArchive()` 前被容器层拒绝，错误表现为 `FileSizeLimitExceededException: maximum permitted size of 1048576 bytes`。

Git 同步当前入口为 `POST /api/projects/{projectId}/sources/git-sync`，`GitUrlValidator` 负责非空和 HTTP(S) 内嵌凭据校验，worker 侧 `ProcessGitClientAdapter` 直接执行 `git clone <gitUrl> <worktreeDir>`。常见 Git 平台通常同时接受带 `.git` 和不带 `.git` 的 HTTP(S) URL，但为了减少不同平台行为差异，后端应在任务创建前将常见仓库 URL 规范化。

## Goals / Non-Goals

**Goals:**

- 后端源码压缩包上传支持最大 10GB 的单文件和请求体。
- 上传大小支持环境变量覆盖，容器部署可通过 `.env` 调整。
- Git 同步 API 对常见 HTTP(S) 和 SSH scp 风格仓库 URL 自动补齐 `.git` 后缀。
- 保持 Git URL 内嵌凭据拒绝、源码来源锁定和项目权限校验不变。
- 补充单元测试、配置测试和源码 E2E 覆盖。

**Non-Goals:**

- 不把 archive 上传/解包改造成异步任务；本 change 仍沿用当前同步上传和同步解包流程。
- 不修改数据库 schema。
- 不改变凭据表、Git askpass 机制或 Git worker 的 clone/fetch 实现。
- 不把非仓库 URL、复杂本地路径或特殊 Git transport 强行改写为 `.git`。
- 不把前端 nginx 配置作为本 change 的强制实现范围；如果后续用户经前端容器上传仍遇到代理层 413，应由前端/部署 change 单独补齐 `client_max_body_size`。

## Decisions

1. **通过 Spring Boot multipart 配置提升上传上限**

   在 `application.yml` 中设置：

   - `spring.servlet.multipart.max-file-size=${RVPORT_MAX_FILE_SIZE:10GB}`
   - `spring.servlet.multipart.max-request-size=${RVPORT_MAX_REQUEST_SIZE:10GB}`

   这样可以直接覆盖 Tomcat 当前 1MiB 默认限制，并允许部署时通过 `.env` 或容器环境变量降级或调大。相比在 controller/service 中自行判断 `MultipartFile.getSize()`，这种方式能在容器解析 multipart 前阻止超限请求，行为更接近实际入口。

2. **在 GitUrlValidator 阶段做 URL 规范化**

   规范化应发生在 `SourceService.gitSync()` 创建任务和保存凭据前，因为任务 input snapshot、审计摘要和 credential metadata 都应使用同一个脱敏后的规范 URL。

   规则：

   - 先 `trim`。
   - HTTP(S) URL：保留 query/fragment 禁止策略，仓库 URL 若包含 query 或 fragment，视为不适合自动补齐；普通 path 去掉末尾 `/` 后，最后一段不以 `.git` 结尾则追加 `.git`。
   - SSH scp 风格：如 `git@github.com:org/repo`，去掉末尾 `/` 后追加 `.git`。
   - `ssh://` 等 URI 风格：可按 path 末段同样处理，但仍不接受内嵌凭据。
   - 已以 `.git` 结尾时保持原样。
   - 空 URL、HTTP(S) 内嵌用户名/密码/token 继续返回现有错误。

   这样比在 worker clone 失败后重试更可控：数据库、任务、审计中只有一个规范化 URL，不会出现“用户输入 URL”和“实际 clone URL”分裂。

3. **上传 10GB 的长期风险单独留给后续异步化**

   10GB 上传和解包仍在请求线程中完成，可能带来长连接、磁盘空间和请求超时风险。这个 change 只解决当前硬限制，不改变交互模型。后续如果真实 10GB 包频繁使用，应单独设计 archive import 长任务和上传进度模型。

## Risks / Trade-offs

- [Risk] 10GB 同步上传可能超过前端代理、网关、浏览器或部署平台超时。→ Mitigation: 本 change 只保证后端 Tomcat 限制放开；文档说明代理层也需要匹配配置，后续可做异步上传任务。
- [Risk] 自动追加 `.git` 可能误改某些非标准 URL。→ Mitigation: 仅对明确的 HTTP(S)/SSH 仓库 URL 规范化；带 query/fragment 或不识别格式时保持原样，只继续执行安全校验。
- [Risk] 规范化 URL 后审计记录与用户原始输入不完全一致。→ Mitigation: 以实际执行 URL 为准，避免任务和 worker 行为分裂；不记录原始输入以减少敏感信息风险。
- [Risk] 大文件 E2E 直接创建 10GB 测试文件成本过高。→ Mitigation: 单元/配置测试验证上限配置；E2E 使用小文件确认上传链路仍可用，必要时增加可选 smoke 校验响应不再是 1MiB 限制。
