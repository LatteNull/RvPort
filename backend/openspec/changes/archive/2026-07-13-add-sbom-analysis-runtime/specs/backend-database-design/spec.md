## ADDED Requirements

### Requirement: SBOM 运行时必须复用现有数据库表
SBOM 分析运行时 SHALL 优先复用现有环境快照、环境组件、任务、工具执行和 SBOM 结果表，不得为 MVP 引入通用 artifact 表。

#### Scenario: 保存环境组件来源
- **WHEN** 环境采集写入 `environment_components`
- **THEN** `source` SHALL 使用稳定来源值表达组件来源
- **AND** 来源值 SHALL 至少包含 `INSTALLED_PACKAGE`、`INSTALLED_LIBRARY`、`TOOL_VERSION`、`NATIVE_FILE`、`REPOSITORY_PACKAGE` 和 `REPOSITORY_PROVIDE`

#### Scenario: 保存 SBOM 运行结果
- **WHEN** SBOM_ANALYSIS 成功完成
- **THEN** 后端 SHALL 使用 `sbom_runs` 保存运行记录
- **AND** SHALL 使用 `sbom_components` 保存组件事实
- **AND** SHALL 使用 `replacement_candidates` 保存替代候选
- **AND** SHALL 使用 `tool_runs` 和 `task_logs` 保存分析器执行记录和日志元数据

#### Scenario: 不新增 artifact 表
- **WHEN** 保存分析器输入、输出或日志
- **THEN** 后端 MUST NOT 引入通用 artifact 表
- **AND** 完整日志 SHALL 继续通过 `task_logs` 元数据和本地日志文件管理
- **AND** 可追溯摘要 SHALL 保存到 `summary` 或 `metadata` JSON 字段

### Requirement: SBOM 结果必须引用实际使用的环境快照
SBOM 运行 SHALL 明确引用源环境快照和目标环境快照，保证分析结果可复现。

#### Scenario: 创建 SBOM 运行
- **WHEN** 后端创建 `sbom_runs` 记录
- **THEN** `source_snapshot_id` SHALL 指向本次分析实际使用的源环境快照
- **AND** `target_snapshot_id` SHALL 指向本次分析实际使用的目标环境快照
- **AND** 快照所属环境和项目 SHALL 与 `sbom_runs` 的项目、源环境和目标环境一致

#### Scenario: 快照被后续采集替代
- **WHEN** 同一环境后续产生新快照
- **THEN** 已有 `sbom_runs` MUST continue 引用原始快照
- **AND** 后端 MUST NOT 自动把历史 SBOM 运行切换到新快照

### Requirement: SBOM 数据不得保存敏感信息
SBOM 相关表中的摘要和元数据 SHALL 避免保存明文凭据、私钥、token、passphrase 和服务器真实绝对路径。

#### Scenario: 写入分析器摘要
- **WHEN** 后端保存 `sbom_runs.summary`、`sbom_components.metadata` 或 `replacement_candidates.metadata`
- **THEN** 写入内容 MUST NOT 包含明文凭据
- **AND** 写入内容 MUST NOT 包含服务器真实绝对路径
- **AND** 必要路径信息 SHALL 使用文件名、远端相对摘要、哈希或遮蔽值表达

#### Scenario: 写入失败摘要
- **WHEN** SBOM_ANALYSIS 失败并保存任务错误信息或 tool run summary
- **THEN** 错误信息 MUST NOT 包含明文凭据、服务器真实绝对路径或完整分析器输入 JSON
