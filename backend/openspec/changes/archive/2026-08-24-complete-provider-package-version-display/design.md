## Context

构建驱动依赖分析已经替代旧 SBOM 主流程，用 x86/source 构建事实提取真实依赖，再查询 RISC-V/target 环境和软件源能力。最近真实验证发现结果仍有一个关键断点：ELF/SO 和构建工具虽然能找到部分 provider evidence，但 API/JSON/HTML 没有稳定展示源端包名、源端包版本、目标端包名、目标端包版本和版本关系。

当前 `summary.json` 中部分目标端证据位于 `evidence.targetMatchEvidence`，例如 `libc.so -> libc6-dev`、`libgcc.so -> libgcc-13-dev:riscv64@13.2.0-23ubuntu4bb4`，但源端 owner package/version 未结构化进入结果项，HTML 也只渲染一个 provider 字段。这会导致审计人员无法确认风险等级是否来自真实版本关系。

## Goals / Non-Goals

**Goals:**

- 为依赖分析结果建立稳定的 provider package/version 字段。
- 将 provider package version 与 detected version 分离，避免把低置信度 ELF 字符串误当成包版本。
- 让列表 API、详情 API、JSON artifact、HTML artifact 和真实验证 HTML 都能展示源/目标双方版本。
- 保留敏感信息和服务器路径脱敏规则。
- 补齐单元测试、E2E 和真实验证脚本，使正常流程、异常流程和 edge case 都覆盖该契约。

**Non-Goals:**

- 不恢复旧 SBOM 主流程。
- 不为每一种构建系统单独实现完整 parser。
- 不把完整构建日志、远端真实路径或凭据写入 API 响应。
- 不要求所有 ELF/SO 都能得到高置信度版本；缺失时必须明确标记 evidence 不足。

## Decisions

### 1. provider package version 是主版本依据

依赖分析结果应优先保存以下字段：

| 字段 | 含义 |
|---|---|
| `sourceProviderPackage` | 源环境中提供该工具/库/文件的 owner package |
| `sourceProviderVersion` | 源环境 owner package 版本 |
| `targetProviderPackage` | 目标环境或目标软件源中匹配到的 provider package |
| `targetProviderVersion` | 目标 provider package 版本 |
| `providerVersionStatus` | 源/目标 provider 版本关系 |
| `sourceDetectedVersion` | 非包管理器方式推断出的源端版本 |
| `targetDetectedVersion` | 非包管理器方式推断出的目标端版本 |
| `versionEvidenceConfidence` | detected version 的证据强度 |

原因：包管理器 owner/provider 查询可审计、可重复，适合作为风险判断依据；`--version`、`readelf`、`objdump`、`strings` 输出格式不稳定，只能作为补充证据。

### 2. ELF/SO 不默认执行 `--version`

ELF/SO 的解析顺序：

```text
定位实际文件
  -> rpm -qf / dpkg -S / 等效 owner 查询
  -> owner package version 作为主版本
  -> readelf/objdump 提取 SONAME、NEEDED、Machine、ABI
  -> 文件名/SONAME/symlink 提取库版本
  -> strings 仅作为最后的弱 evidence
```

不对 `.so` 默认执行 `--version`，因为多数动态库不是可执行命令入口，直接执行不稳定，也可能产生副作用。

### 3. 工具命令可以安全采集 detected version

构建工具和命令行工具的解析顺序：

```text
定位命令路径
  -> rpm -qf / dpkg -S / 等效 owner 查询
  -> owner package version 作为主版本
  -> 白名单版本命令采样，例如 gcc --version、cmake --version、make --version
```

版本命令必须有限时、输出长度上限和敏感信息脱敏。版本命令失败不应导致依赖分析失败。

### 4. 版本关系必须可解释

`providerVersionStatus` 使用固定枚举：

- `SAME_MAJOR`: 源有包，目标有包，大版本一致，对应 `INFO`
- `TARGET_NEWER`: 源有包，目标有包，目标版本高于源版本，对应 `LOW`
- `TARGET_OLDER`: 源有包，目标有包，目标版本低于源版本，对应 `HIGH`
- `TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED`: 源无 owner package，但有 detected version，目标有 provider package version，对应 `MEDIUM`
- `NO_TARGET_VERSION_FOUND`: 源无 owner package，且目标无可确认版本，对应 `CRITICAL`
- `UNKNOWN`: 证据不足或不适用，必须保留 warning/evidence

列表和报告应同时展示风险等级和版本关系，不能只展示裸 `TARGET_INSTALLED` 或 `REPO_AVAILABLE`。

### 5. API/制品统一使用结构化字段

依赖分析 API DTO、JSON artifact 和 HTML artifact 使用同一组字段。`evidence` 继续保存原始匹配证据摘要，但前端和报告不应从 nested evidence 猜字段。

HTML 展示至少包含：

- 依赖类型
- 依赖名称
- 源 provider package/version
- 源 detected version
- 目标 provider package/version
- 目标 detected version
- provider version status
- 风险等级
- 目标匹配状态
- 位置标签
- 建议

## Risks / Trade-offs

- [Risk] 不同发行版版本格式差异大，字符串比较会误判。  
  → Mitigation: 优先使用 rpm/deb 版本解析；无法解析时只提取 major 并标记解析方式；仍无法解析则返回 `UNKNOWN`。

- [Risk] 源端 provider 查询失败会让风险等级偏高。  
  → Mitigation: 保留 source-unowned 分支，用 detected version 和目标 provider 作为中置信度证据，不静默降级成低风险。

- [Risk] `strings` 可能提取到误导性版本。  
  → Mitigation: `strings` 仅作为低置信度 evidence，不参与高置信度 provider version 判断。

- [Risk] 新增结构化字段需要数据库和 jOOQ 同步。  
  → Mitigation: 通过 Liquibase 创建迁移，迁移后运行 jOOQ 生成脚本；不得手动直接改数据库 schema 后绕过迁移。

- [Risk] 真实验证 HTML 与业务 HTML 字段不一致。  
  → Mitigation: 真实验证脚本复用或映射同一组结果字段，并在 E2E 中校验关键字段存在。

## Migration Plan

1. 增加 Liquibase 迁移，为依赖分析结果明细补充 provider package/version 和 detected version 字段，或明确将其稳定写入现有字段并同步 DTO。
2. 运行 jOOQ 生成脚本，确保生成代码和 schema 一致。
3. 更新依赖分析 worker 写入逻辑和版本解析逻辑。
4. 更新 API DTO、JSON artifact、HTML artifact 和真实验证 HTML。
5. 补齐单元测试、E2E 和真实四项目验证。
6. 回滚时可保留新增列为空；旧响应字段仍可兼容，但新展示能力不可用。

## Open Questions

- 是否需要把 `providerVersionStatus` 做成数据库 enum/check constraint，还是先用 varchar + 应用层白名单。
- detected version 的置信度是否需要固定枚举为 `PACKAGE_OWNER`、`COMMAND_VERSION`、`ELF_METADATA`、`FILENAME`、`STRINGS`、`UNKNOWN`。
