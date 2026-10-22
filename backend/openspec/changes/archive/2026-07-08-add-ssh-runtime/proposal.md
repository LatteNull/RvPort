## Why

环境管理 API 已经能创建 SSH 环境和连接测试任务，但 worker 还不能真实建立 SSH 连接，环境状态也无法被实际验证。现在任务执行上下文已经具备进度、日志和失败摘要能力，适合先补齐 SSH runtime，让后续源码同步、环境采集和远程脚本执行有可靠基础。

## What Changes

- 新增 SSH runtime / Env Runner 基础服务，用于按环境配置建立 SSH 连接并执行受控远程命令。
- 支持 SSH 密码凭据、SSH 私钥凭据和可选 passphrase，运行时从 `credentials.encrypted_payload` 解密使用。
- 支持直连和一层跳板机连接，继续拒绝多级跳板链路。
- 实现 `ENV_TEST_CONNECTION` 任务 handler，通过任务执行上下文写入进度、日志摘要和安全失败信息。
- 连接测试成功时更新环境连接状态并写入 `tool_runs` 执行记录，失败时写入安全错误摘要，不在日志、事件或响应中暴露明文凭据。
- 统一 `ENV_TEST_CONNECTION`、`ENV_COLLECT`、`ENV_RUN_SCRIPT` 的远程执行记录、日志和结构化结果保存语义，避免连接测试、环境采集和脚本执行记录互相污染。
- 明确前端触发环境运行类型的 API 合约：连接测试、环境检查、环境采集和脚本执行都必须通过明确接口创建任务。
- 增加 SSH runtime 的单元测试和可选手动连通性验证说明，覆盖正常流程、异常流程和 edge case。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `project-source-environment`: 环境连接测试任务从“只创建并投递任务”扩展为 worker 真实执行 SSH 连通性验证，并规范 SSH 凭据运行时解密、跳板机连接、安全日志、执行记录、环境采集快照和环境状态更新。

## Impact

- 影响环境任务 worker handler、凭据读取/解密能力、环境状态更新、执行记录和任务日志。
- 新增 Apache MINA SSHD 客户端依赖，用于密码登录、私钥登录和一层跳板机连接。
- 不修改数据库 schema；复用现有 `environments`、`credentials`、`tasks`、`task_events`、`task_logs`、`tool_runs`、`environment_snapshots` 和 `environment_components` 表。
- 不实现 Git clone、源码同步、构建命令或测试命令；这些后续 change 复用 SSH runtime。
