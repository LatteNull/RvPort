## ADDED Requirements

### Requirement: SBOM 分析必须优先使用 ELF capability 匹配
SBOM 分析器 SHALL 优先使用 ELF `SONAME`、installed provides capability 和 repository provides capability 匹配库替代结果。

#### Scenario: exact SONAME 命中目标已安装组件
- **WHEN** 源侧库组件包含 `elfSoname`
- **AND** 目标已安装组件 metadata 包含相同 `elfSoname` 或 `providesCapabilities`
- **THEN** 分析器 SHALL 生成 `TARGET_PRESENT` 候选
- **AND** `matchType` SHALL 表示 exact ELF capability 或 exact SONAME
- **AND** confidence SHALL 为 `HIGH`

#### Scenario: exact SONAME 命中目标仓库 provides
- **WHEN** 源侧库组件包含 `elfSoname`
- **AND** 目标仓库 `REPOSITORY_PROVIDE` 组件 metadata 命中该 SONAME 或 capability
- **THEN** 分析器 SHALL 生成 `DIRECT_AVAILABLE` 或 `UPGRADE_AVAILABLE` 候选
- **AND** candidate metadata SHALL 包含 `provideKind`、`queryValue`、`packageName`、`scanner` 和 confidence
- **AND** 该候选 SHALL 优先于 normalized library name 匹配

#### Scenario: SONAME 主版本不一致
- **WHEN** 源侧 `elfSoname` 为 `libfoo.so.1`
- **AND** 目标侧只存在 `libfoo.so.2` 或 normalized `libfoo.so`
- **THEN** 分析器 MUST NOT 将该候选标记为 exact SONAME match
- **AND** 分析器 SHALL 降低 confidence 或要求人工确认
- **AND** 结果 evidence SHALL 表明 SONAME version mismatch

### Requirement: SBOM 分析必须优先进行 package-level 归并
SBOM 分析器 SHALL 先判断 package 级 replacement，再处理 library/native 级 replacement，并使用 owner package 关系消解已被 package 覆盖的 library/native。

#### Scenario: owner package 可迁移时 library 被 package 覆盖
- **WHEN** 源侧 library/native 组件 metadata 包含 `ownerPackage`
- **AND** 同一个源侧 package 已生成 `TARGET_PRESENT`、`DIRECT_AVAILABLE` 或 `UPGRADE_AVAILABLE` 的 package replacement result
- **THEN** 分析器 SHALL 将该 library/native 标记为 package-covered
- **AND** metadata SHALL 包含 `coveredByPackage=true`、`coveredByPackageName`、`coveredByPackageCandidate`、`coveredByPackageStatus` 和 `coveredByPackageMatchType`
- **AND** 该 library/native SHALL NOT 作为独立缺口或独立源码构建问题展示

#### Scenario: owner package 不可迁移时才进入 library 匹配
- **WHEN** 源侧 library/native 组件没有 owner package
- **OR** owner package 没有目标候选
- **OR** owner package 的 replacement status 为 `SOURCE_BUILD_REQUIRED`、`NO_ALTERNATIVE` 或 `MANUAL_CONFIRM_REQUIRED`
- **THEN** 分析器 SHALL 对该 library/native 执行 ELF SONAME、repository provides、normalized library 和 weak fallback 匹配
- **AND** metadata SHALL 表明该结果未被 package 覆盖

#### Scenario: package 覆盖结果可被审计
- **WHEN** API 返回 package-covered library/native 的结果或明细
- **THEN** 响应 SHALL 保留 source library/native 的 path、owner package、SONAME 和 coverage metadata
- **AND** 前端 MAY 默认折叠或过滤 covered library/native，但 SHALL 能在明细中查看覆盖证据

### Requirement: SBOM 分析不得把 ELF 依赖库当作替代候选
SBOM 分析器 MUST NOT 使用 source component 的 `elfNeeded` 或 `requiredCapabilities` 生成当前 component 的替代候选。

#### Scenario: source library 依赖 libc
- **WHEN** 源侧 `libfoo.so` 的 metadata 包含 `elfNeeded=libc.so.6`
- **AND** 目标侧存在 `libc.so.6`
- **THEN** 分析器 MUST NOT 将 `libc.so.6` 作为 `libfoo.so` 的 replacement candidate
- **AND** `libc.so.6` MAY 仅作为 dependency evidence 保存在 metadata 中

#### Scenario: target provides 仍可用于匹配当前 SONAME
- **WHEN** 源侧 `libfoo.so` 的 `elfSoname` 为 `libfoo.so.1`
- **AND** 目标 installed/repository component provides `libfoo.so.1`
- **THEN** 分析器 SHALL 可以使用该 provides capability 作为 replacement evidence
- **AND** 该行为不依赖 source 的 `elfNeeded` 字段

### Requirement: SBOM 分析必须表达 ELF evidence
SBOM 分析结果 SHALL 在候选 metadata 中表达 ELF metadata、capability evidence 和 fallback 匹配来源。

#### Scenario: 输出 ELF evidence
- **WHEN** 分析器使用 ELF capability、SONAME 或 repository provides 匹配候选
- **THEN** `replacement_candidates.metadata` SHALL 包含 source SONAME、candidate SONAME、source ELF machine/class、candidate ELF machine/class 和 match evidence
- **AND** metadata SHALL 表达 confidence 和 match source

#### Scenario: fallback 匹配
- **WHEN** 分析器只能使用 normalized library name 或 weak name 匹配
- **THEN** 结果 SHALL 明确标记为 fallback evidence
- **AND** confidence SHALL 低于 exact ELF capability 或 owner package match
- **AND** 对 library/native 组件，结果 MAY 使用 `MANUAL_CONFIRM_REQUIRED` 表示需要人工确认 ABI

#### Scenario: 缺少 ELF metadata
- **WHEN** 源侧或目标侧缺少 `elfSoname`、`elfMachine` 或 `providesCapabilities`
- **THEN** 分析器 SHALL 继续使用现有 owner package、repository package 和 normalized library fallback
- **AND** warnings 或 candidate metadata SHALL 表明 ELF evidence 不完整

### Requirement: SBOM 分析验证必须覆盖 ELF matching
SBOM 分析相关测试 SHALL 覆盖 ELF capability matching 的正常流程、异常流程和 edge case。

#### Scenario: 覆盖正常流程
- **WHEN** 编写 ELF matching 测试
- **THEN** 测试 SHALL 覆盖 exact SONAME installed match、exact SONAME repository provides match、owner package fallback 和 package-covered library/native

#### Scenario: 覆盖异常流程
- **WHEN** 编写 ELF matching 测试
- **THEN** 测试 SHALL 覆盖缺少 readelf/objdump metadata、repository provides 查询失败、analyzer 输入缺少 ELF metadata 和 owner package 不可迁移

#### Scenario: 覆盖 edge case
- **WHEN** 编写 ELF matching 测试
- **THEN** 测试 SHALL 覆盖 `libfoo.so.1` 与 `libfoo.so.2` 不应被 exact 匹配、同名不同架构、重复 provides、normalized fallback、weak match 降级和 `elfNeeded` 不应生成替代候选
