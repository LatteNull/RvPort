## 1. 基础模型与公共能力

- [x] 1.1 创建 `project`、`source`、`environment`、`credential` 包，并按现有风格拆分 Controller、Service、Repository、DTO。
- [x] 1.2 定义项目、源码版本、源码导入、环境、环境快照和凭据遮蔽摘要的响应 DTO。
- [x] 1.3 定义项目列表、源码列表、环境列表和快照列表的分页/筛选请求对象。
- [x] 1.4 定义项目、源码、环境相关枚举或常量，覆盖 stage、status、revisionType、environmentRole、credentialKind 和任务类型。
- [x] 1.5 补充通用校验工具，覆盖 Git URL 凭据检测、安全文件名归一化、SSH 端口、凭据请求类型、跳板机引用和上传目录解析。

## 2. 数据库迁移与 jOOQ

- [x] 2.1 新增 Liquibase changelog，为 `environments` 增加可空 `jump_host_environment_id uuid` 字段。
- [x] 2.2 为 `environments.jump_host_environment_id` 增加自引用外键和索引。
- [x] 2.3 增加数据库或服务层约束，禁止环境引用自己作为跳板机。
- [x] 2.4 运行 Liquibase 验证空库和已有库迁移可执行。
- [x] 2.5 运行 jOOQ 生成脚本，提交更新后的 `src/generated/java`。
- [x] 2.6 为跳板机字段迁移和 jOOQ 生成结果补充校验。

## 3. 凭据加密与遮蔽展示

- [x] 3.1 实现 `CredentialRepository`，支持创建凭据、按 ID 查询凭据摘要、校验项目归属和更新凭据状态。
- [x] 3.2 实现 `CredentialService`，使用 `CredentialCipher` 将 Git/SSH 凭据 payload 加密后写入 `credentials.encrypted_payload`。
- [x] 3.3 实现 SSH 密码、SSH 私钥、Git 密码和 Git token 的 payload 构造与 `maskedSummary` 生成。
- [x] 3.4 确保凭据查询响应只返回 `configured`、`id`、`kind`、`name` 和 `maskedSummary`。
- [x] 3.5 在凭据加密密钥缺失或格式无效时返回明确 API 错误，并确认不会写入明文凭据。
- [x] 3.6 为凭据加密、遮蔽展示、密钥缺失和禁止明文泄露补充单元测试，覆盖正常流程、异常流程和 edge case。

## 4. 项目管理 API

- [x] 4.1 实现 `ProjectRepository`，支持创建、详情、分页列表、筛选、更新、软删除状态过滤和基础统计查询。
- [x] 4.2 实现 `ProjectService`，创建项目时设置 `PROJECT_CREATED`、`ACTIVE` 和当前用户 ID。
- [x] 4.3 实现 `GET /api/projects`、`POST /api/projects`、`GET /api/projects/{projectId}` 和 `PATCH /api/projects/{projectId}`。
- [x] 4.4 限制项目更新接口不能任意写入 `stage`，只允许更新基础信息和项目状态。
- [x] 4.5 实现 `GET /api/projects/{projectId}/overview`，聚合项目、当前源码、源码数量、环境摘要、最近任务和推荐下一步动作。
- [x] 4.6 为项目创建、列表筛选、详情、更新和 overview 聚合补充测试，覆盖正常流程、异常流程和 edge case。

## 5. 源码版本 API

- [x] 5.1 实现 `SourceRepository`，支持源码版本列表、创建源码版本、切换当前版本和创建源码导入记录。
- [x] 5.2 实现压缩包上传保存逻辑，使用 `RVPORT_UPLOAD_DIR`、项目 ID 和源码版本 ID 组织本地路径。
- [x] 5.3 实现 `GET /api/projects/{projectId}/sources`，返回源码版本分页列表并隐藏服务器本地路径。
- [x] 5.4 实现 `POST /api/projects/{projectId}/sources/archive`，创建 `ARCHIVE` 源码版本和 `source_imports` 记录。
- [x] 5.5 实现源码版本激活逻辑，在同一事务内取消同项目其他 active 版本并启用目标版本。
- [x] 5.6 实现 `POST /api/projects/{projectId}/sources/{sourceRevisionId}/activate`，校验源码版本归属并写入审计日志。
- [x] 5.7 实现 `POST /api/projects/{projectId}/sources/git-sync`，拒绝内嵌凭据的 Git URL，支持引用或新建 Git 凭据。
- [x] 5.8 Git 同步请求创建 `SOURCE_GIT_SYNC` 任务和 `source_imports` 记录，任务输入快照不得包含明文凭据。
- [x] 5.9 为源码上传、重复上传、版本切换、Git URL 校验、Git 任务投递和路径隐藏补充测试，覆盖正常流程、异常流程和 edge case。

