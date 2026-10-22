## Context

依赖分析已经从旧 SBOM 差异分析转向“基于 x86 构建事实的依赖分析”。这个方向是正确的：先让项目在源环境成功构建，再从构建事实中提取真正和该源码相关的依赖，最后验证目标 RISC-V 环境是否具备对应能力。

当前仍有两个偏差：

1. `compile_commands.json`、`build.ninja`、CMake flag probe、编译宏等构建元数据会进入依赖结果列表。这类信息对源码扫描或构建诊断有价值，但不是本阶段要展示的可替代依赖。
2. ELF/SO 结果主要停留在“源机器用了哪些库文件”。实际要判断的是：这些库文件由源环境哪个软件包提供，目标环境或目标软件源是否有对应软件包，以及版本关系如何。

## Goals / Non-Goals

**Goals:**

- 依赖分析结果只保留工具、软件包、库、头文件、pkg-config module、测试依赖等可迁移依赖。
- 不再把 compiler flag、宏、编译数据库文件、构建脚本元数据作为依赖结果项展示。
- 对 ELF/SO 建立源侧 provider package 到目标侧 provider package 的版本匹配。
- 按五类场景稳定映射风险等级，并把映射依据写入 evidence。
- 对重复 ELF/SO 命中做聚合，列表用于决策，详情用于审计。
- 补齐单元测试、E2E 和真实项目 HTML/JSON 汇总验证。

**Non-Goals:**

- 不删除构建日志、trace、compile database 等原始 evidence 采集能力。
- 不恢复旧 SBOM 两操作系统全量差异分析。
- 不在本 change 中实现源码宏、编译参数兼容性扫描节点。
- 不修改前端页面交互，只保证后端 API 和制品数据可供前端使用。

## Decisions

### 1. 依赖结果只表达“可迁移依赖”

依赖分析结果明细不再生成以下类型：

- `compile_database_define`
- `strace_execve_define`
- `compiler_flag_probe`
- `compile-db`
- `build-ninja`
- 仅表达构建元数据存在性的条目

这些信息可以保留在任务日志、分析 evidence 或内部调试字段中，但不能作为 `dependency_analysis_results` 的列表项，也不能进入迁移输入候选。

理由：本阶段目标是判断目标环境是否满足构建/链接/运行依赖。flag 和宏属于源码兼容性或构建诊断问题，放在依赖结果里会制造噪声。

### 2. ELF/SO 结果优先归一到 provider package

ELF/SO 匹配流程按以下顺序处理：

```text
source ELF/SO path / NEEDED / SONAME
        │
        ▼
source provider resolver
  - rpm -qf / dpkg-query -S / 包数据库 owner
  - SONAME / symlink / 文件名版本 / readelf 版本 evidence
        │
        ▼
normalized dependency identity
  - package name
  - library stem
  - soname
  - version evidence
        │
        ▼
target provider resolver
  - installed packages
  - repository packages
  - repository provides / whatprovides
  - alias / normalized package name
        │
        ▼
version relation + risk level
```

如果源侧能找到 owner package，则以源 package 名和版本作为主匹配身份；ELF/SO 文件名、SONAME、路径只作为 evidence。这样 `libdnf.so.2`、`libfuse.so.2.9.9` 这类库会优先落到对应包，而不是只展示裸库。

如果源侧找不到 owner package，才使用 SONAME、库文件名、文件版本、路径线索尝试建立目标 provider 匹配。

### 3. 版本关系和风险等级采用固定规则

风险映射不由模糊置信度决定，而由源/目标 provider 和版本关系决定：

| 场景 | versionRelation | riskLevel |
| --- | --- | --- |
| 源有包，目标有包，大版本一致 | `SAME_MAJOR` | `INFO` |
| 源有包，目标有包，目标版本更高 | `TARGET_NEWER` | `LOW` |
| 源有包，目标有包，目标版本更低 | `TARGET_OLDER` | `HIGH` |
| 源无包，但源侧能检测版本，目标有对应包版本 | `TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED` | `MEDIUM` |
| 源无包，且目标无可确认版本 | `NO_TARGET_VERSION_FOUND` | `CRITICAL` |

大版本比较需要先使用 rpm/deb 版本解析；无法解析时使用宽松语义版本解析；仍无法解析时降级为 evidence 不足，不得误判为 `INFO`。

### 4. 结果字段采用 evidence 扩展，避免立即大规模 schema 迁移

如果现有 `dependency_analysis_results` 已有依赖类型、名称、版本、目标匹配状态、风险等级、位置标签、建议和 evidence JSON，本 change 优先扩展 evidence JSON，不强制新增大量列。

建议 evidence 至少包含：

- `sourceLibraryPath`
- `sourceLibraryName`
- `sourceSoname`
- `sourceOwnerPackage`
- `sourceOwnerVersion`
- `sourceOwnerSource`
- `sourceVersionEvidence`
- `targetProviderPackage`
- `targetProviderVersion`
- `targetProviderSource`
- `versionRelation`
- `riskMappingRule`
- `matchEvidence`
- `evidencePaths`

列表中常用字段继续落到现有列：

- `dependencyType=LIBRARY` 或 `PACKAGE`
- `dependencyName=<sourceOwnerPackage 或 library name>`
- `dependencyVersion=<sourceOwnerVersion 或 sourceVersionEvidence>`
- `targetMatchStatus=<versionRelation 或 provider status>`
- `riskLevel=<映射结果>`
- `locationLabel=package:<name@version>` 或 `lib:<soname-or-path>`

### 5. 去重聚合以 provider 级别为主

同一个 source package 可能提供多个 SO，同一个 target package 也可能通过多个 provides 命中。列表展示需要按以下 key 聚合：

```text
sourceOwnerPackage + sourceOwnerMajorVersion + targetProviderPackage + targetProviderMajorVersion + versionRelation
```

源侧无 owner package 时使用：

```text
libraryStem + sourceVersionEvidence + targetProviderPackage + targetProviderMajorVersion + versionRelation
```

聚合结果保留代表性 locationLabel，详情 evidence 中保留所有命中的源路径、SONAME、target provides 证据。

## Risks / Trade-offs

- [Risk] 源侧 owner package 解析依赖远端包管理器能力，部分手动安装文件无法归属。  
  → Mitigation: 无 owner 时进入 source-unowned 流程，记录版本证据来源，目标有 provider 时映射为 `MEDIUM`。

- [Risk] 不同发行版包名不一致导致匹配失败。  
  → Mitigation: 复用现有 alias/normalized package 能力，并允许通过 SONAME/library stem/provides 做补充匹配。

- [Risk] rpm/deb 版本格式复杂，简单字符串比较会误判。  
  → Mitigation: 优先使用包管理器语义版本解析；无法解析时使用宽松 major 提取，并在 evidence 中标记解析方式。

- [Risk] 去掉 flag/macro 结果后，某些构建问题暂时缺少展示入口。  
  → Mitigation: 保留原始 evidence 和日志，后续放入源码兼容性扫描或构建诊断节点。

## Migration Plan

1. 修改依赖结果生成逻辑，过滤 flag/macro/build-metadata 类型结果项。
2. 增加源侧 provider 解析和目标侧 provider 版本匹配。
3. 调整 HTML/JSON 报告和迁移输入展示字段。
4. 补充单元测试、E2E 和真实项目验证。
5. 旧数据不做数据库迁移清理；新分析任务生成新格式结果。

## Open Questions

- 是否需要在后续单独建立“源码宏/编译参数兼容性扫描”能力。目前本 change 不处理。
- 是否需要为跨发行版包名 alias 建立可维护的管理 API。目前先复用已有 alias/规范化能力。
