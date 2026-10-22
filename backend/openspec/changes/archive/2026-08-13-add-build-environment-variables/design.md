## Context

构建验证是自动化测试之前的节点，用户需要在 x86 和 RISC-V 环境上用指定命令或脚本验证源码能否构建。当前 `dev` 分支已有 `buildvalidation` API、运行记录和 worker handler，主 spec 与 `docs/API_DESIGN.md` 已声明 `POST /api/projects/{projectId}/builds` 支持 `environmentVariables`，但构建验证代码侧缺少输入校验、worker 注入和脱敏闭环。

本 change 的重点是补齐构建任务的任务级环境变量闭环：API 接收、输入校验、任务快照保存、worker 执行注入、日志/事件/审计脱敏和测试覆盖。

## Goals / Non-Goals

**Goals:**
- 构建创建 API 支持可选 `environmentVariables`。
- 构建任务输入快照保留运行所需变量值，同时所有对外摘要只展示脱敏值。
- 构建 worker 在远程执行命令或临时脚本时注入这些变量。
- 构建环境变量只作用于当前任务，不污染环境配置、凭据表或系统配置。
- 补充单元测试和独立 API E2E，覆盖正常流程、异常流程和 edge case。

**Non-Goals:**
- 不实现测试日志比较 agent。
- 不解析结构化构建日志或构建报告。
- 不新增全局构建环境配置中心。
- 不改变环境配置中已有 SSH、工作目录和跳板机行为。

## Decisions

### 1. 复用自动化测试的环境变量输入模型

构建请求使用 `environmentVariables: Record<string,string>`，与自动化测试保持一致。变量名使用白名单正则校验，变量值限制最大长度和总数量。服务层负责生成两份结构：

- worker 输入使用真实变量值。
- API 响应、任务事件、任务输入摘要和审计使用脱敏变量值。

理由：构建和测试脚本都可能依赖 `CC`、`CFLAGS`、`PATH`、`LD_LIBRARY_PATH`、`PKG_CONFIG_PATH`、`MAKEFLAGS` 等变量，统一模型能减少前端和运行时分歧。

### 2. 任务输入快照中保存运行所需变量，但对外读取必须脱敏

`tasks.input_snapshot` 是 worker 事实输入来源。构建环境变量需要保存在任务输入快照中，否则异步 worker 无法可靠执行。任何返回给前端或写入日志、SSE、审计的内容必须从脱敏摘要生成，不能直接序列化完整 input snapshot。

敏感变量识别规则沿用自动化测试：名称包含 `TOKEN`、`PASSWORD`、`SECRET`、`KEY` 或 `PASS` 的变量必须脱敏；为了简单一致，所有环境变量值在对外摘要中都可以统一显示为遮蔽值或仅显示名称。

### 3. 远程执行时由 SSH runtime 注入环境变量

构建 handler 在调用远程命令或临时脚本执行前，将 `environmentVariables` 传给 SSH runtime。远端执行应优先复用已有临时脚本上传/执行机制，避免复杂 shell quoting；变量注入在脚本执行命令前完成。

如果底层 SSH runtime 当前只支持命令字符串，本 change 应补一个受控 helper，将变量安全地渲染为 shell `export` 前缀或临时 env 文件，并确保值中空格、双引号、单引号、换行等特殊字符不会破坏脚本。

### 4. 不把环境变量写入正式配置

构建任务级变量是一次性运行参数，不进入：

- `environments`
- `credentials`
- `system_configs`
- 邮件或 Codex provider 配置

理由：这些变量通常是用户为一次构建临时传入的编译参数或路径覆盖，持久化到正式配置会造成后续任务污染和敏感信息留存扩大。

### 5. E2E 使用可审计变量验证注入结果

E2E 应创建或复用测试项目、源码版本和 SSH 环境，提交一个构建任务，命令中读取一个非敏感变量，例如 `RVPORT_BUILD_FLAG`，并让构建 stdout 明确输出该值。测试完成后校验：

- 构建成功。
- stdout 或日志文件中能看到远程命令确实读取到变量。
- API 响应、任务事件和构建详情不返回变量明文。
- 清理测试产生的业务数据和远端临时目录。

## Risks / Trade-offs

- [Risk] 变量值通过 shell quoting 泄漏或破坏命令 → 优先使用临时脚本/环境文件机制，必要时增加专门的 shell escaping 单元测试。
- [Risk] input snapshot 保存真实变量值扩大敏感数据面 → 仅作为 worker 内部输入读取，对外 DTO、事件、审计全部使用脱敏摘要；后续如变量含高敏 secret，可迁移到任务级 secret payload。
- [Risk] 用户传入超大变量集合导致任务记录膨胀 → 限制变量数量、单值长度和总大小。
- [Risk] 构建环境变量需要贯穿 API、repository、handler 多处 → 抽取公共环境变量校验器，复用自动化测试的规则和 SSH 注入模式，避免新增平行实现。

## Migration Plan

1. 补齐构建 API 请求 DTO、校验器和 service 创建逻辑。
2. 补齐构建运行记录和任务输入快照中的环境变量摘要。
3. 补齐构建 handler 远程执行时的变量注入。
4. 补齐构建详情、列表、任务事件和审计的脱敏输出。
5. 运行单元测试、必要的集成测试和独立 API E2E。

不需要数据库 schema 迁移，除非实现过程中发现当前构建运行表缺少必要摘要字段；即便需要，也应通过 Liquibase 新增 changeset，不能手动改库。
