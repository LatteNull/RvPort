## ADDED Requirements

### Requirement: 环境采集必须支持 SBOM 组件清单
环境采集 SHALL 为 SBOM 分析保存可复用的组件清单，并根据环境角色区分源侧已安装清单和目标侧仓库可用清单。

#### Scenario: 采集 x86 源环境组件
- **WHEN** worker 执行 `SOURCE_X86` 环境的 `ENV_COLLECT`
- **THEN** 后端 SHALL 采集已安装软件包、已安装库、基础工具版本和独立 native/so 文件摘要
- **AND** 后端 SHALL 将组件写入 `environment_components`
- **AND** `source` SHALL 标记为 `INSTALLED_PACKAGE`、`INSTALLED_LIBRARY`、`TOOL_VERSION` 或 `NATIVE_FILE`

#### Scenario: 采集 RISC-V 目标环境已安装组件
- **WHEN** worker 执行 `TARGET_RISCV` 环境的 `ENV_COLLECT`
- **THEN** 后端 SHALL 采集已安装软件包、已安装库、基础工具版本和独立 native/so 文件摘要
- **AND** 后端 SHALL 将组件写入 `environment_components`
- **AND** `source` SHALL 标记为 `INSTALLED_PACKAGE`、`INSTALLED_LIBRARY`、`TOOL_VERSION` 或 `NATIVE_FILE`

#### Scenario: 采集 RISC-V 目标环境仓库候选
- **WHEN** worker 执行 `TARGET_RISCV` 环境的 `ENV_COLLECT`
- **THEN** 后端 SHALL 尝试采集软件源可用包和仓库 provides/so 能力
- **AND** 仓库可用包 SHALL 写入 `environment_components` 并标记 `source=REPOSITORY_PACKAGE`
- **AND** 仓库 provides/so 能力 SHALL 写入 `environment_components` 并标记 `source=REPOSITORY_PROVIDE`
- **AND** 采集失败或命令不可用时 SHALL 在快照 `raw_snapshot` 中记录解析警告

### Requirement: 环境采集不得因仓库清单不完整阻断基础快照
目标环境仓库清单属于 SBOM 增强信息，基础 OS、包管理器、已安装组件和工具版本仍 SHALL 在可用时保存。

#### Scenario: 仓库 provides 命令不可用
- **WHEN** 目标环境无法执行仓库 provides 查询
- **THEN** `ENV_COLLECT` MAY 成功保存基础快照和已安装组件
- **AND** `raw_snapshot.parseWarnings` SHALL 记录仓库 provides 缺失原因
- **AND** 后续 SBOM 分析 SHALL 能基于已安装组件继续运行

#### Scenario: 已安装组件采集失败
- **WHEN** 已安装包或已安装库清单无法采集或无法解析
- **THEN** worker SHALL 将 `ENV_COLLECT` 任务标记为 `FAILED`
- **AND** 后端 MUST NOT 写入不完整成功快照

### Requirement: SBOM 组件采集必须保护路径和敏感信息
环境采集写入组件清单时 SHALL 避免把敏感路径、凭据或用户 home 文件内容暴露给 API、事件或日志摘要。

#### Scenario: 采集 native/so 文件
- **WHEN** 环境采集发现独立 native/so 文件
- **THEN** `environment_components.path` MAY 保存后端内部需要的远端文件路径
- **AND** API、任务事件和日志摘要 MUST NOT 暴露敏感路径或用户 home 文件内容
- **AND** 组件 `metadata` SHOULD 保存文件名、soname、哈希或大小等非敏感摘要

#### Scenario: 日志脱敏
- **WHEN** 采集脚本输出包含凭据、token、私钥、passphrase 或敏感路径
- **THEN** 后端 SHALL 在写入任务事件和日志 excerpt 前执行脱敏