## 6. 环境管理 API

- [x] 6.1 实现 `EnvironmentRepository`，支持环境创建、详情、列表筛选、更新、禁用、跳板机引用和快照分页查询。
- [x] 6.2 实现 `EnvironmentService`，创建环境时保存或引用 SSH 凭据，并设置默认 `UNKNOWN` 与 `enabled=true`。
- [x] 6.3 实现 `GET /api/projects/{projectId}/environments` 和 `POST /api/projects/{projectId}/environments`。
- [x] 6.4 实现 `GET /api/environments/{environmentId}` 和 `PATCH /api/environments/{environmentId}`，响应包含凭据遮蔽摘要和跳板机非敏感摘要。
- [x] 6.5 支持创建和更新环境时配置 `jumpHostEnvironmentId`。
- [x] 6.6 校验跳板机必须属于同一项目、已启用、不能自引用，且 MVP 不允许多级跳板链路。
- [x] 6.7 禁止禁用仍被其他环境引用的跳板机。
- [x] 6.8 禁止禁用环境创建新的连接测试、环境采集或远程脚本任务。
- [x] 6.9 实现 `GET /api/environments/{environmentId}/snapshots`，按采集时间倒序返回快照分页列表。
- [x] 6.10 为环境创建、更新、禁用、跳板机校验、筛选、凭据遮蔽和快照列表补充测试，覆盖正常流程、异常流程和 edge case。

## 7. 环境与源码长任务投递

- [x] 7.1 将 `SOURCE_GIT_SYNC`、`ENV_TEST_CONNECTION`、`ENV_COLLECT`、`ENV_RUN_SCRIPT` 纳入任务类型常量和响应显示。
- [x] 7.2 实现 `POST /api/environments/{environmentId}/test-connection`，创建并投递 `ENV_TEST_CONNECTION` 任务。
- [x] 7.3 实现 `POST /api/environments/{environmentId}/collect`，创建并投递 `ENV_COLLECT` 任务。
- [x] 7.4 实现 `POST /api/environments/{environmentId}/scripts`，创建并投递 `ENV_RUN_SCRIPT` 任务。
- [x] 7.5 确保任务 input snapshot 只包含项目 ID、环境 ID、跳板机环境 ID、源码导入 ID、凭据 ID、脚本摘要、超时等安全字段。
- [x] 7.6 为长任务创建、队列投递、输入快照脱敏、禁用环境拒绝任务、跳板机引用和任务响应补充测试，覆盖正常流程、异常流程和 edge case。

## 8. 审计与安全

- [x] 8.1 为项目创建/更新、源码上传、源码激活、Git 同步、环境创建/更新、跳板机变更、凭据替换和环境任务创建写入审计日志。
- [x] 8.2 扩展审计记录时包含可用的 `project_id`，并保持历史认证审计兼容。
- [x] 8.3 审计详情不得包含明文密码、私钥、token、passphrase、加密密文或服务器本地路径。
- [x] 8.4 补充未登录访问、强制改密用户访问和普通登录用户访问项目 API 的安全测试，覆盖正常流程、异常流程和 edge case。

## 9. 测试覆盖策略

- [x] 9.1 为每个核心服务测试类按正常流程、异常流程和 edge case 三类组织测试用例。
- [x] 9.2 正常流程测试必须覆盖项目创建/查询、源码上传/激活、环境创建/跳板机配置、凭据加密保存和任务投递。
- [x] 9.3 异常流程测试必须覆盖资源不存在、非法状态、未登录或强制改密限制、Git URL 内嵌凭据、凭据密钥缺失、禁用环境创建任务。
- [x] 9.4 Edge case 测试必须覆盖空列表、可选字段为空、重复源码上传、active 源码切换、跳板机自引用、多级跳板、跨项目跳板、分页边界和 SSH 端口边界。

## 10. 集成验证与文档同步

- [x] 10.1 运行 `mvn test`，确认现有测试和新增测试全部通过。
- [x] 10.2 在本地基础设施运行时，实际验证创建项目、上传源码、创建跳板机环境、创建通过跳板机访问的源/目标环境、Git 同步任务、环境任务投递和 SSE/任务列表可见性。
- [x] 10.3 验证 PostgreSQL 中项目、源码、导入、环境、跳板机引用、凭据、任务和审计记录的变化符合预期。
- [x] 10.4 验证 Redis/RabbitMQ 中无明文凭据泄露，RabbitMQ 消息只承载任务 ID 等路由信息。
- [x] 10.5 清理手工联通验证产生的测试数据和上传文件。
- [x] 10.6 如接口字段与 `docs/API_DESIGN.md` 或 `docs/DATABASE_DESIGN.md` 存在差异，同步更新中文文档。
