## Context

后端已经具备项目、源码、SSH 环境、凭据、任务运行时、RabbitMQ worker、SSE、任务日志、tool runs 和初始 SBOM 数据表。当前缺口不是表结构，而是 SBOM 替代分析的可执行链路：环境采集还不足以表达源侧已安装组件和目标侧仓库候选，Java 后端也还没有调用独立分析器并导入结果的 runtime。

这次设计分成两个层次：

- Java 后端负责远程环境采集、项目访问守卫、任务生命周期、日志、执行记录、数据库写入和 API。
- 根目录 `tools/sbom-analyzer` 作为独立 CLI 程序负责标准化比较、替代候选匹配、风险和建议生成。

需要注意：当前 OpenSpec 规划根是 `backend`，但用户已明确要求 SBOM 分析工具位于根目录 `tools`。实现时需要把 `tools/sbom-analyzer` 作为本 change 的特别允许范围处理，或者先调整 OpenSpec edit root。

## Goals / Non-Goals

**Goals:**

- 扩展环境采集，使 x86 源侧和 RISC-V 目标侧都能提供 SBOM 分析需要的组件清单。
- 为目标侧 RISC-V 采集软件源可用包和 provides/so 能力，支持“未安装但仓库可替代”的判断。
- 新增独立 `tools/sbom-analyzer` CLI，约定输入输出 JSON、退出码和日志边界。
- 新增 `SBOM_ANALYSIS` 长任务 handler，调用分析器并把结果写入现有 SBOM 表。
- 提供 SBOM 分析创建、列表、详情、组件结果和采集详情 API。
- 复用项目访问守卫、任务运行时、SSE、任务日志和 tool runs。
- 测试覆盖正常流程、异常流程和 edge case。

**Non-Goals:**

- 不实现问题清单 API 或 `components:add-to-issues` 的落库联动。
- 不实现报告生成、复检 diff、构建、测试或源码修复建议。
- 不把 SSH 连接和远程采集放进 SBOM 分析器；远程执行仍由 Java SSH runtime 负责。
- 不引入通用 artifact 表。
- 不在本 change 中设计复杂外部软件包知识库；MVP 以环境快照中的 installed/repository inventory 为事实来源。
- 不要求自动判断所有 `.so` 的 ABI 兼容性；MVP 先输出可解释的候选和风险。

## Decisions

### 1. 分析器作为独立 CLI，而不是嵌入 Java

选择：在 `tools/sbom-analyzer` 提供独立 CLI，Java 通过进程调用。

理由：

- SBOM 比较规则、包管理器归一化、未来可能的语言生态解析更适合独立演进。
- Java 后端保持编排和持久化职责，避免业务 API 与分析算法强耦合。
- 现有项目已经有 `tools/kb-scanner` 等独立工具目录，符合仓库结构。

备选：

- 直接用 Java 实现分析。优点是部署简单；缺点是算法迭代和工具复用差。
- 分析器自己 SSH 到远端采集。优点是工具自治；缺点是凭据、安全审计、跳板机和任务日志会重复实现。

### 2. Java 负责环境采集，分析器只分析标准输入

选择：Java SSH runtime 生成 `environment_snapshots` 和 `environment_components`，SBOM 分析器只读取 Java 导出的 JSON。

理由：

- 凭据解密、跳板机、项目访问、任务日志和审计已经在 Java 后端内。
- 同一环境快照可以被多次 SBOM 分析复用，结果可追溯。
- 分析器不接触 SSH 凭据，降低安全边界。

### 3. 源侧和目标侧采集内容不同

选择：

- 源侧 x86：采集已安装包、已安装库、基础工具、独立 native/so 文件。
- 目标侧 RISC-V：采集已安装包、已安装库、基础工具、独立 native/so 文件、软件源可用包、仓库 provides/so 能力。

理由：

- x86 侧主要表达“当前应用依赖了什么”。
- RISC-V 侧不仅要知道“已经装了什么”，还要知道“目标仓库可以装什么”，否则会把可直接安装的替代包误判为不可用。

### 4. 复用现有 SBOM 表，暂不新增表

选择：优先复用 `sbom_runs`、`sbom_components`、`replacement_candidates`、`environment_components`。

字段约定：

