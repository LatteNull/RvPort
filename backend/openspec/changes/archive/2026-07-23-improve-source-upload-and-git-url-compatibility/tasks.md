## 1. Multipart 上传配置

- [x] 1.1 在 `application.yml` 中配置 `spring.servlet.multipart.max-file-size` 默认 10GB，并支持环境变量覆盖
- [x] 1.2 在 `application.yml` 中配置 `spring.servlet.multipart.max-request-size` 默认 10GB，并支持环境变量覆盖
- [x] 1.3 确认 Docker Compose 后端运行环境可通过 `.env` 设置上传大小上限；如需要，补充后端服务环境变量
- [x] 1.4 检查当前全局异常处理对 multipart 超限异常的响应，确保返回统一错误包络且不暴露内部堆栈或服务器路径

## 2. Git URL 规范化

- [x] 2.1 在 `GitUrlValidator` 中实现 HTTP(S) 仓库 URL 去除末尾 `/` 和缺失 `.git` 时自动补齐
- [x] 2.2 在 `GitUrlValidator` 中实现 SSH scp 风格仓库 URL 缺失 `.git` 时自动补齐
- [x] 2.3 确保已有 `.git` 后缀不会被重复追加
- [x] 2.4 确保 HTTP(S) URL 内嵌凭据仍然返回 `GIT_URL_CONTAINS_CREDENTIAL`
- [x] 2.5 对带 query、fragment 或不适合安全识别的 URL 保持原样，不强行补齐 `.git`
- [x] 2.6 确认 `SourceService.gitSync()` 的任务 input snapshot、凭据 metadata 和审计摘要都使用规范化后的 Git URL

## 3. 测试与 E2E

- [x] 3.1 补充 `GitUrlValidatorTests` 正常流程：HTTP(S) 无 `.git` 自动补齐、已有 `.git` 原样、末尾 `/` 处理
- [x] 3.2 补充 `GitUrlValidatorTests` edge case：SSH scp 风格无 `.git` 自动补齐、带 query/fragment 不自动补齐
- [x] 3.3 补充 Git URL 异常流程测试：空 URL 和内嵌凭据继续拒绝
- [x] 3.4 补充 `SourceServiceTests`，确认 `gitSync` 创建任务时 input snapshot 使用规范化 URL
- [x] 3.5 补充配置测试，确认 multipart 默认上限为 10GB，并可通过环境变量覆盖
- [x] 3.6 更新源码 E2E case，使用无 `.git` 后缀的公开仓库 URL 创建 Git 同步任务并确认任务输入或后续记录使用规范化 URL
- [x] 3.7 运行源码相关单元测试和 E2E module，确认 archive 上传与 Git 同步路径仍通过

## 4. 文档与验证

- [x] 4.1 更新 `backend/docs/API_DESIGN.md`，说明源码压缩包默认最大 10GB 和 Git URL 自动补齐 `.git`
- [x] 4.2 更新 `backend/docs/api-e2e-coverage.md`，补充源码 E2E 覆盖点
- [x] 4.3 运行完整 Maven 测试
- [x] 4.4 运行 `openspec validate improve-source-upload-and-git-url-compatibility`
