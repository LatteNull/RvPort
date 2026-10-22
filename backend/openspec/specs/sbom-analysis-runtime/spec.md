> 迁移说明：SBOM 功能已取消。本文件保留历史设计背景，不代表当前可调用的功能；原有任务勾选和验证结论仅适用于原版本。

# sbom-analysis-runtime Specification

## Purpose

定义 RvPort SBOM 分析运行时的独立分析器、Java 后端调用契约、组件替代分析和结果持久化要求。

## Requirements

### Requirement: SBOM 分析器必须作为独立 CLI 工具运行
系统 SHALL 在根目录 `tools/sbom-analyzer` 提供独立 SBOM 分析 CLI，Java 后端通过受控进程调用该工具。Java 后端 SHALL 在调用分析器前准备本轮环境快照；分析器本身不得直接连接远程环境或读取后端数据库。

#### Scenario: Java 后端调用分析器
- **WHEN** worker 执行 `SBOM_ANALYSIS` 任务
- **THEN** 后端 SHALL 先为源环境和目标环境生成本轮环境快照
- **AND** 后端 SHALL 将环境快照和组件清单导出为分析器输入 JSON
- **AND** 后端 SHALL 以受控进程调用 `tools/sbom-analyzer`
- **AND** 后端 SHALL 从分析器输出 JSON 导入 SBOM 结果

#### Scenario: 分析器不访问远程环境
- **WHEN** 分析器执行替代分析
- **THEN** 分析器 MUST NOT 建立 SSH 连接
- **AND** 分析器 MUST NOT 解密或读取 Git/SSH 凭据
- **AND** 分析器 MUST NOT 直接查询后端 PostgreSQL

#### Scenario: 分析器失败
- **WHEN** 分析器返回非零退出码、输出 JSON 缺失或输出 JSON 无法解析
- **THEN** worker SHALL 将 `SBOM_ANALYSIS` 任务标记为 `FAILED`
- **AND** 后端 SHALL 保存 tool run、stdout/stderr 日志和安全错误摘要
- **AND** 后端 MUST NOT 写入成功态 SBOM 结果

### Requirement: SBOM 分析器输入输出必须使用稳定 JSON 契约
SBOM 分析器 SHALL 使用版本化 JSON 输入和输出，使 Java 后端可以稳定导出、调用和导入。

#### Scenario: 生成分析器输入
- **WHEN** Java 后端准备调用分析器
- **THEN** 输入 JSON SHALL 包含 `schemaVersion`、项目信息、运行信息、源环境、目标环境、源快照、目标快照、源组件、目标已安装组件、目标仓库组件和分析选项
- **AND** 输入 JSON MUST NOT 包含明文凭据、服务器真实绝对路径或任务完整日志

#### Scenario: 读取分析器输出
- **WHEN** 分析器成功完成
- **THEN** 输出 JSON SHALL 包含 `schemaVersion`、`summary`、`components`、`replacementCandidates`、`warnings` 和 `tool`
- **AND** `replacementCandidates` SHALL 为每个源侧组件给出替代结论或明确无候选结论
- **AND** 输出 JSON MUST NOT 包含明文凭据或服务器真实绝对路径

#### Scenario: 版本不兼容
- **WHEN** 分析器输出的 `schemaVersion` 不被 Java 后端支持
- **THEN** worker SHALL 将任务标记为 `FAILED`
- **AND** 失败摘要 SHALL 表示分析器结果版本不兼容

### Requirement: SBOM 分析必须比较源侧依赖和目标侧可替代能力
SBOM 分析 SHALL 基于源侧已安装组件和目标侧已安装及仓库可用组件生成替代候选和风险。

#### Scenario: 目标侧已安装组件可满足源侧组件
- **WHEN** 源侧组件在目标已安装组件中存在可匹配项
- **THEN** 分析结果 SHALL 生成 `TARGET_PRESENT` 替代结论
- **AND** 候选项 SHALL 包含匹配类型、候选名称、版本、架构和证据摘要

