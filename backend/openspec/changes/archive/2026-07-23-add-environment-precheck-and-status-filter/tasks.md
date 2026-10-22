## 1. API 与请求模型

- [x] 1.1 新增新建环境连接预检请求 DTO，复用创建环境所需的 SSH 连接字段并增加可选 `timeoutSeconds`
- [x] 1.2 在 `EnvironmentController` 增加 `POST /api/projects/{projectId}/environments/test-connection`
- [x] 1.3 扩展 `EnvironmentListRequest`，增加 `EnvironmentStatus status` 查询参数

## 2. 环境服务与任务输入

- [x] 2.1 在 `EnvironmentService` 增加新建环境预检入口，校验项目权限、连接字段、凭据和跳板机
- [x] 2.2 生成不包含明文凭据的 `ENV_TEST_CONNECTION` 任务输入，区分 `environmentId` 模式和未落库 `target` 模式
- [x] 2.3 复用或扩展凭据加密保存逻辑，确保请求中提交的新凭据不会以明文进入任务、日志、审计或响应
- [x] 2.4 保持已有已创建环境连接复测逻辑兼容

## 3. Worker 与 SSH Runtime

- [x] 3.1 扩展 `EnvironmentTestConnectionHandler` 或 SSH runtime 输入解析，支持未落库目标配置
- [x] 3.2 新建环境预检成功或失败时只更新任务、日志、tool run 和 SSE，不写入正式环境状态或快照
- [x] 3.3 保持已创建环境连接复测继续更新 `environments.status` 和 `last_connected_at`

## 4. 环境列表状态过滤

- [x] 4.1 扩展 `EnvironmentRepository.count/list/filter`，支持 `status` 与 `role/enabled` 组合过滤
- [x] 4.2 确认 `status=AVAILABLE&enabled=true&role=SOURCE_X86|TARGET_RISCV` 可用于 SBOM 环境选择
- [x] 4.3 非法状态值通过参数绑定校验返回统一错误，不能进入 SQL 拼接

## 5. 测试与验证

- [x] 5.1 补充单元测试正常流程：新建环境预检创建任务、已创建环境复测保持兼容、环境列表按 status 过滤
- [x] 5.2 补充单元测试异常流程：无项目权限、非法跳板机、缺少凭据、凭据加密配置不可用、禁用跳板机
- [x] 5.3 补充 edge case 测试：默认端口、默认超时、status 与 role/enabled 组合、非法状态、任务输入脱敏
- [x] 5.4 补充或更新 E2E 模块，覆盖新建环境预检和 `status=AVAILABLE` 环境列表查询
- [x] 5.5 运行 `mvn test` 和相关 E2E，确认无回归并清理测试数据

## 6. 文档与 OpenSpec

- [x] 6.1 更新 `docs/API_DESIGN.md` 中环境接口说明
- [x] 6.2 如实现引入临时凭据语义，补充 README 或运维说明中的安全注意事项
- [x] 6.3 运行 `openspec validate add-environment-precheck-and-status-filter`

## 7. 预检临时凭据语义修正

- [x] 7.1 更新 OpenSpec artifact，明确未保存表单预检不得写入正式 `credentials`
- [x] 7.2 新增 `task_secret_payloads` Liquibase migration 和任务级 secret repository/service
- [x] 7.3 修改预检任务创建逻辑：明文密码或私钥只保存到任务级加密 payload，`input_snapshot` 只保存引用和 hash
- [x] 7.4 修改 SSH runtime：target 模式支持从 `temporaryCredentialPayloadId` 解密临时 SSH 凭据
- [x] 7.5 更新单元测试和 E2E，确认明文预检不会创建 `credentials` 记录且能真实连通
- [x] 7.6 重新运行 `mvn test`、相关 E2E 和 `openspec validate`

## 8. 预检临时凭据终态清理

- [x] 8.1 更新 OpenSpec artifact，明确任务终态后删除 `task_secret_payloads`、保留任务结果和日志
- [x] 8.2 新增按任务删除临时 secret 的 repository/service 方法
- [x] 8.3 在 worker 成功、失败、取消等终态路径调用临时 secret 清理；重试重新入队时不清理
- [x] 8.4 补充单元测试覆盖成功、失败、取消、重试路径
- [x] 8.5 运行 `mvn test`、相关 E2E、真实预检和 `openspec validate`
