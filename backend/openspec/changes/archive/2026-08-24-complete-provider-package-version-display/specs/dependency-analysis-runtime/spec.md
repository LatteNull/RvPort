## ADDED Requirements

### Requirement: 依赖分析必须结构化展示 provider package 版本
依赖分析运行时 SHALL 为可解析的构建工具、ELF 和 SO 依赖保存并返回源端 provider package/version、目标端 provider package/version、detected version、provider version status 和版本证据置信度。

#### Scenario: 保存源目标 provider package 版本
- **WHEN** 依赖分析 worker 从构建事实中识别到构建工具、ELF 或 SO 依赖
- **THEN** worker SHALL 优先使用源环境包管理器 owner 查询获取 `sourceProviderPackage` 和 `sourceProviderVersion`
- **AND** worker SHALL 使用目标环境已安装包、目标软件源、provides 或 whatprovides 查询获取 `targetProviderPackage` 和 `targetProviderVersion`
- **AND** worker SHALL 将上述字段保存为结果明细的结构化字段或稳定 DTO 字段
- **AND** worker SHALL 在 evidence 中保留 owner 查询命令、匹配来源、版本解析方式和脱敏后的摘要

#### Scenario: ELF 和 SO 使用低风险版本探测
- **WHEN** 依赖项是 ELF 或 SO 文件
- **THEN** worker MUST NOT 默认对该文件执行 `--version`
- **AND** worker SHALL 优先使用 `rpm -qf`、`dpkg -S` 或等效包管理器 owner 查询获取包版本
- **AND** owner 查询失败时，worker MAY 使用 SONAME、文件名、symlink、`readelf`、`objdump` 或 `strings` 提取 `sourceDetectedVersion` 或 `targetDetectedVersion`
- **AND** `strings` 结果 MUST 标记为低置信度 evidence，不能作为高置信度 provider package version

#### Scenario: 工具命令补充 detected version
- **WHEN** 依赖项是构建工具或命令行工具
- **THEN** worker SHALL 优先使用包管理器 owner 查询获取 provider package version
- **AND** worker MAY 对白名单工具执行有限时、限长、脱敏的版本命令以获取 `sourceDetectedVersion` 或 `targetDetectedVersion`
- **AND** 版本命令失败 MUST NOT 导致依赖分析任务失败

#### Scenario: 计算 provider 版本状态
- **WHEN** 源端和目标端 provider 版本证据可用
- **THEN** worker SHALL 计算 `providerVersionStatus`
- **AND** 源有包、目标有包且大版本一致 SHALL 标记为 `SAME_MAJOR` 并映射为 `INFO`
- **AND** 源有包、目标有包且目标版本高于源版本 SHALL 标记为 `TARGET_NEWER` 并映射为 `LOW`
- **AND** 源有包、目标有包且目标版本低于源版本 SHALL 标记为 `TARGET_OLDER` 并映射为 `HIGH`
- **AND** 源无 owner package 但存在 detected version 且目标有 provider package version SHALL 标记为 `TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED` 并映射为 `MEDIUM`
- **AND** 源无 owner package 且目标无可确认版本 SHALL 标记为 `NO_TARGET_VERSION_FOUND` 并映射为 `CRITICAL`
- **AND** 证据不足或不适用时 SHALL 标记为 `UNKNOWN` 并保留 warning

#### Scenario: API 和制品展示 provider 版本
- **WHEN** 用户查询依赖分析列表、结果详情、JSON artifact、HTML artifact 或真实验证 HTML
- **THEN** 响应或制品 SHALL 展示源 provider package/version、源 detected version、目标 provider package/version、目标 detected version、provider version status、目标匹配状态和风险等级
- **AND** 响应或制品 MUST NOT 要求前端从 nested evidence 中推断这些主要字段
- **AND** 响应或制品 MUST NOT 暴露服务器真实路径、SSH 凭据、私钥、token 或完整远端日志

#### Scenario: provider 信息缺失时明确展示
- **WHEN** 源端或目标端 provider package/version 无法确认
- **THEN** API 和制品 SHALL 返回明确的空值、`UNKNOWN` 状态或 warning 摘要
- **AND** 后端 MUST NOT 将缺失字段伪装为已确认版本
- **AND** 后端 MUST NOT 因单条依赖缺少 provider version 导致整个依赖分析失败
