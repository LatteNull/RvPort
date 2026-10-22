## ADDED Requirements

### Requirement: 依赖分析必须解析动态库实际源路径
依赖分析运行时 SHALL 对 ELF `NEEDED` 和 `SONAME` 中出现的动态库名解析 source 环境实际库文件路径，并 SHALL 使用该路径查询 source owner package/version。

#### Scenario: 解析 libc 这类 NEEDED 动态库
- **WHEN** x86 构建事实中存在 `NEEDED` 动态库 `libc.so.6`
- **THEN** 构建事实采集 SHALL 尝试在 source 环境中解析 `libc.so.6` 的实际库文件路径
- **AND** 解析成功时 SHALL 记录实际库路径、resolver 来源、source owner package 和 source owner version
- **AND** 依赖分析结果 SHALL 使用该 owner package/version 作为 source provider 证据

#### Scenario: 动态库路径解析失败时降级
- **WHEN** `ldconfig`、安全路径扫描或等效 resolver 无法解析某个 `NEEDED` 动态库
- **THEN** 依赖分析 SHALL 保留当前 SONAME 匹配逻辑
- **AND** 结果 evidence SHALL 记录解析失败 warning
- **AND** 构建验证或依赖分析 MUST NOT 仅因单个动态库路径解析失败而失败

#### Scenario: 多候选动态库路径
- **WHEN** 同一 SONAME 在 source 环境中解析到多个候选路径
- **THEN** 后端 SHALL 优先选择实际引用 ELF 可确认的路径
- **AND** 无法确认唯一实际路径时 SHALL 保留候选摘要并降级为人工确认或低置信度 evidence
- **AND** 后端 MUST NOT 随机选择一个候选并标记为高置信度

### Requirement: 依赖分析必须支持同包生态 provider fallback
依赖分析运行时 SHALL 在默认 source 与 target 属于同一发行版包生态的前提下，当 target SO/provides 匹配失败但 source owner package 已确认时，使用 source owner package 对目标已安装包和目标软件源包进行 fallback 匹配。

#### Scenario: 目标 provides 缺失但同名包存在
- **WHEN** source 环境已确认动态库 owner package 为 `glibc`
- **AND** target 环境无法通过 SO/provides 定位该动态库 provider
- **AND** target 已安装包或目标软件源中存在同名 package `glibc`
- **THEN** 依赖分析 SHALL 使用 `glibc` 作为 target provider package
- **AND** evidence SHALL 标记 `matchedBy=source-owner-package-fallback`
- **AND** evidence SHALL 标记 `samePackageEcosystemAssumed=true`

#### Scenario: fallback 命中后继续比较大版本
- **WHEN** source owner package 和 target fallback package 都存在可解析版本
- **THEN** 依赖分析 SHALL 继续使用现有 major version 关系计算 `providerVersionStatus`
- **AND** 同大版本 SHALL 返回 `SAME_MAJOR` 和 `INFO`
- **AND** target 版本高于 source SHALL 返回 `TARGET_NEWER` 和 `LOW`
- **AND** target 版本低于 source SHALL 返回 `TARGET_OLDER` 和 `HIGH`

#### Scenario: fallback 命中但目标版本不可确认
- **WHEN** target fallback package 命中但目标 provider version 不可确认
- **THEN** 依赖分析 SHALL 返回证据不足状态或 `NO_TARGET_VERSION_FOUND`
- **AND** 后端 MUST NOT 因包名相同就伪造目标版本或低风险结论

#### Scenario: 不进行跨发行版 alias 推断
- **WHEN** source owner package 名称与 target 包生态中的等价包名不同
- **THEN** 本能力 MUST NOT 自动推断跨发行版 alias
- **AND** 后端 MUST NOT 将 `glibc` 自动等价为 `libc6`
- **AND** 该场景 SHALL 保持缺失、证据不足或人工确认状态，除非未来单独引入跨发行版 alias 能力
