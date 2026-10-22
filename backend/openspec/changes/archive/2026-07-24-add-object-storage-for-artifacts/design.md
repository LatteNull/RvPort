## Context

RvPort 后端已经会生成多类运行制品：KB 扫描的 HTML/JSON/log、SBOM 分析摘要、后续迁移报告 HTML/JSON、归档包和任务日志归档。当前状态不一致：

- KB 扫描 artifact 使用 `kb_scan_artifacts.content_path` 指向本地文件。
- SBOM 分析 artifact 使用 `sbom_analysis_artifacts.content jsonb` 保存轻量 JSON。
- 报告设计还准备使用 `reports.html_path/json_path` 本地路径。

此前文档中“不引入通用 artifact 表”表达过宽，真实约束应是“不为源码输入制品建立通用制品表，也不开放面向前端的通用 Artifact API”。后端运行产生的输出制品需要统一元数据和对象存储能力。

## Goals / Non-Goals

**Goals:**

- 在本地 Docker Compose 中增加 MinIO，作为 S3 兼容对象存储。
- 增加后端对象存储客户端封装，业务模块不直接依赖 MinIO SDK 细节。
- 增加后端生成制品元数据表，用于记录对象存储位置和审计摘要。
- 区分源码输入制品和后端输出制品，更新过于绝对的文档/spec 约束。
- 支持 KB/SBOM artifact 迁移到对象存储，并为迁移报告生成提供前置能力。
- 保持业务下载接口不变，不新增通用 Artifact API。

**Non-Goals:**

- 不把源码包上传文件、Git checkout、源码工作副本纳入 `stored_artifacts`。
- 不提供 `GET /api/artifacts/{artifactId}` 这类通用前端 API。
- 不要求一次性物理迁移所有历史本地文件或历史 SBOM JSON。
- 不在本 change 实现迁移报告本身。
- 不直接向前端暴露 MinIO 预签名 URL，MVP 下载仍由后端鉴权后代理输出。

## Decisions

### 1. 使用 S3 兼容抽象，MinIO 作为本地实现

后端新增 `ObjectStorageService`，接口表达 `put/get/delete/head` 等能力。配置使用 S3 通用字段：endpoint、region、bucket、accessKey、secretKey、pathStyle、enabled。MinIO 只是 compose 中的本地服务。

选择这个方案是为了避免业务层和 MinIO 绑定。后续如果替换成云厂商 S3 兼容存储，只调整配置和 client 即可。

### 2. 新增 `stored_artifacts` 表保存后端输出制品元数据

建议字段：

- `id`
- `project_id`
- `task_id`
- `owner_type`
- `owner_id`
- `artifact_type`
- `bucket`
- `object_key`
- `content_type`
- `size_bytes`
- `sha256`
- `summary jsonb`
- `created_at`

`owner_type + owner_id + artifact_type` 用于表达 KB scan、SBOM analysis、migration report、archive 等业务归属。该表只保存后端输出制品，不保存源码输入制品。

### 3. 保留业务下载接口，不新增通用 Artifact API

前端仍调用：

- KB: `/api/kb-scans/{scanId}/artifacts...`
- SBOM: `/api/sbom-analyses/{analysisId}/artifacts...`
- 报告: `/api/reports/{reportId}/download`
- 归档: `/api/archives/{archiveId}/download`

业务 service 根据 owner 类型和权限读取 `stored_artifacts` 并从对象存储取回内容。这样可以复用元数据和对象存储，但不把权限模型压扁成一个通用 artifact API。

### 4. 对 KB/SBOM 采用兼容迁移

本 change 可以新增 `stored_artifacts` 并让新写入优先进入对象存储。现有表做兼容：

- KB 新 artifact 可继续写 `kb_scan_artifacts` 作为业务索引，同时增加 `stored_artifact_id` 或通过 owner 反查。
- SBOM 新 artifact 可继续保留 summary/metadata 查询能力，完整内容或大内容迁移到对象存储。

实现时可以先让 KB/SBOM 的现有 API 能从 `stored_artifacts` 下载或读取；历史本地路径/JSON 可保留兼容读取。

### 5. object key 不包含服务器真实路径

object key 使用业务归属构造，例如：

```text
projects/{projectId}/{ownerType}/{ownerId}/{artifactType}-{artifactId}.{ext}
```

禁止把本机绝对路径、临时目录、用户上传原始文件名中的路径片段写入 object key。展示给前端的文件名由业务层生成安全文件名。

### 6. 对象存储失败必须让业务写入失败

对象上传成功但数据库写入失败时，应尽力删除已上传对象。数据库写入成功但对象上传失败时，不应写入成功态 artifact 元数据。业务任务是否失败由调用方决定，但不能留下指向不存在对象的成功元数据。

## Risks / Trade-offs

- [Risk] 新增对象存储增加本地启动复杂度。→ Mitigation: `.env.example` 给默认本地 MinIO 配置，compose 配置健康检查，README/INFRASTRUCTURE 说明启动方式。
- [Risk] 对象上传与数据库事务无法天然原子。→ Mitigation: 先上传对象，事务写元数据；事务失败后尽力删除对象；下载时对不存在对象返回安全错误。
- [Risk] 一次性改造 KB/SBOM 可能影响稳定性。→ Mitigation: 保留现有业务表和接口语义，新增对象存储路径作为新写入优先路径，历史数据兼容读取。
- [Risk] 通用元数据表被误用为源码制品表。→ Mitigation: spec 和代码枚举限制 `owner_type`，明确源码包和源码工作副本不进入该表。
- [Risk] API 直接暴露对象存储 key 后形成信息泄露。→ Mitigation: 响应只返回 artifact id、type、size、sha256、summary 等安全字段，不返回 bucket/object key。

## Migration Plan

1. 增加 MinIO compose 服务和 `.env.example` 配置。
2. 增加对象存储配置、client 和服务封装。
3. 增加 `stored_artifacts` 表和 jOOQ 代码生成。
4. 改造 KB/SBOM 新写入路径使用对象存储元数据，保留旧数据读取兼容。
5. 更新文档，明确源码输入制品和后端输出制品的差异。
6. 后续 `add-migration-report-runtime` 基于 `stored_artifacts` 保存报告 HTML/JSON。

## Open Questions

- 是否需要为生产环境增加 bucket 自动创建开关；本地开发建议自动创建，生产可要求预先创建。
- 历史 KB/SBOM artifact 是否需要后台迁移任务；MVP 可先不迁移。
