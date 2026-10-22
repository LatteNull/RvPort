## Context

当前环境连接测试接口是 `POST /api/projects/{projectId}/environments/{environmentId}/test-connection`，服务端会先读取已存在环境，再创建 `ENV_TEST_CONNECTION` 任务。这个模型适合环境复测，但不适合新建环境表单，因为表单提交前没有 `environmentId`。

环境列表当前支持 `role`、`enabled`、分页；数据库 `environments.status` 已存在，运行时也会在连接测试或禁用时更新状态，但列表查询没有暴露 `status` 过滤。SBOM 配置页需要只拿可用环境，不能只依赖 `enabled=true`。

## Goals / Non-Goals

**Goals:**

- 支持新建环境前用表单 SSH 配置发起连接预检。
- 预检任务不提前创建 `environments` 记录，避免无效环境污染正式环境列表。
- 环境列表支持按 `status` 过滤，并继续支持现有 `role`、`enabled` 和分页。
- 保持凭据脱敏、项目权限校验、跳板机校验和任务 SSE 行为一致。
- 测试覆盖正常流程、异常流程和 edge case。

**Non-Goals:**

- 不实现前端页面变更。
- 不移除已创建环境的连接复测接口。
- 不改造正式凭据资产模型，不把预检临时凭据写入 `credentials`。
- 不把问题 3/4 的 latest API 纳入本 change；相关状态由全局 SSE 处理。

## Decisions

### 1. 新增项目级预检接口，不复用创建环境接口

新增 `POST /api/projects/{projectId}/environments/test-connection`，请求体使用与创建环境接近的连接字段：名称可以不需要，但 `role`、`arch`、`host`、`sshPort`、`username`、凭据、跳板机、工作目录、超时等字段需要可表达。

原因：
- 连接预检的目标是验证“这份表单配置能否连通”，不是创建业务环境事实。
- 如果为了测试先创建环境，失败后还需要清理，会引入脏数据和复杂状态。

备选方案：
- 先创建 `UNKNOWN` 环境再测试。拒绝该方案，因为无效环境会进入正式列表。

### 2. 预检任务使用任务输入承载临时目标配置

现有 `ENV_TEST_CONNECTION` worker 以 `environmentId` 读取目标环境。预检需要支持另一种输入：`target` 连接配置。worker 根据输入判断：

```text
ENV_TEST_CONNECTION
  ├─ environmentId 存在 -> 已创建环境复测
  └─ target 存在        -> 新建环境预检
```

任务输入必须只包含安全字段和受控凭据引用；不得保存明文密码、私钥、passphrase。实现规则：
- 请求中引用已有 `credentialId` 时，仅保存该正式凭据 ID。
- 请求中提交新密码或私钥时，不写入正式 `credentials`，而是生成 `temporaryCredentialPayloadId`，把凭据 payload 加密保存到 `task_secret_payloads`，并在 `tasks.input_snapshot.target` 中只保存 `temporaryCredentialPayloadId` 和 hash。

`task_secret_payloads` 是任务级临时 secret 表，绑定 `task_id`，任务清理时随任务删除。worker 处理 target 模式任务时，如果没有 `credentialId`，则使用 `temporaryCredentialPayloadId` 解密得到 SSH runtime 凭据。

任务进入终态后，worker 必须立即删除该任务关联的 `task_secret_payloads`，只保留 `tasks`、`task_events`、`task_logs` 等结果观察数据。这样前端仍可查看预检结果，但临时密码、私钥和 passphrase 不会长期留库。重试重新入队不是终态，不能删除临时 secret，否则下一次 attempt 无法继续执行。

### 3. 跳板机只允许引用已存在环境

新建目标环境本身未落库，但跳板机必须是已存在、同项目、启用、且不是多级跳板的环境。预检接口应复用现有跳板机校验规则，但无需执行“不能引用自己”，因为目标环境尚无 ID。

### 4. 预检不更新正式环境状态

预检目标不是正式 `environments` 记录，所以成功或失败都不更新 `environments.status`、`last_connected_at`、`last_collected_at`。任务状态、任务事件和任务日志仍然作为前端观察结果的事实来源。

已创建环境复测接口继续按现有逻辑更新正式环境连接状态。

### 5. 环境列表按 status 做白名单过滤

扩展 `EnvironmentListRequest` 增加 `EnvironmentStatus status`，repository 的 filter 增加 `ENVIRONMENTS.STATUS.eq(status.name())`。查询条件与 `role`、`enabled` 使用 AND 语义。

`status=AVAILABLE` 可用于 SBOM 配置页筛选当前可用环境；状态枚举仍沿用现有 `EnvironmentStatus`，不新增状态模型。

## Risks / Trade-offs

- [Risk] 临时凭据如果写入正式凭据表，会污染用户资产并长期留存。  
  Mitigation: 预检表单提交的新凭据只写入 `task_secret_payloads`，任务终态后立即删除，任务整体清理时也通过 `task_id` 级联兜底；正式 `credentials` 只在用户保存环境时写入。

- [Risk] 预检任务输入包含比普通任务更多连接配置，泄漏风险更高。  
  Mitigation: 输入 snapshot 只保存 host、port、username、jumpHostEnvironmentId、credentialId 或 temporaryCredentialPayloadId/hash 等非明文字段；日志和审计继续脱敏。

- [Risk] `AVAILABLE` 语义依赖环境状态更新准确性。  
  Mitigation: 本 change 不改变状态机，只暴露已有状态过滤；环境状态仍由连接测试和禁用逻辑维护。

- [Risk] 同一个 handler 支持两种输入形态后测试复杂度上升。  
  Mitigation: 单元测试分别覆盖 environmentId 模式和 target precheck 模式，E2E 覆盖至少一个真实预检流程。
