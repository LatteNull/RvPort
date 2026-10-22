## 1. 测试基线与辅助断言

- [x] 1.1 复核当前 `mvn test` 基线，记录测试总数、跳过项和已知 warning。
- [x] 1.2 建立或复用测试辅助断言，用于检查响应、审计 details、任务 input snapshot 和消息载荷不包含密码、token、privateKey、passphrase、script 原文。
- [x] 1.3 确认新增测试只依赖 mock、临时目录或内存上下文，普通 `mvn test` 不要求真实 Docker Compose 基础设施。

## 2. 认证与用户管理补测

- [x] 2.1 为 `AuthService` 补充 disabled 用户登录失败测试，并验证写入失败审计原因。
- [x] 2.2 为 `AuthService` 补充当前用户不存在、当前用户禁用、改密当前密码错误的异常测试。
- [x] 2.3 为 `AuthService` 补充改密后不泄露明文密码或密码哈希的断言。
- [x] 2.4 为 `AdminUserService` 补充 username 重复、email 重复和用户不存在的异常测试。
- [x] 2.5 为 `AdminUserService` 补充 update 禁止 username、isSuperAdmin、mustChangePassword、passwordHash、roles、permissions 字段的测试。
- [x] 2.6 为 `AdminUserService` 补充空白 displayName/email 转 null、resetPassword 显式 `mustChangePassword=false` 的 edge case 测试。

## 3. 项目与源码补测

- [x] 3.1 为 `ProjectService` 补充 get/update/overview 项目不存在的异常测试。
- [x] 3.2 为 `ProjectService` 补充 update 保留未传字段、更新审计 changedFields 的 edge case 测试。
- [x] 3.3 为 `SourceService` 补充 list 项目不存在和空源码包上传的异常测试。
- [x] 3.4 为 `SourceService` 补充源码版本不存在、源码版本跨项目激活的异常测试。
- [x] 3.5 为 `SourceService` 补充 `activate=false` 不调用 `clearActive`、`activate=true` 调用 `clearActive` 的 edge case 测试。
- [x] 3.6 为 `SourceService` 补充 Git token/password 自动创建凭据分支，并断言任务 input snapshot 不包含明文 secret。
- [x] 3.7 为 `SourceService` 补充上传保存失败映射为 `SOURCE_ARCHIVE_SAVE_FAILED` 的异常测试。

## 4. 环境与凭据补测

- [x] 4.1 为 `CredentialService` 补充 `requireActive` 凭据不存在和项目不匹配的异常测试。
- [x] 4.2 为 `CredentialService` 补充 SSH 密码、SSH 私钥、Git 凭据类型错误和 Git secret 为空的异常测试。
- [x] 4.3 为 `CredentialService` 补充长 token 脱敏只显示尾部、默认凭据名称 fallback 的 edge case 测试。
- [x] 4.4 为 `EnvironmentService` 补充项目不存在、创建环境未提供 credentialId/loginType 的异常测试。
- [x] 4.5 为 `EnvironmentService` 补充跳板机跨项目、跳板机禁用、禁用被引用跳板机的异常测试。
- [x] 4.6 为 `EnvironmentService` 补充 update 清除 jumpHost、默认 sshPort=22、保留未传字段的 edge case 测试。
- [x] 4.7 为 `EnvironmentService` 补充 testConnection、collect、runScript 创建任务的正常流程测试。
- [x] 4.8 为 `EnvironmentService` 补充 runScript 只写入 scriptSha256/scriptLength，不写入脚本原文的敏感信息测试。
- [x] 4.9 为 `EnvironmentService` 补充 snapshots 空列表分页和环境不存在异常测试。

## 5. 任务、日志和 worker 补测

- [x] 5.1 为 `TaskService` 补充 task 不存在、create 缺 projectId、createdBy、type 的异常测试。
- [x] 5.2 为 `TaskService` 补充 input snapshot 不可序列化时返回 `TASK_INPUT_INVALID` 的异常测试。
- [x] 5.3 为 `TaskService` 补充终态任务 cancel 幂等返回当前任务、不重复追加取消事件的 edge case 测试。
- [x] 5.4 为 `TaskService` 补充 queued 任务 cancel 正常追加取消事件的测试。
- [x] 5.5 为 `TaskLogService` 补充日志记录不存在、日志文件不存在、合法嵌套相对路径可下载的测试。
- [x] 5.6 为 `TaskLogService` 补充 Unix `../`、绝对路径和 Windows 盘符路径的非法路径 edge case 测试。
- [x] 5.7 为 `TaskWorkerService` 补充 taskId 不存在时跳过、不查 handler 的测试。
- [x] 5.8 为 `TaskWorkerService` 补充 handler 抛异常时标记 FAILED、错误码为 `HANDLER_FAILED` 的测试。
- [x] 5.9 为 `TaskWorkerService` 补充 handler 异常 message 为空时使用默认安全消息的 edge case 测试。

## 6. Controller 与安全边界补测

- [x] 6.1 为 `AdminUserController` 补充 create/update/reset 请求校验和错误包络测试。
- [x] 6.2 为 `ProjectController` 补充 create/update 请求校验、非法分页和统一响应包络测试。
- [x] 6.3 为 `SourceController` 补充 multipart 空文件、Git sync 参数非法和错误包络测试。
- [x] 6.4 为 `EnvironmentController` 补充 create/update/runScript 参数校验、非法分页和错误包络测试。
- [x] 6.5 为 `TaskController` 补充任务详情、取消、日志列表和日志下载错误包络测试。
- [x] 6.6 为安全过滤器补充 `/api/auth/csrf`、`/api/auth/logout` 在 mustChangePassword 状态下允许访问的 edge case 测试；`/api/auth/login` 发生在认证前，不属于 mustChangePassword 已认证主体过滤白名单，本次按当前安全设计记录为不适用。

## 7. 验证与收尾

- [x] 7.1 运行受影响测试类，确认新增测试全部通过。
- [x] 7.2 运行完整 `mvn test`，确认普通 Maven 测试通过且独立 API E2E 未被自动执行。
- [x] 7.3 复核新增测试是否覆盖正常流程、异常流程和 edge case；对不适用项在 tasks 或实现说明中记录原因。
- [x] 7.4 如果补测发现生产代码缺陷，完成最小生产修复并补充对应回归测试。
- [x] 7.5 检查测试中没有硬编码真实环境秘密、没有依赖本机 Docker Compose 状态、没有留下临时文件。
