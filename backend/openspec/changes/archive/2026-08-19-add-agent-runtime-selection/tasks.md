## 1. 数据库和生成代码

- [x] 1.1 新增 Liquibase changeset，创建 `agent_runtimes` 表，包含 agent 类型、名称、启用状态、可执行路径、默认参数、配置、最近探测结果和审计时间字段。
- [x] 1.2 在 `model_stage_assignments` 中增加 `agent_runtime_id` 外键，并保留 `stage` 唯一约束。
- [x] 1.3 初始化或 upsert `CODEX`、`DEEPSEEK_HARNESS`、`OPENCODE` 默认 agent runtime，初始化过程必须可重复执行。
- [x] 1.4 迁移已有 `TEST_LOG_COMPARE` 阶段绑定，使其默认关联 Codex runtime。
- [x] 1.5 确认 `model_profiles.executable_path` 不再作为运行时事实来源；必要时只用于兼容读取或初始化 Codex runtime。
- [x] 1.6 运行 Liquibase 并检查 PostgreSQL 中新表、外键、唯一约束和默认 runtime 数据。
- [x] 1.7 运行 jOOQ 生成脚本并确认生成代码纳入 `src/main/java`。

## 2. Agent Runtime 核心抽象

- [x] 2.1 新增 agent runtime 领域对象、枚举和 repository，支持查询、启用状态过滤和最近探测结果更新。
- [x] 2.2 新增统一 `AgentRuntimeAdapter` 接口和 adapter registry，按 agent 类型选择实现。
- [x] 2.3 重构现有 `CodexProcessRunner` 或新增通用进程 runner，使执行结果包含 `stdout`、`stderr`、`mergedOutput`、`exitCode` 和 `timedOut`。
- [x] 2.4 确保 `mergedOutput` 按真实产生顺序合并 stdout/stderr，并保留流来源标签。
- [x] 2.5 为进程输出读取增加脱敏处理，避免 API key、授权头、完整 prompt 和服务器敏感路径出现在错误摘要中。

## 3. Agent Adapter 实现

- [x] 3.1 将现有 Codex 命令构造迁移到 `CodexAgentRuntimeAdapter`。
- [x] 3.2 新增 `DeepSeekHarnessAgentRuntimeAdapter`，使用受控 workspace、模型 profile 和 runtime 配置构造命令。
- [x] 3.3 新增 `OpenCodeAgentRuntimeAdapter`，使用受控 workspace、模型 profile 和 runtime 配置构造命令。
- [x] 3.4 每个 adapter 必须实现基础文本、workspace/tool 闭环和测试比较 schema probe。
- [x] 3.5 每个 adapter 失败时必须返回受控错误，禁止执行任意客户端提交命令。

## 4. 模型管理和阶段绑定 API

- [x] 4.1 新增 `GET /api/admin/agent-runtimes` 和 `GET /api/admin/agent-runtimes/{runtimeId}`。
- [x] 4.2 扩展阶段绑定请求和响应，使 `TEST_LOG_COMPARE` 同时返回和保存 `modelProfile` 与 `agentRuntime`。
- [x] 4.3 扩展模型 profile 测试 API，支持请求指定 `agentRuntimeId`。
- [x] 4.4 模型测试结果保存 agent 类型、agent runtime ID、分项 probe 和聚合兼容性状态。
- [x] 4.5 更新模型 profile 列表和详情响应，确保不返回 API key、完整 agent 命令、完整 prompt 或服务器真实敏感路径。
- [x] 4.6 普通用户访问 agent runtime、模型 profile 和阶段绑定接口必须返回无权限错误。

## 5. 测试结果比较运行时

- [x] 5.1 重构 `TestComparisonAgentRuntime`，通过 `TEST_LOG_COMPARE` 阶段绑定解析模型 profile 和 agent runtime。
- [x] 5.2 测试比较运行时通过 agent adapter registry 执行，不再直接拼接 Codex 命令。
- [x] 5.3 阶段未绑定模型、未绑定 agent、绑定对象禁用或配置不完整时，自动比较标记为不可用或受控失败，不影响自动化测试结果查询。
- [x] 5.4 原始 agent 输出 artifact 保存 `stdout`、`stderr`、`mergedOutput`、`exitCode` 和 `timedOut` 的结构化内容。
- [x] 5.5 比较详情返回使用的 agent 类型或 runtime 摘要，且不暴露完整命令、完整 prompt、API key 或服务器真实路径。
- [x] 5.6 测试比较成功生成报告或摘要后，按全局约束登记归档候选。

## 6. Docker 和环境配置

- [x] 6.1 更新后端 Dockerfile，安装或预留 Codex CLI 可执行入口。
- [x] 6.2 更新后端 Dockerfile，安装或预留 DeepSeek Harness 可执行入口。
- [x] 6.3 更新后端 Dockerfile，安装或预留 OpenCode 可执行入口。
- [x] 6.4 增加 `.env.example` 中 agent runtime 可执行路径覆盖变量。
- [x] 6.5 确保某个非默认 agent 缺失不会导致后端容器启动失败，只在探测或运行时返回不可用状态。
- [x] 6.6 确认 agent 安装层不破坏现有 Maven 依赖缓存策略。

## 7. 文档和 OpenSpec 同步

- [x] 7.1 更新 `docs/API_DESIGN.md`，补充 agent runtime API、阶段绑定和模型测试响应。
- [x] 7.2 更新 `docs/DATABASE_DESIGN.md`，补充 `agent_runtimes` 和阶段绑定外键。
- [x] 7.3 更新 `docs/INFRASTRUCTURE.md` 或 README 中后端容器 agent runtime 说明。
- [x] 7.4 更新 `docs/api-e2e-coverage.md`，记录 agent runtime 相关 E2E 模块或 case。

## 8. 测试和验证

- [x] 8.1 增加数据库迁移测试，覆盖 `agent_runtimes` 初始化、唯一约束、阶段绑定外键和历史 Codex 绑定迁移。
- [x] 8.2 增加 repository/service 单元测试，覆盖 agent runtime 查询、禁用状态、阶段绑定解析和异常流程。
- [x] 8.3 增加进程 runner 单元测试，覆盖 stdout/stderr 交织输出生成 `mergedOutput` 的正常流程、异常流程和 edge case。
- [x] 8.4 增加 adapter 单元测试，覆盖 Codex、DeepSeek Harness、OpenCode 的命令构造、脱敏和不可用路径。
- [x] 8.5 增加模型 profile 测试 API 单元测试和必要 MVC 测试，覆盖指定 agent runtime、无权限、配置不完整和 agent 不存在。
- [x] 8.6 增加测试比较 runtime 测试，覆盖使用阶段绑定 agent、未绑定 agent、agent 输出不可解析和 `mergedOutput` artifact 保存。
- [x] 8.7 增加 E2E case，覆盖 agent runtime 列表、阶段绑定、模型测试响应和测试比较运行时解析。
- [x] 8.8 运行 `mvn test`，并记录结果。
- [x] 8.9 在 Docker 容器中构建并启动后端，验证 agent runtime 列表和配置 API。
- [x] 8.10 如本地具备可用模型配置，至少用 Codex runtime 跑一次真实模型 probe；DeepSeek Harness 和 OpenCode 根据 CLI 安装状态返回成功或明确不可用。
- [x] 8.11 运行相关 E2E 模块，确认测试数据清理不留下脏数据。
- [x] 8.12 运行 `openspec validate add-agent-runtime-selection --strict`。
