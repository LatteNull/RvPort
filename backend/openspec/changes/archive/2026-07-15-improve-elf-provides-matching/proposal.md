## Why

当前 SBOM provider matching 主要依赖包名、文件名和归一化 `.so` 名称，容易把不同 SONAME/ABI 的库弱化为同一个候选，也可能漏掉“包通过 ELF capability 提供该库”的证据。需要把环境采集和分析器匹配提升到 ELF metadata 与 provides capability 层级，降低误判和漏判。

真实环境验证后又暴露出一个关联性问题：源侧很多 `.so` 是由 rpm/dpkg package 安装出来的。如果 owner package 在目标 RISC-V 环境或目标软件源中已经有可用候选，那么这些 `.so` 不应再作为独立迁移问题出现；它们应作为 package 迁移的 evidence/covered item。否则结果会被大量 library 噪声淹没，并且可能把 package 升级问题误拆成多个 library 问题。

进一步真实验证发现，采集端对 package、repository package、library/native 和 provider 记录存在固定数量截断，导致 `java-17-openjdk-*`、`libdnf`、`fuse` 等真实存在的源/目标包没有进入分析输入；同时 `java` 这类工具只记录命令版本，没有记录命令路径对应的 owner package/version，导致工具被误判为需要源码构建。全量 SBOM 分析不能依赖人为 `head` 上限，需要由远端命令输出完整数据，由任务超时和运行环境负责控制耗时。

## What Changes

- 环境采集对源 x86 和目标 RISC-V 的 ELF/native 文件提取 `SONAME`、`NEEDED`、ELF machine、ELF class 等非敏感 metadata。
- x86 和 RISC-V 两侧都尝试记录 installed package owner 与 installed provides/capability evidence。
- RISC-V 目标仓库查询优先使用 exact SONAME/capability，再 fallback 到 normalized library name 和 package candidate。
- SBOM analyzer 匹配优先级调整为 exact ELF capability/SONAME 优先，之后才是 owner package、repository provides、normalized library、weak name。
- SBOM analyzer 需要先做 package-level replacement，再用 owner package 覆盖关系消解 library/native 结果。
- 当 library/native 的 `ownerPackage` 已有 `TARGET_PRESENT`、`DIRECT_AVAILABLE` 或 `UPGRADE_AVAILABLE` 的 package 结果时，该 library/native 应标记为 `coveredByPackage`，不再作为独立替代候选展示。
- library/native 本体匹配不得把 `elfNeeded`/`requiredCapabilities` 里的依赖库当作替代候选；这些字段只能作为依赖 evidence 或后续缺失依赖分析输入。
- 分析结果 evidence 需要表达匹配来源、confidence、SONAME、needed、ELF arch/class 和 repository provides 证据。
- 环境采集不再对 package、repository package、library/native、provider 等记录做固定数量截断，确保全量分析。
- `TOOL` 组件需要记录命令真实路径、owner package、owner version、owner arch 和 provider scanner，`java`/`javac` 这类工具应能映射到 `java-17-openjdk-headless`/`java-17-openjdk-devel` 等真实包。
- replacement candidate metadata 需要保留源侧 owner package/version/arch，静态报告和 API evidence 能审计 x86 源包版本。
- 补齐单元测试、analyzer 测试和 API/E2E 或真实验证脚本的覆盖。
- 不做完整 ABI diff、符号级兼容性判断或大型 SBOM 标准格式转换。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `project-source-environment`: 环境采集需要提取 ELF metadata，并在源/目标两侧记录 installed provides 与 repository provides 证据。
- `sbom-analysis-runtime`: SBOM 分析需要优先使用 package-level replacement 与 exact ELF capability/SONAME 匹配，并区分 package-covered、exact、arch-normalized、library-normalized 和 weak evidence 的置信度。

## Impact

- 影响 `SshRuntimeService` 的环境采集脚本、采集解析和 `environment_components.metadata` 写入。
- 影响环境采集输出规模：全量 package/repository/library/provider 记录可能显著增加任务耗时和数据库写入量。
- 影响 `tools/sbom-analyzer` 的 index/lookup key、candidate evidence、confidence 和 warning 生成。
- 影响 `tools/sbom-analyzer` 的结果归并逻辑：package 结果需要覆盖其 owner library/native，减少独立 library 噪声。
- 影响 SBOM 组件结果 API 的展示语义：前端应优先展示 package 级结果，并可在明细中查看被 package 覆盖的 library/native evidence。
- 影响 SBOM analyzer 测试、Java 环境采集测试、SBOM runtime 测试和 E2E/真实验证记录。
- 不新增数据库表；继续使用 `environment_components.metadata`、`sbom_components.metadata` 和 `replacement_candidates.metadata` 承载新证据。
