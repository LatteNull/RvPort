## 1. 结构化输出提取

- [x] 1.1 将 Agent Probe 的机器结果来源调整为优先 stdout、清洗后的 merged output 回退，并保留原始诊断输出用于失败消息
- [x] 1.2 实现 ANSI 控制序列和通道标签的边界清洗，确保不改写 JSON 字符串中的普通内容
- [x] 1.3 实现支持日志前后缀、Markdown fence、多行内容、字符串转义和嵌套对象的 JSON 候选提取
- [x] 1.4 按输出顺序从后向前选择最后一个满足当前 probe 全部预期字段的对象，并保持超时、非零退出码优先失败
- [x] 1.5 将 workspace write 响应接入统一提取逻辑，并继续校验结果文件、JSON 对象和 marker

## 2. 单元测试

- [x] 2.1 补充 Codex、DeepSeek Harness 和 OpenCode 正常输出测试，覆盖独立 stdout、merged 标签、ANSI 状态日志与 workspace 读写
- [x] 2.2 补充日志前后缀、Markdown fence、多行 JSON、多个候选、嵌套对象和字符串内花括号等 edge case
- [x] 2.3 补充空输出、截断 JSON、字段缺失或不匹配、错误候选在末尾、输出文件缺失或 marker 不匹配等异常测试
- [x] 2.4 验证超时和非零退出码不会因有效 JSON 被覆盖，并验证 API key、Authorization 和路径诊断继续脱敏

## 3. API E2E 与真实运行时验证

- [x] 3.1 扩展模型管理 E2E 模块，使用可控进程 fixture 产生真实 stdout、stderr、ANSI、通道交织和 workspace 文件
- [x] 3.2 通过 Agent Probe Run API 验证 DeepSeek Harness 风格和 OpenCode 风格的三个通用检查均能正确返回成功
- [x] 3.3 验证无效输出返回稳定错误码、持久化结果与 API 响应均不泄露密钥，且单 Agent 失败不影响同一 run 的其他 Agent 结果
- [x] 3.4 重建后端 API 与 Worker 容器，使用已配置的 Codex、DeepSeek Harness、OpenCode runtime 执行真实兼容性复测并记录结果

## 4. 质量验收

- [x] 4.1 运行受影响模块单元测试，确认正常、异常与 edge case 全部通过且不依赖外部服务
- [x] 4.2 运行完整 Maven 单元测试与 JaCoCo 检查，确认项目整体及受影响模块行覆盖率和分支覆盖率均不低于 90%
- [x] 4.3 运行 `openspec validate --change fix-agent-probe-structured-output-parsing` 并记录测试命令、结果、覆盖率范围和报告位置

## 验证记录

- 受影响单元测试：`mvn -q -Dtest=CodexProviderProbeServiceTests test`，16 条测试全部通过，无外部服务依赖。
- 受影响范围覆盖率：`mvn -q clean "-Dtest=cn.rvport.backend.codexprovider.*Tests" test jacoco:report`；`codexprovider` 包行覆盖率 96.30%、分支覆盖率 91.57%，`CodexProviderProbeService` 行覆盖率 97.68%、分支覆盖率 94.35%。
- API E2E：`node runner.js run --module=model-profile`，run `e2e_20260914_123952_9fb68d70` 通过并完成测试数据清理。
- 真实运行时：使用已配置的 `GLM-5.2` Profile 执行 run `b0f6fd9f-62a4-44bc-a644-44a2a0dc14d7`，Codex、DeepSeek Harness、OpenCode 的三个通用检查全部成功。
- 容器：`docker compose build backend` 与 `docker compose up -d --force-recreate backend backend-worker` 成功，API 容器健康。
- 完整验证：修正 `TaskWorkerServiceTests.sanitizesMailAndWorkerMessagesAtBoundary` 的重载反射调用歧义后，`mvn -B clean verify` 成功；共运行 1534 条测试，0 失败、0 错误、2 跳过。整体行覆盖率 96.92%、分支覆盖率 91.04%，受影响 `codexprovider` 包行覆盖率 96.30%、分支覆盖率 91.57%，均达到 90% 门槛。
- 覆盖率报告：`target/site/jacoco/index.html`；OpenSpec 严格校验命令：`openspec validate fix-agent-probe-structured-output-parsing --type change --strict --no-interactive`。