#### Scenario: 目标仓库存在可安装候选
- **WHEN** 源侧组件未在目标已安装组件中命中但在目标仓库组件中存在候选
- **THEN** 分析结果 SHALL 生成 `DIRECT_AVAILABLE` 或 `UPGRADE_AVAILABLE` 替代结论
- **AND** 候选项 SHALL 标记来源为仓库清单

#### Scenario: 只能源码构建或人工确认
- **WHEN** 源侧组件无法从目标已安装组件或目标仓库组件中直接匹配
- **THEN** 分析结果 SHALL 生成 `SOURCE_BUILD_REQUIRED`、`NO_ALTERNATIVE` 或 `MANUAL_CONFIRM_REQUIRED` 结论
- **AND** 结果 SHALL 给出可展示的建议说明和风险等级

### Requirement: Java SBOM runtime 必须持久化分析运行和结果
Java SBOM runtime SHALL 创建并更新 `sbom_runs`，在同一任务中完成源/目标环境采集，回填快照 ID，并将分析器结果导入 `sbom_components` 和 `replacement_candidates`。

#### Scenario: 创建 SBOM 运行记录
- **WHEN** 用户创建 SBOM 分析任务
- **THEN** 后端 SHALL 创建 `SBOM_ANALYSIS` 任务
- **AND** 后端 SHALL 创建或准备关联该任务的 `sbom_runs` 运行记录
- **AND** `sbom_runs` SHALL 引用项目、源环境、目标环境和任务 ID
- **AND** `sbom_runs.source_snapshot_id` 和 `sbom_runs.target_snapshot_id` MAY 在采集完成前为空
- **AND** 后端 SHALL 使用默认全量采集范围和默认仓库策略，不依赖前端提交分析选项

#### Scenario: SBOM 任务内部采集环境
- **WHEN** worker 开始执行 `SBOM_ANALYSIS` 任务
- **THEN** worker SHALL 将 SBOM 运行标记为 `RUNNING`
- **AND** worker SHALL 先采集源环境并保存源快照和组件清单
- **AND** worker SHALL 再采集目标环境并保存目标快照和组件清单
- **AND** worker SHALL 将新生成的源快照 ID 和目标快照 ID 回填到 `sbom_runs`
- **AND** worker SHALL 只基于本轮生成的快照构造分析器输入

#### Scenario: 源环境采集失败
- **WHEN** `SBOM_ANALYSIS` 任务中的源环境采集失败
- **THEN** worker SHALL 将 SBOM 运行和任务标记为 `FAILED`
- **AND** 失败摘要 SHALL 表达失败阶段为 `SOURCE_COLLECT`
- **AND** worker MUST NOT 调用 SBOM 分析器

#### Scenario: 目标环境采集失败
- **WHEN** `SBOM_ANALYSIS` 任务中的目标环境采集失败
- **THEN** worker SHALL 将 SBOM 运行和任务标记为 `FAILED`
- **AND** 失败摘要 SHALL 表达失败阶段为 `TARGET_COLLECT`
- **AND** 已生成的源环境快照 MAY 保留供审计
- **AND** worker MUST NOT 调用 SBOM 分析器

#### Scenario: 任务取消
- **WHEN** 用户取消正在运行的 `SBOM_ANALYSIS` 任务
- **THEN** worker SHALL 尝试中止当前 SSH 采集命令或本地分析器进程
- **AND** worker SHALL 将 SBOM 运行标记为 `CANCELLED`
- **AND** 已完成的快照 MAY 保留供审计，但 MUST NOT 写入成功态 SBOM 结果

#### Scenario: 导入组件结果
- **WHEN** 分析器成功输出组件结果
- **THEN** 后端 SHALL 写入 `sbom_components`
- **AND** 源侧组件 SHALL 使用 `environment_side=SOURCE`
- **AND** 目标侧或候选组件 SHALL 使用 `environment_side=TARGET` 或 `CANDIDATE`
- **AND** 每个组件 SHALL 具备稳定 `fingerprint`

