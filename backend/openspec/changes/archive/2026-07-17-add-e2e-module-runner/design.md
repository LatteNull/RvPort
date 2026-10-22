## Context

当前 E2E runner 使用 `CASES` 数组硬编码串行执行全部 case：

```text
001-auth-users
002-project-source-environment
003-task-sse
004-sbom-analysis
```

这使得认证、用户、邮箱配置等轻量改动也必须被环境、任务、SBOM case 的耗时和外部状态影响。近期新增用户邀请和邮箱配置时，实际只需要验证 `001-auth-users`，但现有 runner 没有单独运行模块的正式入口，只能临时编写 Node 调用。

## Goals / Non-Goals

**Goals:**

- 支持按模块、按 case、按 tag 运行 E2E。
- 保留当前全量运行能力。
- 任意模块单独运行时，都具备完整 setup、管理员登录、临时状态恢复、清理和必要 post assertion。
- 通过 `list` 命令暴露可运行模块、case 和 tag。
- 文档说明模块化运行方式和新增 API 时的推荐验证路径。

**Non-Goals:**

- 不重写 E2E 为 Jest、Playwright 或其他测试框架。
- 不新增 npm 依赖。
- 不改变后端业务 API、数据库 schema 或生产配置。
- 不把长耗时真实 SBOM 验证并入默认轻量模块运行。

## Decisions

### 1. 使用 case metadata 驱动选择运行

每个 case 导出稳定 metadata：

```js
module.exports = {
  id: "001-auth-users",
  module: "auth",
  tags: ["smoke", "auth", "users", "mail"],
  postAssertions: ["redis"],
  run
};
```

选择这个方案而不是继续维护多个硬编码数组，是因为 metadata 和 case 文件同处一处，新增 case 时不需要同步修改多个列表。runner 只需要从注册表读取 case path 并加载 metadata。

备选方案是按目录拆分模块，例如 `e2e/cases/auth/*.js`。该方案更适合 case 数量明显增长后再做，目前会造成文件移动和历史 diff 变大。

### 2. runner 提供统一选择参数

推荐命令：

```bash
node e2e/runner.js list
node e2e/runner.js run --all
node e2e/runner.js run --module=auth
node e2e/runner.js run --case=001-auth-users
node e2e/runner.js run --tag=smoke
```

默认 `node e2e/runner.js run` 继续等价于全量运行，避免破坏已有使用习惯。`--all` 作为显式全量入口，方便文档和 CI 表达。

### 3. 单模块运行仍由 runner 做公共 setup

runner 统一负责：

```text
load config
check infrastructure and backend
create shared clients
admin login
temporarily clear admin must_change_password
run selected cases
run selected post assertions
cleanup selected run id data
restore admin must_change_password
```

这样 `002`、`003`、`004` 单独运行时不会隐式依赖先跑 `001` 完成登录。

### 4. post-run assertions 按 case 需要启用

现有 `postRunAssertions` 同时检查 Redis 和 RabbitMQ。auth/mail 模块不一定会创建任务或触碰 RabbitMQ，因此全局强制检查队列 payload 容易产生无关失败。

改为按选中 case 的 `postAssertions` 聚合：

```text
redis: 检查 session key 和 secret 泄漏
rabbit: 检查任务队列可查询和 payload 脱敏
```

全量运行默认包含两者；轻量模块只启用必要检查。

### 5. 清理逻辑继续基于 runId 和 registry

模块化运行不引入新的清理机制。每次运行仍生成独立 runId，并由 `CleanupRegistry` 记录创建的项目、用户、文件和队列。失败和成功路径都复用现有 cleanup。

## Risks / Trade-offs

- [Risk] case metadata 与实际行为不一致，导致模块选择遗漏依赖。  
  Mitigation: `list` 输出 metadata，新增 case 的任务要求必须包含 metadata；文档说明 tag/module 命名规则。

- [Risk] 单独运行某个 case 暴露该 case 对前置 case 的隐式依赖。  
  Mitigation: 将管理员登录、CSRF、基础设施检查、`must_change_password` 临时处理放在 runner 公共 setup 中。

- [Risk] `--tag=smoke` 语义后续膨胀，变得不稳定。  
  Mitigation: 文档定义 tag 为人工维护的稳定分类；CI 或快速验证应优先使用明确 `--module` 或 `--case`。

- [Risk] 全量运行默认行为改变导致现有脚本不兼容。  
  Mitigation: `node e2e/runner.js run` 继续运行全部 case，新增参数只扩展能力。
