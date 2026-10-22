## 1. Runner 选择模型

- [x] 1.1 为 E2E case 定义统一 metadata 结构，包括 `id`、`module`、`tags`、`description` 和 `postAssertions`。
- [x] 1.2 在 `e2e/runner.js` 中建立 case 注册表，替代只用于全量串行执行的硬编码 `CASES` 数组。
- [x] 1.3 实现 `list` 命令，输出可用模块、case、tag 和简要说明。
- [x] 1.4 扩展参数解析，支持 `--all`、`--module=<name>`、`--case=<id>`、`--tag=<tag>`。

## 2. 模块化运行行为

- [x] 2.1 实现 case 选择逻辑，确保 `--module`、`--case`、`--tag` 只运行匹配 case。
- [x] 2.2 保持 `node e2e/runner.js run` 默认运行全部 case，兼容现有用法。
- [x] 2.3 对不存在的 module、case 或 tag 返回失败状态，并输出可用值提示。
- [x] 2.4 保留 `--run-id`、`--skip-cleanup`、`--require-real` 等现有参数行为。

## 3. 公共 setup、清理和断言

- [x] 3.1 确保任意单模块运行都会执行基础设施检查、后端健康检查、Redis PING、管理员登录和 CSRF 初始化。
- [x] 3.2 确保任意单模块运行都会临时处理并最终恢复管理员 `must_change_password` 状态。
- [x] 3.3 确保任意单模块运行都会创建独立 run id 和 cleanup registry，并在成功或失败后按现有策略清理。
- [x] 3.4 将 post-run assertion 改为根据选中 case 的 `postAssertions` 聚合执行。
- [x] 3.5 确保 auth/mail 等轻量模块不会因为 RabbitMQ 历史消息或无关队列状态失败。

## 4. Case metadata 迁移

- [x] 4.1 为 `001-auth-users.js` 增加 `auth` module、相关 tags 和 Redis post assertion metadata。
- [x] 4.2 为 `002-project-source-environment.js` 增加 `project` module、相关 tags 和 RabbitMQ post assertion metadata。
- [x] 4.3 为 `003-task-sse.js` 增加 `task` module、相关 tags 和 RabbitMQ post assertion metadata。
- [x] 4.4 为 `004-sbom-analysis.js` 增加 `sbom` module、相关 tags 和 RabbitMQ post assertion metadata。

## 5. 验证

- [x] 5.1 运行 `node e2e/runner.js list`，确认模块、case 和 tag 输出正确。
- [x] 5.2 运行 `node e2e/runner.js run --module=auth`，确认只执行认证/用户/邮箱相关 case 并完成清理。
- [x] 5.3 运行 `node e2e/runner.js run --case=003-task-sse`，确认单 case 不依赖先执行 `001-auth-users`。
- [x] 5.4 运行不存在 module/case/tag 的负向命令，确认返回非零状态和可读错误。
- [x] 5.5 运行 `mvn test`，确认后端单元测试不受 E2E runner 修改影响。

## 6. 文档

- [x] 6.1 更新 `e2e/README.md`，说明 `list`、`--all`、`--module`、`--case`、`--tag` 的用法。
- [x] 6.2 更新 `docs/api-e2e-coverage.md`，说明模块化运行策略和新增 API 时的推荐验证方式。
- [x] 6.3 在文档中明确新增 E2E case 必须提供 metadata，并说明 `module` 和 `tag` 命名约定。
- [x] 6.4 运行 OpenSpec 状态检查，确认 proposal、design、specs、tasks 均完整。