#### Scenario: 导入替代候选
- **WHEN** 分析器成功输出替代候选
- **THEN** 后端 SHALL 写入 `replacement_candidates`
- **AND** 每个候选 SHALL 关联对应源侧 `sbom_components`
- **AND** `replacement_status` SHALL 使用既有数据库枚举值

### Requirement: SBOM 分析必须配套测试覆盖
SBOM 分析相关实现 SHALL 配套 Java 单元测试、分析器测试和 API E2E 测试，并覆盖正常流程、异常流程和 edge case。

#### Scenario: 覆盖正常流程
- **WHEN** 编写 SBOM 分析测试
- **THEN** 测试 SHALL 覆盖创建分析任务、源环境采集、目标环境采集、快照回填、导出输入、调用分析器、导入结果、查询列表、查询详情和查询组件结果

#### Scenario: 覆盖异常流程
- **WHEN** 编写 SBOM 分析测试
- **THEN** 测试 SHALL 覆盖环境不存在、环境不属于项目、源环境采集失败、目标环境采集失败、分析器退出失败、输出 JSON 无效、输出版本不兼容和结果导入失败

#### Scenario: 覆盖 edge case
- **WHEN** 编写 SBOM 分析测试
- **THEN** 测试 SHALL 覆盖空组件清单、同名不同版本组件、同名不同架构组件、仓库候选重复、`.so` 仅名称匹配、采集中查询采集详情、取消时部分快照已生成、输出过大和日志脱敏

### Requirement: SBOM 分析必须使用 provider 证据匹配库替代
SBOM 分析器 SHALL 优先使用源侧 owner package、目标侧 provider/whatprovides 证据和仓库候选生成库替代结果。

#### Scenario: 源侧库存在 owner package
- **WHEN** 分析器输入中的源侧 `.so` 组件包含 owner package metadata
- **THEN** 分析器 SHALL 将 owner package 作为优先匹配线索
- **AND** 分析器 SHALL 在候选 evidence 中记录 owner package 名称、版本和架构

#### Scenario: 目标侧已安装组件提供同名库
- **WHEN** 目标已安装组件 metadata 表明某个包提供源侧库或其归一化候选
- **THEN** 分析器 SHALL 生成 `TARGET_PRESENT` 候选
- **AND** 候选 SHALL 记录匹配依据为 installed provider evidence
- **AND** 候选 SHALL 给出 confidence

#### Scenario: 目标仓库提供库文件
- **WHEN** 目标仓库组件或 `REPOSITORY_PROVIDE` 记录命中源侧库、normalized name 或 query pattern
- **THEN** 分析器 SHALL 生成 `DIRECT_AVAILABLE` 或 `UPGRADE_AVAILABLE` 候选
- **AND** 候选 SHALL 记录匹配依据为 repository provides evidence
- **AND** 候选 SHALL 包含目标包名、路径或 provides pattern 摘要

### Requirement: SBOM 分析必须处理架构归一化候选
SBOM 分析器 SHALL 使用环境采集生成的架构归一化候选进行跨架构匹配，并保留原始事实与匹配置信度。

#### Scenario: 使用 normalized library name 查询候选
- **WHEN** 源侧库组件包含 normalized library name
- **THEN** 分析器 SHALL 使用 normalized library name 与目标已安装库、目标仓库 provides 和目标包候选匹配
- **AND** 分析器 SHALL 在结果 evidence 中保存原始库名和 normalized library name

#### Scenario: 使用架构替换后的 package candidate
- **WHEN** 源侧组件包含替换为目标架构 token 的 package candidate
- **THEN** 分析器 SHALL 使用该候选查询目标仓库包
- **AND** 命中结果 SHALL 标记为 normalized package match
- **AND** confidence SHALL 低于精确 owner package 或 exact provides 命中

