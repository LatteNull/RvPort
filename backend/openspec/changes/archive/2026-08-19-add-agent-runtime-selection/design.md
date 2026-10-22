## Context

当前后端测试结果比较运行时通过 `TestComparisonAgentRuntime` 直接构造 `codex exec` 命令，模型 profile 中也保存了 `executablePath`。这导致两个概念被绑定在一起：

- 模型连接参数：`baseUrl`、`model`、`wireApi`、`apiKey`、超时。
- Agent 执行器参数：agent 类型、可执行文件路径、命令参数、workspace 约定、输出解析方式。

实际测试中已经出现同一 OpenAI-compatible 平台上不同模型对 Codex agent 支持不一致的问题。后续还需要接入 DeepSeek Harness 和其他开源 agent，因此必须把模型 profile 和 agent runtime 拆开，并让阶段绑定同时选择模型与 agent。

本 change 只处理 `TEST_LOG_COMPARE` 阶段。测试结果比较仍然是自动化测试完成后的自动后续步骤，不新增手动业务比较入口。

## Goals / Non-Goals

**Goals:**

- 支持 `CODEX`、`DEEPSEEK_HARNESS` 和 `OPENCODE` 三类 agent runtime。
- 提供 agent runtime 列表/详情展示能力，供前端选择。
- 将 `TEST_LOG_COMPARE` 阶段绑定扩展为 `modelProfileId + agentRuntimeId`。
- 将 Codex 专用执行逻辑抽象为通用 agent adapter。
- 模型 profile 测试时可指定 agent runtime，并保存该 agent 的分项 probe 结果。
- 测试比较 runtime 使用统一 agent 输出对象，其中 `mergedOutput` 是按真实产生顺序合并 stdout/stderr 并保留流标签的输出。
- 后端容器提供 Codex、DeepSeek Harness、OpenCode 的安装或可执行路径配置，并能报告不可用状态。

**Non-Goals:**

- 不新增除 `TEST_LOG_COMPARE` 之外的阶段绑定。
- 不提供任意 prompt 执行 API。
- 不把 agent 配置开放给普通用户。
- 不在本 change 中实现前端页面。
- 不承诺所有第三方模型都能通过所有 agent 探测；探测结果是配置可用性的事实来源。

## Decisions

### 拆分 agent runtime 和 model profile

新增 `agent_runtimes` 表，保存 agent 类型、名称、可执行路径、默认参数、启用状态和最近探测摘要。`model_profiles` 继续只表达模型连接参数。`model_stage_assignments` 增加 `agent_runtime_id`。

替代方案是在 `model_profiles` 上增加 `agentType`。该方案改动小，但会导致同一模型为了不同 agent 重复配置多份 profile，也会让模型列表承担 agent 管理职责，不利于后续扩展。

### 使用 agent adapter 层统一运行

新增通用接口，例如：

```text
AgentRuntimeAdapter
  supports(agentType)
  run(config, workspace, prompt, timeout)
  probe(...)
```

实现类：

- `CodexAgentRuntimeAdapter`
- `DeepSeekHarnessAgentRuntimeAdapter`
- `OpenCodeAgentRuntimeAdapter`

测试比较 runtime 只依赖统一接口，不再直接拼接 Codex 命令。

### 统一输出字段使用 mergedOutput

统一 agent 进程输出对象保留：

- `stdout`：stdout 完整内容。
- `stderr`：stderr 完整内容。
- `mergedOutput`：按真实产生顺序交织合并 stdout/stderr，并使用 `[STDOUT]`、`[STDERR]` 或等效流标签标记来源。
- `exitCode`
- `timedOut`

测试比较失败摘要、agent 输出 artifact 和调试信息优先使用 `mergedOutput`，因为简单拼接 stdout/stderr 会丢失错误发生的上下文顺序。

### 阶段绑定同时保存模型和 agent

`TEST_LOG_COMPARE` 运行时解析阶段绑定时必须同时得到：

- 已启用的 `model_profiles`。
- 已启用的 `agent_runtimes`。

缺少任意一侧时，自动比较标记为不可用，不影响自动化测试结果本身。

### DeepSeek Harness 和 OpenCode 的接入边界

DeepSeek Harness 作为用户指定的新增开源 agent 接入。OpenCode 作为第二个开源 agent 接入，原因是它是开源终端 agent，并且支持 OpenAI-compatible provider，更符合当前模型 profile 能力。

初始实现只要求三类 agent 能完成统一 probe 和测试比较 prompt。每个 adapter 的具体命令参数由实现根据实际 CLI 版本确定；命令行、API key、完整 prompt 和服务器路径不得通过 API 返回。

### Docker 镜像中的 agent 安装

后端 Docker 镜像默认安装 Node.js 22，并通过 npm 安装三类 agent CLI：

