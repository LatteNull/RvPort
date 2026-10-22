## Context

当前 SBOM 分析器只读取 Java 后端导出的 JSON 输入，基于源环境组件、目标已安装组件和目标仓库组件生成替代候选。匹配逻辑已经支持 ELF capability、owner package、repository provides、normalized library 和 weak name，但跨发行版包名差异仍会导致误判。

典型例子是 openEuler 的 `CP1250.so` 归属 `glibc`，而 Bianbu/Debian 目标环境中的同名文件归属 `libc6:riscv64`。这说明目标侧具备同一运行时能力，但当前分析结果仍可能进入 `MANUAL_CONFIRM_REQUIRED`。同时，目标侧文件位于 `/usr/lib/riscv64-linux-gnu/gconv/CP1250.so`，现有系统库扫描深度不足会遗漏这类 multiarch runtime module。

## Goals / Non-Goals

**Goals:**
- 在环境采集中覆盖 Debian/Bianbu multiarch 与 gconv 等运行时模块目录。
- 在 SBOM 分析中自动发现 source owner package 与 target owner package 的等价候选关系。
- 将等价候选关系作为本次分析的匹配证据，降低错误的人工确认项。
- 将自动发现的关系沉淀为可查询、可复用、可审核的 observation。
- 为后续人工批准/拒绝 alias 关系预留状态字段和查询基础。

**Non-Goals:**
- 不在本 change 中实现完整的人工审核管理页面。
- 不把自动发现的关系无条件升级为全局强规则。
- 不实现复杂的跨发行版版本排序算法；版本兼容判断只在已存在证据基础上保留原始版本与 normalized upstream version 供展示和后续增强。
- 不改变 SBOM 分析器独立运行的原则；分析器仍不直接连接数据库、不处理凭据。

## Decisions

### 1. 系统库扫描深度调整为 4

系统库目录扫描从 `-maxdepth 2` 调整为 `-maxdepth 4`，覆盖如下目录形态：

```text
/usr/lib/riscv64-linux-gnu/gconv/CP1250.so
/usr/lib/<multiarch>/gio/modules/*.so
/usr/lib/<multiarch>/<runtime-module-dir>/*.so
```

扫描仍限制为系统库目录和 `.so*` 文件：

```bash
find "$libdir" -maxdepth 4 -type f -name '*.so*'
```

`/opt` 和 `/usr/local/bin` 的 unmanaged native 扫描暂不扩大，避免非系统路径扫描成本失控。

### 2. Alias 发现基于“能力匹配但包名不同”

当 source 和 target 通过强或中等证据匹配成功，并且两边 owner package 不一致时，分析器生成 package alias observation。

可触发 observation 的证据包括：
- exact ELF SONAME / provided capability
- exact library filename
- normalized library name
- gconv/runtime module 文件名
- owner package 覆盖的 library 被 package candidate 覆盖

不应只因为 weak name 命中就生成高置信 alias。

### 3. Observation 默认是候选，不是人工确认规则

自动发现的关系默认状态为 `CANDIDATE`。后续可以复用，但 confidence 必须体现来源：

```text
CANDIDATE + observed_count 较低  -> MEDIUM
CANDIDATE + 多证据多次命中       -> MEDIUM/HIGH
APPROVED                         -> HIGH
REJECTED                         -> 不参与匹配
```

这样避免把偶然同名文件误升为全局包等价关系。

### 4. 跨操作系统分析必须先跑 library/native evidence pre-pass

当 source 和 target 的操作系统、发行版或包管理器不同时，分析器应先运行 library/native evidence pre-pass，再做 package/tool candidate 判断。

原因是跨发行版时包名可能不同，但库文件、ELF SONAME、gconv 模块或 provided capability 可以更早证明两个包提供同一运行时能力。例如 `CP1250.so` 能先反推出 `glibc -> libc6`，再让 package 阶段使用该 alias 判断 `glibc` 的目标候选。

分析阶段调整为：

```text
Phase 1: library/native evidence pre-pass
  - 比较 source library/native 与 target installed/repository library evidence
  - 生成本次 package alias observations
  - 合并历史未拒绝 alias observations

Phase 2: package/tool candidate decision
  - 使用 Phase 1 alias 进行 package/tool 判断
  - 避免 glibc/libc6 这类跨发行版基础包被误判为源码构建

Phase 3: library/native finalization
  - 已被 package candidate 覆盖的库标记为 covered
  - 未覆盖的库再单独匹配或进入人工确认
```

同一发行版且包管理器一致时可以保留现有流程，但仍可使用历史 `APPROVED` alias。

### 5. Java 后端负责持久化和注入历史 alias

分析器保持独立，只接收输入 JSON 并输出结果 JSON。Java 后端负责：
- 查询历史 alias observations。
- 将可用 alias 作为 `packageAliases` 注入 analyzer input。
- 导入 analyzer 输出中的 `packageAliasObservations`。
- 更新 observed_count、first_seen_at、last_seen_at 和 status。

### 6. 分析结果需要展示 alias 证据

replacement candidate metadata 和 Java 导入后的 `evidence` 字段必须包含：

```json
{
  "packageAliasCandidate": true,
  "sourceOwnerPackage": "glibc",
  "targetOwnerPackage": "libc6",
  "aliasEvidenceType": "exact_library_filename",
  "aliasEvidenceValue": "CP1250.so",
  "aliasStatus": "CANDIDATE",
  "aliasConfidence": "OBSERVED"
}
```

前端或审计 HTML 可以据此解释为什么 `glibc` 能匹配到 `libc6`。

## Risks / Trade-offs

- [Risk] 扫描深度从 2 增加到 4 会增加采集耗时。  
  Mitigation: 只扩大系统库目录，并继续限制 `-type f -name '*.so*'`。

- [Risk] 同名库文件不一定证明两个包语义完全等价。  
  Mitigation: 自动发现默认是 `CANDIDATE`，并保留 evidence_type、evidence_value 和 observed_count；弱证据不生成高置信 alias。

- [Risk] alias 关系可能和发行版版本强绑定。  
  Mitigation: observation 记录 source/target distro、版本和 package manager，不做无条件全局复用。

- [Risk] analyzer 输出和 Java DTO/schema 需要同步升级。  
  Mitigation: 保持 schemaVersion 兼容处理，新增字段按可选字段读取。

## Migration Plan

1. 使用 Liquibase 增加 package alias observation 表和必要索引。
2. 扩展 Java SBOM analyzer input，注入历史可用 alias。
3. 扩展 analyzer 输出，增加 `packageAliasObservations`。
4. 扩展 Java 结果导入逻辑，持久化 observation 并在结果 evidence 中展示 alias 证据。
5. 调整环境采集脚本系统库扫描深度到 4。
6. 运行单元测试、analyzer 测试和真实 x86/Bianbu-RISC-V 验证。

Rollback 时可以保留新增表不使用，恢复 analyzer input 不注入 alias，结果仍按原匹配逻辑运行。

## Open Questions

- 自动 alias 是否需要在 MVP 阶段提供管理 API，还是仅先落库并在结果 evidence 中展示。
- `APPROVED` / `REJECTED` 状态由后续配置页维护，还是先通过数据库人工维护。
- upstream version normalization 是否纳入本 change，还是独立 change 处理。