#### Scenario: 归一化候选未命中
- **WHEN** 原始名称、owner package、normalized name 和 package candidates 均未命中目标已安装或仓库组件
- **THEN** 分析器 SHALL 保持 `SOURCE_BUILD_REQUIRED`、`NO_ALTERNATIVE` 或 `MANUAL_CONFIRM_REQUIRED` 结论
- **AND** 分析器 SHALL 在 evidence 中说明 provider evidence 不足或仓库候选不可用

### Requirement: SBOM 分析必须表达仓库证据完整性
SBOM 分析结果 SHALL 表达目标仓库 metadata refresh、repoquery 和 provides 查询是否完整，以便前端解释结果可信度。

#### Scenario: 仓库 metadata 可用
- **WHEN** 目标快照表明仓库 metadata refresh 成功且 repository packages/provides 已采集
- **THEN** 分析器 SHALL 将仓库证据状态标记为完整或部分完整
- **AND** 分析摘要 SHALL 包含 repository evidence counters

#### Scenario: 仓库 metadata 不可用
- **WHEN** 目标快照包含 metadata refresh 失败或 repository scanner warning
- **THEN** 分析器 SHALL 在 warnings 中返回仓库证据不完整摘要
- **AND** 分析器 SHALL 避免把缺少仓库证据等同于目标无替代包

#### Scenario: provider 证据不足
- **WHEN** 源侧或目标侧缺少 owner package、whatprovides 或 normalized metadata
- **THEN** 分析器 SHALL 降低相关候选 confidence
- **AND** 分析器 SHALL 在 evidence 中标明匹配依据来自弱名称匹配

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

### Requirement: SBOM 分析成功后必须持久化结果明细和轻量 artifact
Java SBOM runtime SHALL 在 `SBOM_ANALYSIS` 成功完成后按行持久化分析结果明细，并生成轻量、非敏感、可审计的分析 artifact。

#### Scenario: 按行保存分析结果明细
- **WHEN** 分析器成功输出 package、library、tool 或 native file 对比结果
- **THEN** 后端 SHALL 将每条结果分别写入 `sbom_analysis_result_items`
- **AND** 每条结果 SHALL 关联对应 `project_id`、`task_id` 和 `sbom_run_id`
- **AND** 每条结果 SHALL 保存可用于分页、排序和过滤的普通列
- **AND** 后端 MUST NOT 将完整结果数组整体塞入单个 JSON 字段

#### Scenario: 生成审计摘要 artifact
- **WHEN** 分析器成功输出结果且后端完成结果明细导入
- **THEN** 后端 SHALL 生成 `AUDIT_SUMMARY_JSON` artifact
- **AND** artifact SHALL 包含运行 ID、项目 ID、任务 ID、源/目标环境摘要、源/目标快照摘要、组件数量、replacement status counts、risk counts、match counts、warnings 和工具信息
- **AND** artifact MAY 包含有限样本和结果列表查询入口
- **AND** artifact MUST NOT 保存完整结果明细数组
- **AND** artifact SHALL 关联对应 `project_id`、`task_id` 和 `sbom_run_id`

#### Scenario: 生成分析器输入摘要 artifact
- **WHEN** 后端准备分析器输入 JSON
- **THEN** 后端 SHALL 在成功路径中保存 `ANALYZER_INPUT_SUMMARY_JSON` artifact
- **AND** artifact SHALL 包含输入 schema version、源/目标快照 ID、采集范围、仓库策略和输入组件数量
- **AND** artifact MUST NOT 保存完整组件数组

#### Scenario: 生成分析器输出摘要 artifact
- **WHEN** 后端解析分析器输出 JSON
- **THEN** 后端 SHALL 在成功路径中保存 `ANALYZER_OUTPUT_SUMMARY_JSON` artifact
- **AND** artifact SHALL 包含输出 schema version、summary、warnings、tool、组件数量和候选数量
- **AND** artifact MAY 包含有限候选样本
- **AND** artifact MUST NOT 保存完整分析器输出原文

