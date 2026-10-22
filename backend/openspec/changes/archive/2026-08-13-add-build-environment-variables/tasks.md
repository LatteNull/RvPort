## 1. 构建 API 输入

- [x] 1.1 盘点当前构建验证 API、service、repository、handler 是否已存在，确认需要新增或补齐的类。
- [x] 1.2 在构建任务创建请求 DTO 中支持可选 `environmentVariables`。
- [x] 1.3 复用或抽取环境变量校验逻辑，校验变量名、数量、单值长度和总大小。
- [x] 1.4 创建构建任务时校验项目权限、源码版本归属和执行环境归属。
- [x] 1.5 构建创建响应、构建详情和构建列表只返回脱敏环境变量摘要。

## 2. 构建任务运行时

- [x] 2.1 在构建任务 input snapshot 中保存 worker 执行所需环境变量和对外脱敏摘要。
- [x] 2.2 在构建 handler 中解析 `environmentVariables` 并传递给远程执行层。
- [x] 2.3 补齐 SSH runtime 的构建命令或临时脚本环境变量注入能力。
- [x] 2.4 验证包含空格、引号、等号和空字符串值的变量不会破坏远程脚本执行。
- [x] 2.5 构建失败、超时、取消时保持任务终态、构建运行状态和日志引用一致。

## 3. 安全和脱敏

- [x] 3.1 确保 API 响应、任务事件、SSE data、审计摘要和错误信息不暴露环境变量明文。
- [x] 3.2 确保 RabbitMQ 消息不包含环境变量明文或完整任务输入快照。
- [x] 3.3 确保任务级环境变量不写入 `environments`、`credentials` 或 `system_configs`。
- [x] 3.4 补充敏感变量名规则，覆盖 `TOKEN`、`PASSWORD`、`SECRET`、`KEY` 和 `PASS`。

## 4. 测试和验证

- [x] 4.1 补充环境变量校验和脱敏单元测试，覆盖正常流程、异常流程和 edge case。
- [x] 4.2 补充构建 service 测试，覆盖带环境变量创建、非法变量拒绝、无权限和资源归属错误。
- [x] 4.3 补充构建 handler 或 SSH runtime 测试，验证远程执行能读取任务级环境变量。
- [x] 4.4 补充独立 API E2E 模块，创建构建任务并验证环境变量输入和 API 脱敏。
- [x] 4.5 运行 `mvn test`，确认普通单元测试通过。
- [x] 4.6 在基础设施和后端可用时运行构建环境变量 E2E，并清理测试数据。
- [x] 4.7 运行 `openspec validate add-build-environment-variables --strict`。
