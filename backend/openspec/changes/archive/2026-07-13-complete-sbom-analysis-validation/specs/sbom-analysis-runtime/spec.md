## ADDED Requirements

### Requirement: SBOM 分析必须提供可复跑真实验证记录
SBOM 分析运行时 SHALL 提供可复跑的真实验证流程，用于基于 x86 源环境和 RISC-V 目标环境验证 provider 证据、仓库 metadata、whatprovides 和分析器结果。

#### Scenario: 记录真实环境采集摘要
- **WHEN** 开发者运行 SBOM 真实验证流程
- **THEN** 验证流程 SHALL 记录源环境和目标环境的采集任务 ID、环境角色、OS、架构、包管理器、已安装组件数量、仓库候选数量和 warning 摘要
- **AND** 记录 SHALL 包含 owner package、provider evidence、repo metadata refresh 和 whatprovides 的非敏感统计
- **AND** 记录 MUST NOT 包含 SSH 密码、私钥、passphrase、token 或敏感路径

#### Scenario: 记录分析器输入输出摘要
- **WHEN** 验证流程运行 `SBOM_ANALYSIS`
- **THEN** 验证流程 SHALL 保存分析器输入摘要、输出摘要、replacement status counts、risk counts、match counts 和 warnings
- **AND** 验证流程 SHALL 记录目标仓库候选是否为空及其原因
- **AND** 验证流程 MUST NOT 保存完整明文凭据或未经脱敏的完整任务日志

#### Scenario: 仓库证据缺失时验证失败或明确标记
- **WHEN** 目标 RISC-V 仓库 metadata、repoquery 或 whatprovides 无法使用
- **THEN** 验证流程 SHALL 将该事实记录为明确 warning 或失败原因
- **AND** 验证流程 MUST NOT 把仓库证据缺失解释为目标无替代包

### Requirement: SBOM 分析验证必须覆盖完整测试矩阵
SBOM 分析验证 SHALL 覆盖 Java 单元测试、SBOM analyzer 测试和 API E2E/真实联通验证，并明确区分 passed、failed 和 skipped。

#### Scenario: 运行可自动执行的测试
- **WHEN** 开发者执行 SBOM 验证任务
- **THEN** 验证 SHALL 运行 Maven 相关单元测试
- **AND** 验证 SHALL 运行 `tools/sbom-analyzer` 的测试
- **AND** 验证 SHALL 运行语法检查或静态检查覆盖 SBOM E2E 脚本

#### Scenario: 外部前置条件不可用
- **WHEN** Docker、后端 API、worker、RabbitMQ 或 SSH 环境不可用
- **THEN** 验证 SHALL 明确输出 skipped 或 failed 的前置条件原因
- **AND** 验证 MUST NOT 将未执行的 API E2E 或真实 SSH 验证报告为 passed

#### Scenario: 验证发现缺陷
- **WHEN** 验证发现 provider evidence、repo metadata、whatprovides 或分析结果缺陷
- **THEN** 实现 SHALL 优先修复缺陷或记录新的 follow-up change
- **AND** 归档前 SHALL 在 tasks 中说明缺陷处理状态