#### Scenario: 结果明细或 artifact 写入失败
- **WHEN** SBOM 分析结果明细或 artifact 写入失败
- **THEN** worker SHALL 将 `SBOM_ANALYSIS` 任务标记为 `FAILED`
- **AND** 后端 SHALL 将 `sbom_runs` 标记为 `FAILED`
- **AND** 后端 SHALL 保存脱敏失败摘要

### Requirement: SBOM artifact 内容必须使用白名单构造
SBOM artifact builder SHALL 使用字段白名单构造 artifact 内容，不得直接复制完整 analyzer input、analyzer output、raw snapshot 或任务日志。

#### Scenario: 过滤敏感内容
- **WHEN** 后端生成 SBOM artifact
- **THEN** artifact 内容 MUST NOT 包含明文凭据、私钥、token、passphrase 或完整任务日志
- **AND** artifact 内容 MUST NOT 包含服务器真实绝对路径
- **AND** artifact 内容 MUST NOT 包含未经筛选的 `raw_snapshot`

#### Scenario: 保存路径类信息
- **WHEN** artifact 需要表达工具路径、库路径或文件路径
- **THEN** 后端 SHALL 只保存远端采集到的非敏感路径、文件名、遮蔽路径、哈希或摘要
- **AND** 后端 MUST NOT 保存后端服务器本地 runtime 绝对路径

#### Scenario: 计算 artifact 摘要
- **WHEN** 后端保存 SBOM artifact
- **THEN** 后端 SHALL 基于实际写入的 JSON 内容计算 `sha256`
- **AND** 后端 SHALL 保存实际 JSON 字节数为 `size_bytes`

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

### Requirement: SBOM result items 必须可加入迁移输入
SBOM 分析结果明细 SHALL 能作为迁移输入 reference 的来源，但 SBOM run 本身 SHALL 继续保持环境分析维度，不强制绑定源码版本。

#### Scenario: SBOM result 导入迁移输入
- **WHEN** 用户将 SBOM result item 加入迁移输入
- **THEN** 后端 SHALL 校验该 result item 属于当前项目
- **AND** 后端 SHALL 将创建出的迁移输入 reference 绑定到 URL 中的 `sourceRevisionId`
- **AND** 后端 MUST NOT 要求 `sbom_runs` 或 `sbom_analysis_result_items` 持有 `source_revision_id`

#### Scenario: SBOM detected level
- **WHEN** 后端为 SBOM result item 创建迁移输入 reference
- **THEN** `detectedLevel` SHALL 使用 `riskLevel + "/" + targetMatchStatus`
- **AND** 示例值 MAY 为 `HIGH/SOURCE_BUILD_REQUIRED` 或 `LOW/TARGET_PRESENT`

#### Scenario: SBOM location label
- **WHEN** 后端为 SBOM result item 创建迁移输入 reference
- **THEN** 软件包条目 SHALL 使用 `package:name@version`
- **AND** 独立库文件 SHALL 使用 `lib:path`
- **AND** native 文件 SHALL 使用 `native:path`
- **AND** 工具条目 SHALL 使用 `tool:name@version`
- **AND** 缺少版本或路径时 SHALL 使用可用的组件名称 fallback

#### Scenario: SBOM 详情查询保留结构化字段
- **WHEN** 用户查询 SBOM 来源的迁移输入详情
- **THEN** 后端 SHALL 返回对应 SBOM result item 的 `riskLevel`、`targetMatchStatus`、源组件摘要、目标候选摘要、匹配策略、建议和证据
- **AND** 响应 MUST NOT 暴露明文凭据、完整 analyzer output 或服务器真实路径

### Requirement: SBOM 分析 artifact 必须支持对象存储
SBOM 分析运行时 SHALL 支持将新生成的分析输出制品保存到对象存储，并 SHALL 保持现有 SBOM artifact 查询接口语义。

