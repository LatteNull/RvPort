## Context

当前项目表保留 `source_arch` 和 `target_arch`，但没有记录项目源码入库方式。源码版本表和导入表分别通过 `revision_type`、`input_type` 记录单次源码版本或单次导入动作，无法表达“项目首次选择压缩包或 Git 后，后续必须沿用同一种来源”。

当前压缩包上传实现只保存原始上传文件并创建 `ARCHIVE` 源码版本，未自动解包到 `RVPORT_SOURCE_DIR` 或等效源码运行目录，也未写入 `source_revisions.working_copy_path`。后续扫描、构建、测试和对比流程需要稳定的源码工作副本目录，不能只依赖上传包路径。

## Goals / Non-Goals

**Goals:**

- 用项目级字段记录源码来源锁定状态，取值为 `ARCHIVE`、`GIT` 或未锁定。
- 只有首次成功源码入库才能锁定来源；失败的上传、解包或 Git 同步不得锁定项目。
- 后续源码入库必须与锁定来源一致。
- 上传压缩包成功后，后端自动解包到独立源码运行目录，并将该目录作为 `working_copy_path` 保存。
- 支持 `zip`、`rar`、`7z`、`tar.gz`、`tgz`、`tar.xz`、`gzip`，并统一做安全校验。
- 保持 API 响应不暴露服务器真实路径。

**Non-Goals:**

- 不恢复项目创建时的 C/C++ 代码来源字段。
- 不改 frontend 上传进度模型。
- 不把压缩包上传改造成异步任务。
- 不实现源码格式深度识别、语言检测或构建系统识别。
- 不清理历史源码文件和历史运行目录。

## Decisions

### 1. 在 `projects` 增加 `source_input_type`

新增 nullable 字段：

```text
projects.source_input_type text null
CHECK source_input_type IN ('ARCHIVE', 'GIT')
```

未入库项目保持 `null`。首次成功 `ARCHIVE` 或 `GIT` 入库后写入对应值。该字段是项目级源码入口事实，不替代 `source_revisions.revision_type` 和 `source_imports.input_type`。

备选方案是从首个 `source_revisions` 推导项目来源。该方案会让每次请求都要扫描历史版本，并且难以表达“项目已锁定但当前没有 active source”的情况，因此不采用。

### 2. 来源在成功后锁定，而不是请求开始时锁定

压缩包上传需要保存文件、格式校验、解包和源码结构校验。Git 同步需要 worker 成功 checkout。任何失败都不应改变项目来源锁定状态。

压缩包流程在一个事务中完成数据库写入；文件保存和解包发生在数据库提交前，失败时不创建成功记录。Git 流程在 worker 成功创建 `source_revisions` 并完成 `source_imports` 后锁定项目。

### 3. 压缩包解包到源码运行目录

原始上传文件继续保存到 `RVPORT_UPLOAD_DIR`。解包目标使用 `RVPORT_SOURCE_DIR` 或现有 runtime source 配置，目录结构为：

```text
runtime/sources/{projectId}/{sourceRevisionId}/
```

`source_revisions.archive_path` 保存原始压缩包内部路径，`source_revisions.working_copy_path` 保存解包后的源码工作目录。API 只返回安全摘要，不返回这两个本地路径。

### 4. 归档格式支持通过统一 Archive Extractor

实现一个后端内部归档解包服务，负责：

- 根据文件名和文件头识别 `zip`、`rar`、`7z`、`tar.gz`、`tgz`、`tar.xz`、`gzip`。
- 解包前创建独立临时目录，解包完成和校验通过后再移动或确认到最终运行目录。
- 校验每个 entry 的 normalize 结果必须在目标目录内，防止 Zip Slip 和路径逃逸。
- 拒绝空归档、只有目录的归档、解包后无法形成源码根的归档。
- 对 `gzip` 单文件压缩，解压后如果不能形成可用源码文件或目录，返回 `SOURCE_ARCHIVE_UNSUPPORTED_STRUCTURE`。

Java 标准库只覆盖 zip/gzip，不覆盖 rar/7z/tar.xz。实现时应选择许可证兼容的归档库，优先统一通过 Apache Commons Compress 覆盖 tar/gzip/xz/7z，再评估 rar 支持是否需要额外库或受限支持。

### 5. 锁定校验在业务入口执行

`POST /api/projects/{projectId}/sources/archive`：

- `source_input_type is null` 或 `ARCHIVE` 时允许继续。
- `source_input_type = GIT` 时拒绝，返回 `SOURCE_INPUT_TYPE_LOCKED`。

`POST /api/projects/{projectId}/sources/git-sync`：

- `source_input_type is null` 或 `GIT` 时允许继续。
- `source_input_type = ARCHIVE` 时拒绝，返回 `SOURCE_INPUT_TYPE_LOCKED`。

Git 同步允许创建任务前先校验锁定状态，但只有任务成功后才将空锁定写为 `GIT`。

## Risks / Trade-offs

- [Risk] rar 支持的 Java 库能力、许可证和格式兼容性有限。→ Mitigation: 设计中保留格式识别和明确错误码；实现前确认依赖许可，必要时仅支持常见 RAR5 读取并用测试覆盖。
- [Risk] 大压缩包解包耗时较长，同步上传请求可能阻塞。→ Mitigation: MVP 保持同步，限制单包大小和解包超时；后续可迁移为异步 archive import 任务。
- [Risk] 解包成功但数据库事务失败会留下运行目录。→ Mitigation: 失败路径尽力清理本次 `sourceRevisionId` 目录；保留定期 runtime 清理作为后续优化。
- [Risk] 旧项目已有 Git 源码版本但 `source_input_type` 为空。→ Mitigation: 迁移脚本根据已有 `source_revisions` 回填；混合历史项目如果存在多种类型，按 active source 或最早成功版本处理，并记录需要人工确认。

## Migration Plan

1. 新增 Liquibase 迁移：`projects.source_input_type`、check constraint、必要索引。
2. 对已有项目回填：有 active source 时使用 active revision type；无 active source 但有历史 source 时使用最早成功 revision type；没有 source 时保持 null。
3. 重新运行 jOOQ codegen。
4. 更新 repository、service、DTO 和 API 文档。
5. 增加 archive extractor 和测试。
6. 运行 Maven 测试和 source E2E 模块。

## Open Questions

- `rar` 的具体库选择和支持版本需要在实现前确认。
- 是否要对压缩包大小、entry 数量和单文件大小增加配置项，本 change 可先沿用现有上传大小限制。
