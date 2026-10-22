## Context

当前环境采集会发现 `.so`/native 文件、查询 owner package，并在 RISC-V 侧采集 repository package/provides。SBOM analyzer 主要使用包名、owner package、repository provide 文件名、normalized library name 和 weak name 做匹配。

这个模型仍有两个问题：

- `libfoo.so.1` 与 `libfoo.so.2` 可能被统一成 `libfoo.so`，导致 ABI 风险被低估。
- repository provides 只表达“某包可能有某路径/文件”，没有明确表达 ELF SONAME/capability、ELF 架构、class 和 `NEEDED` 依赖。
- library/native 与 package 结果没有做覆盖关系消解。真实环境中大量 `.so` 来自已安装 package；如果 owner package 已经能在目标侧安装或升级，这些 `.so` 不应再作为独立迁移问题出现。
- 当前 ELF capability 匹配存在把 `NEEDED` 依赖库误当成当前 library 替代候选的风险。例如 `libfoo.so` 依赖 `libc.so.6`，不能说明 `libc.so.6` 是 `libfoo.so` 的替代品。
- 当前采集存在固定数量截断：installed package、repository package、library/native、provider 和解析记录都可能被裁掉。真实验证中 `java-17-openjdk-*`、`libdnf`、`fuse` 因此没有稳定进入分析输入。
- 当前 `TOOL` 组件只记录命令版本，不记录命令路径对应的 owner package/version。`java` 会显示 `openjdk 17...`，但 analyzer 无法知道它来自 `java-17-openjdk-headless`。

本 change 将匹配依据提升到 ELF metadata 和 capability 层级，但仍保持 MVP 边界：只做元数据和 capability 匹配，不做符号级 ABI diff。

## Goals / Non-Goals

**Goals:**

- 在源 x86 和目标 RISC-V 环境采集 ELF metadata：`soname`、`needed`、`elfMachine`、`elfClass`。
- 在源/目标两侧记录 installed owner package 和 installed provides/capability evidence。
- 在目标仓库侧优先查询 exact SONAME/capability provides。
- 在 analyzer 中引入 ELF capability key，优先级高于 normalized library name。
- 在 analyzer 中先完成 package-level replacement，再根据 `ownerPackage` 将 package 已覆盖的 library/native 从独立候选中消解。
- 对 library/native 本体匹配禁止使用 `elfNeeded`/`requiredCapabilities` 作为替代候选 key；这些字段只作为依赖 evidence。
- 在结果 metadata 中清楚表达 exact、arch-normalized、library-normalized、weak evidence 的差异。
- 在结果 metadata 中清楚表达 `coveredByPackage`、`coveredByPackageStatus`、`coveredByPackageCandidate` 等覆盖证据。
- 对 package、repository package、library/native、provider 记录进行全量采集和全量解析，不设置人为条数上限。
- 对工具命令采集 `TOOL_PROVIDER` evidence，写入 `ownerPackage`、`ownerVersion`、`ownerArch`、`providerScanner` 和 `toolPath`。
- 在 replacement candidate metadata 中保留 `sourceOwnerVersion` 与 `sourceOwnerArch`，用于审计 x86 源侧包版本。
- 补齐 Java、analyzer 和 E2E/真实验证覆盖。

**Non-Goals:**

- 不做完整 ABI diff。
- 不解析函数级符号表或判断符号兼容性。
- 不新增数据库表。
- 不要求远程环境安装额外重型工具；缺少 `readelf`/`objdump` 时应降级并记录 warning。
- 不在本 change 中实现完整依赖闭包分析。`NEEDED` 仅作为 evidence，不单独输出缺失依赖列表。

## Decisions

### 1. ELF metadata 存入 `environment_components.metadata`

不新增表。每个 ELF/native component 的 metadata 中增加：

- `elfSoname`
- `elfNeeded`
- `elfMachine`
- `elfClass`
- `elfScanner`
- `providesCapabilities`
- `requiredCapabilities`

这样可以复用现有 `environment_components` 和 SBOM analyzer input/export 逻辑。

### 2. 采集脚本优先使用 `readelf`，fallback 到 `objdump`

`readelf -d` 可解析 `SONAME` 和 `NEEDED`，`readelf -h` 可解析 machine/class。若 `readelf` 不存在，再尝试 `objdump -p` 提取 `SONAME`/`NEEDED`。两个工具都不可用时记录 parse warning，不阻断基础环境采集。

### 3. capability key 不抹掉 SONAME 主版本