- `environment_components.source` 使用稳定来源值：`INSTALLED_PACKAGE`、`INSTALLED_LIBRARY`、`NATIVE_FILE`、`TOOL_VERSION`、`REPOSITORY_PACKAGE`、`REPOSITORY_PROVIDE`。
- `sbom_components.environment_side` 使用 `SOURCE`、`TARGET`、`CANDIDATE`。
- `replacement_candidates.replacement_status` 使用既有枚举表达替代结论。
- 分析器原始详情、匹配证据和解析警告放入 `metadata` 或 `summary` 的 JSON 字段。

理由：

- 初始 schema 已经为 SBOM 运行、组件和候选项建模。
- MVP 不需要为了工具输入输出新增 artifact 或中间表。

### 5. SBOM 分析任务创建时引用已存在快照

选择：`POST /api/projects/{projectId}/sbom-analyses` 必须引用源环境、目标环境、源快照和目标快照；不在同一接口里隐式触发环境采集。

理由：

- 分析结果必须可复现，引用具体快照比引用“最新环境状态”更可靠。
- 环境采集本身已经是长任务，可以由前端明确触发。
- 避免一个 SBOM 任务内部串联多个远程采集任务，降低失败语义复杂度。

### 6. 通过任务和 SSE 表达分析进度

选择：SBOM 创建接口返回 `taskId`，worker 通过任务执行上下文写入进度、日志和终态事件；前端通过项目级 SSE 观察状态。

理由：

- 与 Git 同步、环境采集、SSH 脚本的运行方式一致。
- SSE 已经支持项目访问守卫和断线恢复。

### 7. 分析器 JSON 契约稳定

输入结构应包含：

- `schemaVersion`
- `project`
- `run`
- `sourceEnvironment` 与 `targetEnvironment`
- `sourceSnapshot` 与 `targetSnapshot`
- `sourceComponents`
- `targetInstalledComponents`
- `targetRepositoryComponents`
- `options`

输出结构应包含：

- `schemaVersion`
- `summary`
- `components`
- `replacementCandidates`
- `warnings`
- `tool`

Java 只依赖稳定字段，工具内部算法细节不得泄露到 API 契约中。

## Risks / Trade-offs

- [Risk] 根目录 `tools/sbom-analyzer` 超出当前 OpenSpec edit root → Mitigation: apply 前确认允许跨目录实施，或调整 OpenSpec 根/配置。
- [Risk] 各发行版包管理器输出差异大 → Mitigation: 采集脚本按 `packageManager` 分支处理，未识别字段进入 `metadata.parseWarnings`，不阻断基础分析。
- [Risk] 仓库 provides/so 查询成本高 → Mitigation: MVP 只在目标侧启用，设置超时、结果数量上限和日志摘要。
- [Risk] `.so` 名称匹配可能误判 ABI 兼容 → Mitigation: 结果标记 `MANUAL_CONFIRM_REQUIRED` 或较高风险，不直接给出确定性通过结论。
- [Risk] 分析器输出过大 → Mitigation: Java runtime 限制输出文件大小，超限时任务失败并保留日志入口。
- [Risk] 快照过旧导致分析结果不可信 → Mitigation: API 返回快照采集时间，前端可提示重新采集；后端不自动替换用户选择的快照。

## Migration Plan

- 本 change 默认不新增数据库表。
- 如果实现发现需要新增字段，应通过 Liquibase 单独添加迁移，并重新运行 jOOQ codegen。
- 部署时需要配置分析器路径、工作目录、超时时间和输出大小限制。
- 回滚时可禁用 SBOM API 或隐藏入口；已写入的 `sbom_runs` 和结果表作为历史事实保留。

## Open Questions

- `tools/sbom-analyzer` 的实现语言是否沿用 Python，还是使用其他运行时；MVP 建议 Python，和现有 tools 目录一致。
- 目标仓库 provides 采集在不同系统上具体使用 `apt-file`、`dnf repoquery`、`rpm -q --whatprovides` 还是降级为包名索引，需要在实现时按实际环境验证。
- API 是否保留旧设计中的 `POST /api/sbom-analyses/{analysisId}/components:add-to-issues`，本 change 建议暂不实现，仅保留未来扩展位置。
