## Context

当前依赖分析会在分析前刷新源环境和目标环境快照，再基于构建日志、`compile_commands.json`、strace 观测、ELF 依赖和环境组件清单生成依赖结果。openEuler 24.03 LTS-SP2 RISC-V 极简容器暴露出两个问题：

- 环境里实际存在 `glibc`、`libgcc`、`gcc` 及其 repo 元数据，但容器缺少 `findutils` 和 `binutils`，导致 `.so` 文件扫描和 ELF metadata 采集不完整。
- `compile_commands.json` / strace / linker flag 解析出的 `-lc`、`-lgcc_s` 走 `matchLibrary`，没有像 ELF needed 路径一样使用源侧 owner package 做目标侧 provider package 回退。

这会导致 `libc.so`、`libgcc_s.so` 在 SP2 上被误判为缺失。实际应判定为目标环境存在对应 provider，并根据源/目标 provider package 的主版本关系给出风险等级。

## Goals / Non-Goals

**Goals:**

- 源环境和目标环境刷新采集时都检测采集辅助工具缺失。
- 对源环境和目标环境缺少 `find`、`readelf`、`objdump` 等辅助工具的情况，按包管理器能力尝试受控自动安装。
- 工具仍缺失或安装失败时，快照中必须记录 warning，不能静默生成空库清单。
- `.so` 扫描应在 `find` 不可用时具备标准目录降级策略。
- `-lc`、`-lgcc_s` 等链接库应使用 provider-aware 匹配，能从源侧 owner package 回退到目标侧同名包、规范化包名或库别名包。
- 保证 `libc -> glibc`、`libgcc_s -> gcc/libgcc` 这类基础库映射在目标 provider 匹配中生效。

**Non-Goals:**

- 不改变前端页面和交互。
- 不引入跨发行版包名映射体系。本次仍默认源环境和目标环境属于同类发行版。
- 不把缺少采集辅助工具视为环境连接失败；这是采集质量问题，应体现在快照 warning 和分析证据中。
- 不恢复已经废弃的 SBOM 分析主流程。

## Decisions

### 源/目标环境均执行采集辅助工具预检与安装尝试

依赖分析前刷新源环境和目标环境时，在实际采集命令前加入辅助工具预检：

- 基础扫描：`find`，对应 RPM/DNF 包通常为 `findutils`。
- ELF metadata：`readelf` 或 `objdump`，对应 RPM/DNF 包通常为 `binutils`。
- provider 查询：RPM 环境依赖 `rpm`，repository 查询依赖 `dnf/yum repoquery` 能力。
- 源环境构建观测：`strace` 和 `bear`，用于采集 execve 事实和生成 `compile_commands.json`。

如果缺失且环境可通过包管理器安装，后端应尝试安装必要工具。安装命令必须受控，只安装固定 allowlist 包，例如 RPM/DNF 环境中的 `findutils`、`binutils`、`strace`、`bear`。安装失败时记录 warning 并继续采集可获取的信息。

理由：源环境既参与 source owner package 和版本判断，也负责构建观测。如果源环境缺少 `findutils/binutils`，会导致 owner/ELF 证据缺失；如果缺少 `strace/bear`，会导致链接参数、实际执行工具和 compile database 证据不足。

目标环境不需要强制安装 `strace/bear`，除非后续节点在目标环境执行构建观测。本 change 中目标环境只要求补齐 provider 解析和库扫描所需工具。

### `.so` 扫描不能静默依赖 `find`

当前脚本使用 `find "$libdir" ... 2>/dev/null`，在 `find` 不存在时会直接得到空结果。新逻辑需要：

- 在脚本开始处输出 scanner availability。
- `find` 不存在时输出明确 warning。
- 对 `/lib`、`/lib64`、`/usr/lib`、`/usr/lib64`、`/usr/local/lib` 使用 shell glob 或固定深度 fallback 采集常见 `.so` 文件。
- 对符号链接目录和符号链接库文件保持可见，至少要保留路径和 owner package 证据。

### 链接库统一走 provider-aware 匹配

`compile_commands.json`、strace execve 和 linker flag 中提取出的链接库不应只调用 `matchLibrary`。这些路径应复用或抽取 `matchProvider` 语义：

1. 先尝试目标环境 installed library / repository provide。
2. 如果目标库证据缺失，但源侧能解析出 owner package，则回退到目标环境同名包。
3. 同名包未命中时，尝试规范化包名和基础库别名。
4. 命中后基于源/目标 provider package 主版本关系映射 `SAME_MAJOR`、`TARGET_NEWER`、`TARGET_OLDER`、`NO_TARGET_VERSION_FOUND`。

### 基础库别名属于 provider 匹配的一部分

`libc.so` / `libc.so.6` 应能映射到 `glibc`，`libgcc_s.so` 应能映射到 `gcc` 或 `libgcc`。这个别名不应只用于扫描展示，而应直接参与目标 provider package 查找。

## Risks / Trade-offs

- 远程自动安装可能改变测试环境状态 → 限定为固定 allowlist 采集辅助工具，并在日志和快照 warning 中记录安装动作。
- 部分生产环境不允许自动安装 → 安装失败不阻断采集，继续落库已有证据，并明确 warning。
- shell glob fallback 不如 `find` 完整 → fallback 只作为极简环境兜底，正常环境仍优先使用 `find`。
- 包名回退默认同类发行版 → 跨发行版映射暂不处理，避免把软件迁移问题扩展成操作系统迁移问题。