`libssl.so.3` 的 exact capability key 应保留为 `elf:soname:libssl.so.3`。`libssl.so` 只能作为 weaker fallback key。这样 exact SONAME 命中才是 high confidence，normalized library 命中最多 medium。

匹配优先级：

```text
package-level exact / repository package result
  > owner package covers library/native
  > exact ELF SONAME / provides capability
  > repository provides exact capability
  > arch-normalized capability
  > normalized library name
  > weak name
```

### 4. source 和 target 都采集 provides

只在 RISC-V 目标侧查 repository provides 不够。源 x86 也需要 installed provides/capability，用于表达“源组件实际需要或提供的 ABI”。目标侧再用 installed provides 与 repository provides 来匹配。

### 5. 采集不做固定数量截断

SBOM 分析需要完整 package 和库证据，采集脚本和 Java 解析层不再使用 `head -n 20/50/80` 或 stream `limit(...)` 裁剪结果。运行边界由任务 timeout、SSH 命令 timeout 和远端包管理器自身控制。

repository evidence 只在目标 RISC-V 环境采集。源 x86 需要全量 installed package、library/native、owner package 和 ELF metadata，但源侧 repository provides 不会入库参与分析，逐库查询只会增加耗时。

目标 RISC-V 必须全量采集 repository package，用于判断 `java-17-openjdk-*`、`libdnf`、`fuse` 等可安装包。repository provides 只允许使用包管理器支持的批量方式采集；禁止对每个 `.so` 逐个执行 `repoquery --whatprovides`，否则全量采集会被远端仓库查询拖死。

全量采集的直接影响是：

- 数据库中 `environment_components` 记录数会增加。
- repository query 在包源较大的环境中会更慢。
- 分析结果更接近真实状态，避免因采集缺失误判为 `SOURCE_BUILD_REQUIRED` 或 `MANUAL_CONFIRM_REQUIRED`。

### 6. TOOL provider evidence

工具命令在采集版本后，需要通过 `command -v`、`readlink -f` 和 rpm/dpkg owner 查询生成：

```text
TOOL_PROVIDER=<tool>|<realPath>|<ownerPackage>|<ownerVersion>|<ownerArch>|<scanner>
```

写入 `TOOL` 组件 metadata 后，analyzer 可以通过 `ownerPackage` 和 `normalizedPackage` 匹配目标侧 package。例如：

- `java` -> `java-17-openjdk-headless`
- `javac` -> `java-17-openjdk-devel`

### 7. repository provides 分两类记录

- `REPOSITORY_PROVIDE`：仓库可提供的文件或 capability。
- metadata 中标记 `provideKind=ELF_SONAME|PATH|PACKAGE` 和 `queryValue`。

这样 analyzer 能区分 exact SONAME 查询和普通路径/文件名查询。

### 8. package 与 library/native 的覆盖消解

Analyzer 应分两阶段处理：

1. **package-level pass**
   - 先处理所有 source `PACKAGE` 和 `TOOL` 组件。
   - 生成 package 的 replacement candidate，包括 `TARGET_PRESENT`、`DIRECT_AVAILABLE`、`UPGRADE_AVAILABLE`、`SOURCE_BUILD_REQUIRED` 等状态。
   - 建立 `packageResultByName` / `packageResultByNormalizedName` 索引，用于后续 owner package 消解。

2. **library/native pass**
   - 对每个 source `LIBRARY` / `NATIVE` 组件读取 `metadata.ownerPackage` 或 `metadata.normalizedPackage`。
   - 如果 owner package 在 package-level pass 中存在可迁移结果：
     - 该 library/native 结果应标记为 package-covered。
     - `replacementStatus` 可使用 `TARGET_PRESENT` / `DIRECT_AVAILABLE` / `UPGRADE_AVAILABLE` 跟随 package 结果，或使用展示层可识别的 metadata 标志。
     - metadata 必须包含：
       - `coveredByPackage=true`
       - `coveredByPackageName`
       - `coveredByPackageCandidate`
       - `coveredByPackageStatus`
       - `coveredByPackageMatchType`
     - 默认组件列表应能够过滤或折叠这类 covered library/native，避免前端看到大量重复 library 问题。
   - 只有 owner package 不存在、owner package 不可迁移、或 owner package evidence 缺失时，才进入 ELF/provides/library fallback 匹配。

### 9. `NEEDED` / required capabilities 只作为依赖 evidence

`elfNeeded` 和 `requiredCapabilities` 表达的是当前 ELF 文件运行时需要的依赖，不表达当前 ELF 文件由谁替代。因此：

