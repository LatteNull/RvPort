## MODIFIED Requirements

### Requirement: 环境采集必须支持 SBOM 组件清单
环境采集 SHALL 为 SBOM 分析保存可复用的组件清单，并根据环境角色区分源侧已安装清单和目标侧仓库可用清单。该能力 SHALL 可由独立 `ENV_COLLECT` 任务调用，也 SHALL 可由 `SBOM_ANALYSIS` 任务作为内部步骤调用。

#### Scenario: 采集 x86 源环境组件
- **WHEN** worker 执行 `SOURCE_X86` 环境的采集步骤
- **THEN** 后端 SHALL 采集已安装软件包、已安装库、基础工具版本和独立 native/so 文件摘要
- **AND** 后端 SHALL 将组件写入 `environment_components`
- **AND** `source` SHALL 标记为 `INSTALLED_PACKAGE`、`INSTALLED_LIBRARY`、`TOOL_VERSION` 或 `NATIVE_FILE`

#### Scenario: 采集 RISC-V 目标环境已安装组件
- **WHEN** worker 执行 `TARGET_RISCV` 环境的采集步骤
- **THEN** 后端 SHALL 采集已安装软件包、已安装库、基础工具版本和独立 native/so 文件摘要
- **AND** 后端 SHALL 将组件写入 `environment_components`
- **AND** `source` SHALL 标记为 `INSTALLED_PACKAGE`、`INSTALLED_LIBRARY`、`TOOL_VERSION` 或 `NATIVE_FILE`

#### Scenario: 采集 RISC-V 目标环境仓库候选
- **WHEN** worker 执行 `TARGET_RISCV` 环境的采集步骤
- **THEN** 后端 SHALL 尝试采集软件源可用包和仓库 provides/so 能力
- **AND** 仓库可用包 SHALL 写入 `environment_components` 并标记 `source=REPOSITORY_PACKAGE`
- **AND** 仓库 provides/so 能力 SHALL 写入 `environment_components` 并标记 `source=REPOSITORY_PROVIDE`
- **AND** 采集失败或命令不可用时 SHALL 在快照 `raw_snapshot` 中记录解析警告

#### Scenario: SBOM 内部采集复用环境采集语义
- **WHEN** `SBOM_ANALYSIS` 任务内部调用环境采集
- **THEN** 后端 SHALL 复用环境采集的脱敏、组件写入、仓库证据、ELF metadata、provider 证据和 unmanaged 工具证据规则
- **AND** 生成的环境快照 SHALL 关联当前 `SBOM_ANALYSIS` 任务 ID
- **AND** 采集日志 SHALL 写入当前 SBOM 任务的日志事件，供项目级 SSE 和任务日志接口恢复查看
