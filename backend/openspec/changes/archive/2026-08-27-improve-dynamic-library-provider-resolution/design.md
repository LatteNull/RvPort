## Context

依赖分析目前已经从 x86 构建日志中读取 `RVPORT_OBSERVATION elfNeeded` 和 `elfSoname`，并通过 source/target 环境快照做 provider package 匹配。但 `elfNeeded` 只包含被依赖库的 SONAME，例如 `libc.so.6`，不包含 source 环境中实际加载到的文件路径，因此不能稳定执行 `rpm -qf` / `dpkg-query -S` 获取 source owner package。

现有 `TargetCapabilityIndex.matchProvider` 已经支持先按 source owner package 匹配目标包，再按 library/provides 匹配目标库。但 source owner 缺失时会退化为基于 SONAME 的模糊匹配；目标 provides 元数据不完整时，也可能无法定位到目标同名包。

本项目当前边界是“软件迁移”，不是“操作系统迁移”。source 与 target 默认属于同一发行版包生态，包名理论上应一致；跨发行版包名等价推断暂不处理。

## Goals / Non-Goals

**Goals:**

- 为 ELF `NEEDED` 动态库解析 source 侧实际库路径，并采集该路径的 owner package/version。
- 在依赖分析中优先使用解析后的 source owner package/version 计算 provider 版本关系。
- 当目标 SO/provides 匹配失败但 source owner package 已确认时，使用同名/归一化同名 package fallback 匹配目标已安装包或目标软件源包。
- 在 evidence 中明确记录解析方式、fallback 命中方式和风险映射依据，便于审计。

**Non-Goals:**

- 不实现跨发行版 alias，例如 `glibc` 与 `libc6` 的等价推断。
- 不要求依赖分析修复目标环境 repo metadata。
- 不改变现有风险等级定义，只补全证据和匹配路径。
- 不把 source 构建产物自身误判为外部依赖。

## Decisions

### 1. 在构建事实采集阶段解析 NEEDED 库实际路径

构建 wrapper 在输出 `elfNeeded <elfPath> <soname>` 后，额外尝试解析该 SONAME 在 source 环境中的实际文件路径。

推荐解析顺序：

1. `ldconfig -p` 查询 SONAME 对应路径。
2. `ldd <elfPath>` 查询该 ELF 实际运行时解析结果。
3. 基于常见库目录做有限 fallback：`/lib*`、`/usr/lib*`。

解析成功后输出新的结构化观测，例如：

```text
RVPORT_OBSERVATION resolvedNeededLibrary <elfPath>    soname=libc.so.6    path=/lib64/libc.so.6    ownerPackage=glibc    ownerVersion=2.38-...    resolver=ldconfig
```

这样依赖分析不需要猜测 `libc.so.6` 的实际来源，而是直接消费构建事实。

### 2. 依赖分析优先使用 resolvedNeededLibrary 补全 source owner

`DependencyFactExtractor` 应建立 `SONAME + referencing ELF path` 或 `SONAME` 级别的 source library owner index。

优先级：

1. `resolvedNeededLibrary` 中的 owner package/version。
2. `ownerPackage` 对应的仓库内 ELF 文件 owner。
3. source 环境快照中 library metadata 的 owner package/version。
4. SONAME 文件名中的版本证据。

这样 `libc.so.6` 应能生成 `sourceOwnerPackage=glibc`，而不是仅得到 `sourceVersionEvidence=6`。

### 3. 目标 fallback 限定为同发行版包生态

当 source owner package 已确认，target 侧 library/provides 未命中或没有版本证据时，使用 source owner package 进行同名包匹配。

匹配顺序：

1. target installed package exact match。
2. target repository package exact match。
3. target installed/repository package normalized match，归一化仅做架构 token 和常见后缀清理，不做跨发行版 alias。

命中时 evidence 必须包含：

- `matchedBy=source-owner-package-fallback`
- `sourceOwnerPackage`
- `requestedLibrary`
- `targetProviderPackage`
- `targetProviderVersion`
- `samePackageEcosystemAssumed=true`

### 4. 风险仍使用 provider 版本关系

fallback 命中以后不单独定义新风险，而是复用现有版本关系：

- `SAME_MAJOR` -> `INFO`
- `TARGET_NEWER` -> `LOW`
- `TARGET_OLDER` -> `HIGH`
- source 有 owner 但 target 版本不可确认 -> `NO_TARGET_VERSION_FOUND` 或证据不足状态

避免因为 fallback 命中包名就直接判低风险。

## Risks / Trade-offs

- [Risk] `ldconfig` 或 `ldd` 不存在，无法解析实际库路径。
  [Mitigation] 记录 warning 并保留当前 SONAME 匹配路径，不让构建成功变失败。

- [Risk] `ldd` 执行不可信二进制存在安全风险。
  [Mitigation] 优先 `ldconfig -p`；如使用 `ldd`，仅对已构建/已发现 ELF 做有限超时调用，并记录 resolver 来源。实现时可先只用 `ldconfig` 和安全路径扫描，避免扩大风险。

- [Risk] 同名包 fallback 在跨发行版环境下可能误判。
  [Mitigation] 本 change 明确不支持跨发行版迁移；evidence 中标记 `samePackageEcosystemAssumed=true`，后续如支持跨发行版，需要单独设计 alias 体系。

- [Risk] 多个路径提供同一 SONAME。
  [Mitigation] 优先实际引用 ELF 的 `ldd` 结果；无法判定时保留多个候选并降级为人工确认。
