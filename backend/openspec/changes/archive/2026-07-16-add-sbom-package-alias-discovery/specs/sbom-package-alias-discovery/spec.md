## ADDED Requirements

### Requirement: 系统库采集必须覆盖 multiarch runtime module
系统在采集环境 native library 时 SHALL 将系统库目录的扫描深度调整为 4，并 SHALL 保持文件类型和文件名过滤，避免扫描非库文件。

#### Scenario: 采集 Debian multiarch gconv 模块
- **WHEN** 目标环境存在 `/usr/lib/riscv64-linux-gnu/gconv/CP1250.so`
- **THEN** 环境采集结果 MUST 包含该文件及其 owner package 信息

#### Scenario: 扫描范围仍受限制
- **WHEN** 系统库目录下存在非 `.so*` 普通文件
- **THEN** 环境采集 MUST NOT 将该普通文件作为 native library 组件入库

### Requirement: 分析器必须发现包名等价观测
SBOM 分析器 SHALL 在 source 和 target 通过库文件、ELF capability 或运行时模块证据匹配成功但 owner package 不一致时，生成 package alias observation。

#### Scenario: glibc 与 libc6 通过 CP1250.so 形成候选等价关系
- **WHEN** source 组件 `CP1250.so` 的 owner package 是 `glibc`，target 组件 `CP1250.so` 的 owner package 是 `libc6`
- **THEN** 分析器 MUST 输出 `glibc -> libc6` 的 package alias observation，并记录 evidence value 为 `CP1250.so`

#### Scenario: 弱名称匹配不生成高置信等价关系
- **WHEN** source 与 target 仅通过 weak name 命中
- **THEN** 分析器 MUST NOT 将该命中记录为高置信 package alias observation

### Requirement: 本次分析必须使用已发现的等价关系
系统 SHALL 在本次分析中使用有明确证据的 package alias observation 作为匹配依据，并在结果 metadata 中展示 alias 证据。

#### Scenario: 跨操作系统先执行库证据预分析
- **WHEN** source 与 target 的操作系统、发行版或包管理器不同
- **THEN** 分析器 MUST 在 package/tool 判断前先执行 library/native evidence pre-pass，并用该阶段发现的 package alias observation 参与 package/tool 判断

#### Scenario: 有 alias 证据的运行时库不再进入人工确认
- **WHEN** source 运行时库只因 owner package 名称不同而未命中 exact package，但存在同名目标库文件和 package alias observation
- **THEN** 分析结果 MUST 返回目标候选，并 MUST NOT 将该项标记为 `MANUAL_CONFIRM_REQUIRED`

#### Scenario: 包判断使用预分析生成的 alias
- **WHEN** library/native evidence pre-pass 发现 `glibc -> libc6` 等价候选
- **THEN** package/tool 判断 MUST 使用该候选关系匹配 source package `glibc` 的目标候选

#### Scenario: 结果展示 alias 证据
- **WHEN** replacement candidate 使用 package alias observation 匹配
- **THEN** candidate metadata MUST 包含 source owner package、target owner package、alias evidence type、alias evidence value 和 alias confidence

### Requirement: 等价关系必须可持久化和复用
Java 后端 SHALL 持久化 package alias observations，并 SHALL 在后续 SBOM 分析中向分析器注入可用的历史 alias。

#### Scenario: 保存自动发现的候选关系
- **WHEN** SBOM 分析器输出 package alias observation
- **THEN** Java 后端 MUST 将该 observation 保存到数据库，并维护 observed count、first seen time 和 last seen time

#### Scenario: 注入历史候选关系
- **WHEN** 后续分析的 source distro、target distro、package manager 与历史 observation 匹配
- **THEN** Java 后端 MUST 将未被拒绝的 alias 关系加入 analyzer input

#### Scenario: 被拒绝的关系不参与匹配
- **WHEN** 历史 package alias observation 的状态为 `REJECTED`
- **THEN** Java 后端 MUST NOT 将该关系注入 analyzer input

### Requirement: 查询接口必须支持分页排序过滤
系统 SHALL 为 package alias observation 提供可查询的数据能力，并 SHALL 支持分页、排序和按关键字段过滤，以符合后续类似接口的统一约定。

#### Scenario: 按包名过滤 observation
- **WHEN** 调用方按 source package 或 target package 查询 package alias observations
- **THEN** 系统 MUST 返回匹配记录，并包含分页信息

#### Scenario: 按状态过滤 observation
- **WHEN** 调用方按 `CANDIDATE`、`APPROVED` 或 `REJECTED` 状态过滤
- **THEN** 系统 MUST 只返回对应状态的 observation

### Requirement: 测试必须覆盖正常流程、异常流程和 edge case
实现 SHALL 为环境采集、分析器匹配、Java 导入和查询能力补充测试，且测试 MUST 覆盖正常流程、异常流程和 edge case。

#### Scenario: 正常流程测试
- **WHEN** source `glibc` 与 target `libc6` 通过 `CP1250.so` 匹配
- **THEN** 测试 MUST 验证 alias observation 被生成、保存并用于结果匹配

#### Scenario: 异常流程测试
- **WHEN** analyzer 输出非法 alias observation 或缺少必要字段
- **THEN** Java 导入逻辑 MUST 跳过非法记录或返回明确错误，且不得破坏主分析结果导入

#### Scenario: Edge case 测试
- **WHEN** 多个 target package 都提供同名库文件
- **THEN** 系统 MUST 保留证据并避免生成无依据的高置信唯一等价关系