#### Scenario: 保存 SBOM 输出到对象存储
- **WHEN** SBOM 分析生成审计摘要、分析器输入摘要或分析器输出摘要 artifact
- **THEN** 后端 SHALL 能将 artifact 内容保存到对象存储
- **AND** 后端 SHALL 保存输出制品元数据
- **AND** 元数据 SHALL 关联 `project_id`、`task_id` 和 `sbom_run_id`

#### Scenario: 查询 SBOM artifact 摘要
- **WHEN** 用户查询 SBOM artifact 列表
- **THEN** 后端 SHALL 返回业务需要的 artifact metadata 和 summary
- **AND** 响应 MUST NOT 返回对象存储 bucket、object key 或服务器真实路径

#### Scenario: 查询 SBOM artifact 内容
- **WHEN** 用户查询某个 SBOM artifact 内容
- **THEN** 后端 SHALL 校验用户对分析所属项目有访问权限
- **AND** 后端 SHALL 从对象存储或兼容的历史 JSON 内容读取 artifact 内容
- **AND** 后端 MUST NOT 暴露对象存储内部位置

### Requirement: SBOM 分析必须使用项目当前运行双环境
SBOM 分析 SHALL 从项目运行环境配置读取源环境和目标环境，并 SHALL 使用该配置版本创建分析运行。

#### Scenario: 创建 SBOM 分析读取运行环境
- **WHEN** 用户创建 SBOM 分析任务
- **THEN** 后端 SHALL 读取项目当前运行环境配置
- **AND** 后端 SHALL 使用配置中的源环境和目标环境创建 `SBOM_ANALYSIS` 任务
- **AND** `sbom_runs` SHALL 保存源环境 ID、目标环境 ID 和环境配置版本

#### Scenario: 缺少双环境时拒绝 SBOM 分析
- **WHEN** 用户创建 SBOM 分析任务且项目运行环境配置不完整
- **THEN** 后端 SHALL 返回运行环境未配置完整错误
- **AND** 后端 MUST NOT 创建 `sbom_runs`、任务或队列消息

#### Scenario: 环境配置变更后 SBOM 结果过期
- **WHEN** 用户查询 SBOM 分析列表或详情
- **THEN** 响应 SHALL 标识该 SBOM 运行是否属于当前项目运行环境配置版本
- **AND** 非当前版本结果 SHALL 保留为历史记录但不得作为当前报告默认输入

### Requirement: SBOM 分析主流程必须标记为 deprecated
SBOM 分析运行时 SHALL 保留旧 API、旧任务类型和历史数据兼容，但 SHALL 在新迁移主流程中标记为 deprecated。

#### Scenario: 保留历史 SBOM 查询
- **WHEN** 用户查询历史 SBOM 分析记录、结果明细或 artifact
- **THEN** 后端 SHALL 在权限校验通过后继续返回历史数据
- **AND** 响应 SHALL 能表达该能力已 deprecated
- **AND** 响应 MUST NOT 暴露服务器真实路径、对象存储内部 key 或明文凭据

#### Scenario: 新流程不默认创建 SBOM 分析
- **WHEN** 前端执行新迁移流程
- **THEN** 前端和后端 SHALL 默认使用依赖分析节点
- **AND** 后端 MUST NOT 在新流程自动合并、报告或归档中默认创建新的 `SBOM_ANALYSIS` 任务

#### Scenario: 保留历史 SBOM 数据
- **WHEN** 系统升级到依赖分析主流程
- **THEN** 旧 `sbom_*` 表、旧 `SBOM_RESULT` 迁移输入和旧 SBOM artifact SHALL 保留历史兼容
- **AND** 后端 MUST NOT 将新依赖分析结果写入旧 `sbom_*` 表

#### Scenario: SBOM 创建入口兼容策略
- **WHEN** 客户端调用旧 SBOM 创建接口
- **THEN** 后端 SHALL 按配置保留兼容创建或返回明确 deprecated 错误
- **AND** 错误响应 SHALL 说明应使用依赖分析 API
- **AND** 后端 MUST NOT 静默把旧 SBOM 创建请求改写为依赖分析请求