- source library/native lookup key MUST NOT 使用 `elfNeeded` 或 `requiredCapabilities` 生成替代候选 key。
- target installed/repository index MAY 继续记录自己的 provides capability，用于匹配“目标是否提供某个 SONAME/capability”。
- 如果后续要分析缺失依赖，应作为单独的 dependency analysis 输出，不和 component replacement 混在一起。

这可以避免 `libfoo.so -> libc.so.6` 这类错误候选。

### 10. 元数据包与架构专用包的误报降级

部分源侧记录不是普通可迁移软件包，或只适用于 x86 启动链。Analyzer 应在匹配失败后降级处理这些已知类别，避免误报为 `SOURCE_BUILD_REQUIRED`：

- `gpg-pubkey` 是 RPM 导入公钥记录，不代表需要迁移或构建的软件包。结果标记为 `METADATA_ONLY`，风险为 `LOW`。
- `grub2-efi-*` 中包含 `x64`、`ia32`、`x86_64`、`amd64`、`i386`、`i686` 等架构 token 时，应尝试替换为目标 `riscv64` 后查询目标仓库包，例如 `grub2-efi-x64-modules` -> `grub2-efi-riscv64-modules`。
- 架构 token 替换不只用于目标仓库，也用于目标已安装组件。如果源侧 `vendor-devkit-x86_64` 与目标侧已安装 `vendor-devkit-riscv64`，结果应为 `TARGET_PRESENT`，而不是继续进入源码构建或人工确认。
- `grub2-pc` / `grub2-pc-*` 属于 x86 BIOS/PC 启动链包，在 RISC-V 目标上没有同名包不应直接视为源码构建缺口。结果标记为 `NOT_APPLICABLE_ARCH`，风险为 `LOW`。

这些规则只处理明确的元数据记录和架构 token，不引入大规模手写包名映射。后续如果前端提供聚合和手动忽略能力，可以继续在展示层处理更细的例外项。

## Risks / Trade-offs

- [Risk] 部分远程环境没有 `readelf` 或 `objdump`。→ Mitigation: 降级到现有 filename/owner package matching，并记录 warning。
- [Risk] 仓库 provides 查询在不同包管理器输出格式差异大。→ Mitigation: 先支持 rpm/dnf/yum 和 apt-file 的稳定字段，无法解析时保留原始安全摘要与 warning。
- [Risk] exact SONAME 更严格，可能让一些原本 DIRECT/UPGRADE 变为 MANUAL_CONFIRM。→ Mitigation: 保留 normalized fallback，但降低 confidence，避免误判为强匹配。
- [Risk] 远程采集时间增加。→ Mitigation: 不再用条数截断牺牲正确性，依赖任务 timeout、SSH timeout、包管理器 timeout 和后续分页展示控制成本。
- [Risk] 逐库 repository provides 查询在真实仓库上不可接受。→ Mitigation: 全量 package 作为主匹配证据；repository provides 只使用批量采集方式，逐库按需查询留到后续单独能力。
- [Risk] package 覆盖消解可能隐藏真正需要单独处理的插件 `.so`。→ Mitigation: 只在存在明确 `ownerPackage` 且 package 结果可迁移时折叠；metadata 保留 covered 明细，API 可按参数展开。
- [Risk] 移除 `requiredCapabilities` 作为替代 key 后，部分过去的 LOW 风险结果会变为 MANUAL_CONFIRM。→ Mitigation: 这是正确的保守行为；依赖缺失应后续单独分析。

## Migration Plan

1. 扩展采集脚本和解析逻辑，写入 ELF metadata 与 provides capability。
2. 移除采集脚本和 Java 解析层的固定条数截断。
3. 对 TOOL 组件增加 provider evidence 和 owner package/version metadata。
4. 扩展 analyzer key/index/lookup 和 candidate metadata。
5. 扩展 analyzer 的 package-first 两阶段处理和 owner package 覆盖消解。
6. 禁止 source library/native 使用 `elfNeeded` / `requiredCapabilities` 作为替代候选 key。
7. 补充测试覆盖 exact SONAME、version mismatch、missing readelf fallback、repository provides exact query、package-covered library、dependency-not-replacement、tool owner package matching。
8. 运行现有 Maven、analyzer 和 SBOM validation/E2E 检查。

## Open Questions

- RISC-V 仓库中 `repoquery --whatprovides` 对 `libfoo.so.N()(64bit)` 的可用性需要在真实环境继续验证。
- covered library/native 在 API 默认列表中应直接过滤，还是保留但由前端折叠展示。