- Codex CLI：默认版本由 `CODEX_CLI_VERSION` 控制，默认可执行入口为 `codex`。
- DeepSeek Harness：默认版本由 `DEEPSEEK_HARNESS_VERSION` 控制，默认可执行入口为 `dsh`。
- OpenCode：默认版本由 `OPENCODE_VERSION` 控制，默认可执行入口为 `opencode`。

构建参数通过根目录 `.env` 和 `docker-compose.yml` 暴露，包含 `NODE_VERSION`、`NODE_DISTRO`、`NODEJS_MIRROR`、`NPM_REGISTRY` 以及三类 agent 版本。运行时可执行入口通过 `RVPORT_AGENT_CODEX_EXECUTABLE`、`RVPORT_AGENT_DEEPSEEK_HARNESS_EXECUTABLE`、`RVPORT_AGENT_OPENCODE_EXECUTABLE` 覆盖。

Dockerfile 使用 BuildKit cache 挂载 Maven 本地仓库和 npm 缓存，避免每次重新构建容器都完整拉取 Maven/npm 依赖；只有版本、锁定参数或缓存失效时才需要重新下载。

### 当前真实探测结果边界

实现完成后应把安装成功和模型兼容性区分开：

- CLI 安装验证只说明容器内存在可执行文件且能返回版本。
- 模型 profile probe 才是某个 agent + 某个模型是否可用于测试比较的事实来源。

当前真实验证中，DeepSeek Harness 和 OpenCode 都可以通过基础文本、agent 文本、workspace/tool 闭环和测试比较 schema probe。OpenCode 使用 `provider` 单数配置、`@ai-sdk/openai-compatible` provider 包、`RVPORT_AGENT_API_KEY` 环境变量注入密钥，并在 `opencode run` 时启用 `--auto` 以允许 workspace/tool 闭环自动执行。后续如果某个模型或 provider 再次失败，应通过模型 profile probe 的兼容性状态暴露给前端，而不是仅凭 CLI 已安装就认为可用。

### 兼容迁移

迁移时内置或初始化默认 Codex agent runtime：

- `agent_type=CODEX`
- `name=Codex`
- `executable_path` 优先使用现有 model profile 的 `executable_path`，无历史值则使用 `codex`

已有 `TEST_LOG_COMPARE` 阶段绑定如果存在，只补齐 `agent_runtime_id=Codex runtime id`。后续 `model_profiles.executable_path` 不再作为运行时事实来源，可以保留一段时间用于兼容展示，或者通过后续 change 移除。

## Risks / Trade-offs

- [Risk] DeepSeek Harness 或 OpenCode CLI 参数随版本变化。  
  Mitigation: 每个 adapter 单独封装命令构造，并通过 agent runtime probe 暴露不可用原因。

- [Risk] 不同 agent 的工具闭环能力差异大。  
  Mitigation: 分项 probe 保留 `BASIC_TEXT`、`AGENT_TEXT`、`AGENT_WORKSPACE_TOOL`、`TEST_COMPARE_SCHEMA`，阶段绑定只代表选择，不代表一定可用；运行前仍检查最近兼容性或执行最小检查。

- [Risk] 合并 stdout/stderr 需要避免阻塞读取。  
  Mitigation: 进程 runner 使用并发读取 stdout/stderr，并以时间顺序写入线程安全 buffer，生成 `mergedOutput`。

- [Risk] 历史模型 profile 中的 `executablePath` 语义混乱。  
  Mitigation: 迁移时只用于初始化 Codex runtime，后续 API 文档将 agent executable 放到 agent runtime 展示里。

- [Risk] agent 输出可能包含密钥、内部路径或完整输入。  
  Mitigation: 所有 API 错误摘要和响应必须脱敏；完整 agent 输出仅作为受控 artifact 保存和下载，且不得包含 API key。

## Migration Plan

1. 新增 Liquibase 迁移创建 `agent_runtimes`，并为 `model_stage_assignments` 增加 `agent_runtime_id`。
2. 插入或 upsert 三条默认 runtime：`CODEX`、`DEEPSEEK_HARNESS`、`OPENCODE`。
3. 将已有 `TEST_LOG_COMPARE` 绑定补齐到 Codex runtime。
4. 重新生成 jOOQ 代码。
5. 实现 agent adapter registry 和三类 adapter。
6. 更新模型 profile 测试、阶段绑定、测试比较 runtime 和 API 响应。
7. 更新 Dockerfile/.env.example/文档，使容器具备对应 agent 可执行入口或明确不可用状态。
8. 补充单元测试和 E2E，覆盖正常流程、异常流程和 edge case。

Rollback 策略：如需要回滚，可通过后续 Liquibase changeset 禁用新增 agent runtime，并将 `TEST_LOG_COMPARE` 绑定恢复为 Codex；应用代码回滚到只读取模型 profile 的版本前，需要确保数据库允许 `agent_runtime_id` nullable 或先清理新绑定逻辑。

## Open Questions

- 是否在运行测试比较前强制要求最近一次 agent probe 成功，还是仅在配置不完整时阻断，实际 agent 失败由任务失败体现。
