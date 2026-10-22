## ADDED Requirements

### Requirement: SBOM 分析必须支持同名工具版本匹配
SBOM 分析器 SHALL 在 package 和 repository 匹配之外，使用目标环境已安装 `TOOL` 组件判断同名工具是否已经存在，并根据安装来源和版本差异设置风险等级。

#### Scenario: 目标存在 package-managed 同名工具
- **WHEN** 源侧组件类型为 `TOOL`
- **AND** 目标已安装组件存在同名 `TOOL`
- **AND** 目标工具 metadata 包含 `installOrigin=package`
- **AND** 源侧与目标侧工具主版本相同或源侧主版本不可解析
- **THEN** 分析器 SHALL 生成 `TARGET_PRESENT` 候选
- **AND** `matchType` SHALL 为 `tool_name_version`
- **AND** risk SHALL 为 `LOW`
- **AND** candidate metadata SHALL 包含目标工具 `toolPath`、`versionText`、`versionMajor` 和 `installOrigin`

#### Scenario: 目标存在 unmanaged 同名工具
- **WHEN** 源侧组件类型为 `TOOL`
- **AND** 目标已安装组件存在同名 `TOOL`
- **AND** 目标工具 metadata 包含 `installOrigin=unmanaged` 或 `installOrigin=unknown`
- **THEN** 分析器 SHALL 生成 `TARGET_PRESENT` 候选
- **AND** `matchType` SHALL 为 `tool_name_version`
- **AND** risk SHALL 为 `MEDIUM`
- **AND** suggestion SHALL 表明目标环境存在同名工具但来源不可由包管理器追踪，需要确认工具链来源、路径优先级和兼容性

#### Scenario: 目标同名工具主版本不同
- **WHEN** 源侧组件类型为 `TOOL`
- **AND** 目标已安装组件存在同名 `TOOL`
- **AND** 源侧与目标侧 `versionMajor` 都可解析
- **AND** 两者主版本不同
- **THEN** 分析器 SHALL 生成 `TARGET_PRESENT` 候选
- **AND** `matchType` SHALL 为 `tool_name_version`
- **AND** risk SHALL 不得低于 `MEDIUM`
- **AND** candidate metadata SHALL 记录 source 和 candidate 的 `versionMajor`

#### Scenario: 已安装工具优先于仓库候选
- **WHEN** 目标已安装组件存在可匹配同名 `TOOL`
- **AND** 目标仓库也存在同名或类似软件包候选
- **THEN** 分析器 SHALL 优先生成来源为 installed 的 `TARGET_PRESENT` 候选
- **AND** 分析器 SHALL NOT 因仓库候选版本更高而覆盖目标已安装工具事实

### Requirement: SBOM 分析必须表达工具匹配证据
SBOM 分析结果 SHALL 在工具匹配 candidate metadata 中保留源侧和目标侧工具版本、安装来源和 owner package 证据。

#### Scenario: 输出工具匹配 metadata
- **WHEN** 分析器使用同名工具版本匹配生成候选
- **THEN** candidate metadata SHALL 包含 `sourceToolVersionText`、`sourceToolVersionMajor`、`candidateToolVersionText`、`candidateToolVersionMajor`
- **AND** candidate metadata SHALL 包含 `candidateInstallOrigin`
- **AND** candidate metadata SHALL 包含 `candidateToolPath`
- **AND** candidate metadata SHALL 保留已有 `sourceOwnerPackage`、`sourceOwnerVersion`、`sourceOwnerArch`

#### Scenario: 工具匹配证据不足
- **WHEN** 源侧或目标侧工具缺少可解析主版本
- **THEN** 分析器 MAY 继续使用同名工具事实生成 `TARGET_PRESENT`
- **AND** risk SHALL 根据目标 `installOrigin` 决定
- **AND** candidate metadata SHALL 保留原始 `versionText` 供审计
