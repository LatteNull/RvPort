## Context

当前 `ENV_COLLECT` 会采集已安装包、`.so` / native 文件、基础工具版本，并在 RISC-V 目标环境尝试采集仓库可用包和 provides 能力。现有实现存在三个主要缺口：

- 源侧 x86 的 `.so` 文件没有稳定记录 owner package，分析器只能基于库名弱匹配。
- 目标侧 RISC-V 仓库查询依赖已有 metadata，未先刷新或校验 metadata，容易得到空仓库候选。
- x86/amd64 架构 token 可能出现在路径、文件名或包名中，直接拿原始名称查询 RISC-V 仓库会漏匹配。

这个 change 的目标是提升 SBOM 替代判断的证据质量，而不是扩大远程环境管理范围。

## Goals / Non-Goals

**Goals:**

- 在 x86 和 RISC-V 环境采集中记录 `.so` / native 文件的 provider/owner package 证据。
- 在 RISC-V 仓库候选查询前执行受控 metadata refresh 或 metadata 可用性检查，并记录状态。
- 为库名、路径和包名生成架构归一化候选，用于跨架构查询。
- 让 SBOM 分析器优先使用 provider、whatprovides、normalized name 和 confidence 生成替代候选。
- 保证仓库增强信息失败时不阻断基础环境快照。

**Non-Goals:**

- 不引入 sudo 或提权执行。
- 不要求完整枚举远程仓库所有 provides 能力。
- 不改变 SBOM 分析器直接访问后端数据库或远程 SSH 的边界。
- 不新增通用 artifact 存储。
- 不实现最终人工确认工作流或 issue 联动。

## Decisions

### 1. provider 采集放在环境采集阶段

环境采集已经拥有远程执行上下文、包管理器探测和快照写入能力。`.so` owner package 属于环境事实，应保存在 `environment_components.metadata`，而不是由 SBOM 分析器事后猜测。

备选方案是让 SBOM 分析器根据 `.so` 名称反推 provider，但分析器不连接远程环境，也不读取包管理数据库，证据会更弱。

### 2. x86 和 RISC-V 都采集 provider

x86 源侧 provider 用于回答“这个源侧库实际来自哪个包”；RISC-V 目标侧 provider/whatprovides 用于回答“目标侧哪个包能提供这个库”。两侧都采集后，分析器可以从文件名匹配升级为包归属和 provides 证据匹配。

### 3. metadata refresh 是增强步骤，不阻断基础快照

RISC-V 仓库 metadata 刷新可能因为 DNS、源 404、网络超时或 repo 配置问题失败。基础快照仍应保存 OS、已安装包、工具版本和已安装库；仓库候选缺失通过 `parseWarnings` 和 `repositories` 摘要表达。

### 4. 归一化只生成候选，不改写事实

原始文件名、路径和包名仍作为事实保存。架构归一化只生成 `normalizedName`、`queryPatterns` 和 `packageCandidates`，并在匹配结果中记录 evidence 和 confidence。这样可以避免把 `libfoo-x86_64.so` 错误地当作真实 `libfoo.so`。

### 5. 查询必须受控

远程命令必须设置超时和低重试，不使用 sudo。`dnf/yum makecache`、`repoquery`、`whatprovides` 或等效命令失败时记录 warning。输出数量继续限制，避免单次采集产生过大日志或快照。

## Risks / Trade-offs

- 仓库 metadata refresh 可能慢 → 使用命令超时、包管理器 timeout、低重试和输出上限。
- provider 查询命令在不同发行版差异大 → 先覆盖 rpm/dnf/yum 和 dpkg/apt 常见路径，缺失时记录 warning。
- 架构归一化可能产生误匹配 → 保存原始值、normalized 值、query pattern、confidence 和 evidence，避免静默覆盖事实。
- provides 查询范围过大 → 优先针对源侧库名和归一化候选做定向查询，不要求完整仓库 provides 枚举。
- 远程输出可能包含敏感路径 → 进入任务日志 excerpt、事件和 API 前继续执行脱敏，metadata 中只保存必要摘要。

## Migration Plan

- 不需要数据库结构迁移，优先复用 `environment_components.metadata`、`environment_snapshots.raw_snapshot` 和 `sbom_components.metadata`。
- 更新采集脚本和解析逻辑后，历史快照不会自动补充 provider 信息；新 SBOM 分析应提示旧快照 provider 证据缺失。
- 需要重新采集源/目标环境，才能获得 provider 和 refreshed repository metadata。

## Open Questions

- 是否需要为 apt 系统安装或依赖 `apt-file`，还是只在存在时使用并记录缺失 warning？
- RISC-V 仓库 metadata refresh 是否允许 `dnf makecache --refresh`，还是默认只做 `repoquery` 前的 metadata 校验？
- provider 查询的默认上限应按库数量、总输出行数还是总执行时间控制？
