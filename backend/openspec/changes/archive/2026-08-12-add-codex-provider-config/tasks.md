## 1. 配置模型和持久化

- [x] 1.1 新增 Codex provider 配置请求、响应和内部配置模型，字段覆盖 `enabled`、`executablePath`、`modelProviderType`、`baseUrl`、`model`、`wireApi`、`apiKey`、`timeoutSeconds` 和 `maxRuntimeSeconds`
- [x] 1.2 新增 Codex provider 配置服务，复用 `SystemConfigService` 和 `codex-provider` namespace 保存配置
- [x] 1.3 实现 `apiKey` 可选更新语义：未传入保留、空字符串清空、非空字符串加密覆盖
- [x] 1.4 保存和读取最近一次测试状态：`lastTestStatus`、`lastTestMessage`、`lastTestedAt`

## 2. 管理 API

- [x] 2.1 实现 `GET /api/admin/configs/codex-provider` 查询配置摘要
- [x] 2.2 实现 `PATCH /api/admin/configs/codex-provider` 保存配置
- [x] 2.3 实现 `POST /api/admin/configs/codex-provider:test` 测试已保存配置或请求中的临时覆盖配置
- [x] 2.4 校验 `modelProviderType`、`wireApi`、`baseUrl`、`model`、`timeoutSeconds`、`maxRuntimeSeconds` 和 `executablePath`
- [x] 2.5 确认接口继续受 `/api/admin/configs/**` 超级管理员权限保护

## 3. Codex Provider 探测

- [x] 3.1 新增 Codex provider smoke test 服务，使用隔离临时目录运行最小非交互 Codex 调用
- [x] 3.2 调用外部进程时使用参数数组，不通过 shell 字符串拼接
- [x] 3.3 将 OpenAI-compatible base URL、模型和 API key 注入 Codex 运行配置或环境变量
- [x] 3.4 对进程超时、退出码非 0、输出格式错误和配置缺失返回受控失败
- [x] 3.5 对测试输出和错误摘要进行脱敏，禁止泄漏 API key、授权头和服务器真实敏感路径

## 4. 文档

- [x] 4.1 更新 `docs/API_DESIGN.md`，补充 Codex provider 配置 API 请求、响应、权限和错误码
- [x] 4.2 更新 `docs/DATABASE_DESIGN.md`，补充 `system_configs` 中 `codex-provider` namespace 的 key、类型和 secret 约束
- [x] 4.3 如 README 或开发计划中已有自动化测试节点说明，补充 Codex provider 只是配置基础，不包含日志比较运行时
- [x] 4.4 更新后端 Dockerfile 和 compose build arg，确保后端镜像安装 Codex CLI

## 5. 测试

- [x] 5.1 补充正常流程单元测试：超级管理员保存、查询、API key 加密保存、遮蔽返回和 provider 测试摘要保存
- [x] 5.2 补充异常流程单元测试：非超级管理员拒绝、非法 URL、非法 provider type、空模型、越界超时和配置不完整
- [x] 5.3 补充 edge case 单元测试：未传 `apiKey` 保留旧 secret、空字符串清空 secret、失败消息脱敏
- [x] 5.4 补充 API E2E 模块测试，覆盖配置保存、查询、权限拒绝和参数校验；真实 Codex smoke test 可在环境具备 Codex CLI 和第三方 API key 时显式运行
- [x] 5.5 运行 Maven 单元测试和可用的 E2E 模块测试

## 6. 验证和收尾

- [x] 6.1 运行 `openspec validate add-codex-provider-config --strict`
- [x] 6.2 确认本 change 未实现自动化测试执行、测试日志比较或任意 LLM 调用 API
