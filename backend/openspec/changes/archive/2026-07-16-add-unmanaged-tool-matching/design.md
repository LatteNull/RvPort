## Context

当前环境采集已经记录基础工具版本，并尝试通过 `rpm -qf` 或 `dpkg-query -S` 将工具路径映射到 owner package。这个模型能覆盖通过包管理器安装的工具，例如 `gcc`、`java`、`javac`，但不能完整表达源码安装或手工安装工具。

典型场景：

```text
source x86:
  TOOL gcc
  version = gcc 12.x
  ownerPackage = gcc

target riscv:
  TOOL gcc
  version = gcc 14.x
  toolPath = /opt/gcc-14/bin/gcc
  ownerPackage = null
```

目标环境已经存在可执行 `gcc`，但它不是包管理器安装。这个结果不应被判断为 `SOURCE_BUILD_REQUIRED`；同时也不能当作 `LOW` 风险，因为它缺少包管理器可追踪性、升级/回滚来源和依赖关系。

## Goals / Non-Goals

**Goals:**

- 采集 package-managed 与 unmanaged 工具的安装来源。
- 对 owner package 不存在但命令可执行的工具保留 `TOOL` 组件记录。
- SBOM 分析优先使用目标已安装工具事实，再考虑目标仓库候选。
- 支持同名工具版本匹配，例如 `gcc 12` -> `gcc 14`。
- unmanaged 工具命中时输出 `TARGET_PRESENT`，但风险为 `MEDIUM`。
- 在 metadata 中保留 `toolPath`、`installOrigin`、`providerScanner`、`versionMajor`、`versionText`，方便前端审计。

**Non-Goals:**

- 不递归扫描 `/opt`、`/usr/local` 或用户目录下所有可执行文件。
- 不判断工具链 ABI 或编译行为完全兼容。
- 不引入新的数据库表。
- 不把 unmanaged 工具自动降为 `LOW` 风险。
- 不为每类工具维护大量手写版本兼容矩阵。

## Decisions

### 1. 工具采集以 PATH 可见命令为边界

MVP 只采集当前内置工具列表中通过 `command -v <tool>` 可见的命令，例如 `gcc`、`g++`、`make`、`cmake`、`python3`、`java`、`javac`、`mvn`。

不扫描未进入 PATH 的 `/opt/gcc-14/bin/gcc`。原因是全盘扫描容易带来性能和权限问题，也可能误读用户私有目录。后续如需要，可以单独增加“自定义工具路径”配置。

### 2. owner 查询失败不等于工具不存在

`TOOL_VERSION` 表达命令可执行事实，`TOOL_PROVIDER` 表达 owner package 归属事实。二者不能绑定成“必须同时存在”。

当 `command -v gcc` 成功但 `rpm -qf` / `dpkg-query -S` 无法归属时：

```text
componentType = TOOL
source = TOOL_VERSION
metadata.installOrigin = unmanaged | unknown
metadata.providerScanner = none
metadata.ownerPackage = null
metadata.toolPath = <real path>
metadata.versionText = <first line of --version>
metadata.versionMajor = <parsed major>
```

### 3. installOrigin 推断规则

安装来源按以下顺序判断：

```text
ownerPackage exists
  -> package
ownerPackage missing and path starts with /usr/local, /opt, /home/*/.local, /root/.local
  -> unmanaged
ownerPackage missing
  -> unknown
```

`unknown` 仍保留工具事实，但风险不得低于 `MEDIUM`。

### 4. 分析器优先判断目标已安装工具

SBOM 分析顺序应保持：

```text
target installed package/library/tool
  -> target repository package/provides
  -> no candidate / manual
```

对于 `TOOL`：

```text
owner package exact/normalized match
  -> exact tool name match
  -> tool family/version match
  -> weak name fallback
```

目标工具命中但来源为 unmanaged/unknown 时，结果使用：

```text
replacementStatus = TARGET_PRESENT
matchType = tool_name_version
risk = MEDIUM
```

### 5. 同名工具版本匹配不做强兼容承诺

`gcc 12` 和 `gcc 14` 同名且同工具族，但主版本不同。分析器只能表达“目标环境存在同类可执行工具”，不能表达“完全兼容”。

建议输出：

```text
status = TARGET_PRESENT
matchType = tool_name_version
risk = MEDIUM
suggestion = 目标环境存在同名工具，但版本或安装来源不同，需要确认兼容性
```

如果主版本相同且目标工具为 package-managed，可以保持 `LOW` 风险。

## Risks / Trade-offs

- [Risk] 只检查 PATH 可见工具，可能漏掉未加入 PATH 的源码安装工具。→ Mitigation: MVP 保持安全边界，后续通过环境配置增加自定义工具路径。
- [Risk] 版本字符串格式差异大，主版本解析可能不稳定。→ Mitigation: 只提取首个数字作为 `versionMajor`，原始 `versionText` 永久保留用于审计。
- [Risk] unmanaged 工具可能不可复现或依赖缺失。→ Mitigation: 命中时使用 `MEDIUM` 风险，不标记为 `LOW`。
- [Risk] 同名工具不一定语义完全一致。→ Mitigation: 仅对内置工具白名单使用同名工具匹配，且不同主版本或 unmanaged 来源需要人工确认兼容性。
- [Risk] 前端状态聚合可能把 `TARGET_PRESENT` 都当作低风险。→ Mitigation: risk 和 matchType 必须明确输出，前端聚合应按 risk 展示。

## Migration Plan

1. 扩展 `SshRuntimeService` 工具采集输出和解析，保留 owner 查询失败的工具记录。
2. 为工具 metadata 增加 `installOrigin`、`versionText`、`versionMajor`、`providerScanner`、`toolPath`。
3. 扩展 SBOM analyzer 的工具匹配逻辑，支持 installed target tool 的同名版本匹配。
4. 补充 Java 和 analyzer 测试。
5. 使用真实 x86/RISC-V 环境复跑至少一组工具对比记录。

## Open Questions

- 是否需要在后续 change 中允许用户为某个环境配置额外工具扫描路径。
- 对 `gcc`、`g++`、`cc`、`c++` 这类别名是否需要建立 tool family 映射，目前先只做同名匹配。
