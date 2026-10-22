## Why

后端已经产生 KB 扫描报告、SBOM 分析摘要、后续迁移报告和归档等运行制品，这些内容不适合长期保存在 PostgreSQL 大字段或容器本地临时目录中。引入 MinIO/S3 兼容对象存储可以让数据库只保存可查询元数据，报告和扫描输出等大文件由对象存储负责持久化。

此前“不建立 artifact 表”的约束指向源码包、源码版本等输入制品，不应阻止后端运行过程中产生的报告、扫描输出、日志归档等输出制品建立统一元数据。两者需要在文档和实现中明确区分。

## What Changes

- 新增 MinIO 作为本地开发和部署基础设施，集成到根目录 `docker-compose.yml`。
- 新增对象存储配置项，使用 `.env` 管理 endpoint、bucket、access key、secret key、region、path-style 等参数。
- 新增 S3 兼容对象存储客户端封装，业务代码只依赖后端抽象，不直接绑定 MinIO 实现细节。
- 新增后端生成制品的统一元数据表，用于记录 bucket、object key、content type、size、sha256、owner 类型和 owner ID。
- 明确不新增源码制品表，不把源码包、源码版本工作副本或 Git checkout 纳入该制品表。
- 明确不新增面向前端的通用 Artifact API；下载仍由 KB、SBOM、报告、归档等业务接口负责权限校验和响应。
- 为后续 `add-migration-report-runtime` 提供报告 HTML/JSON 保存到对象存储的基础能力。
- 为现有 KB/SBOM artifact 迁移到对象存储预留兼容路径。

## Capabilities

### New Capabilities

- `object-storage-artifacts`: 后端生成制品的对象存储、元数据和受控下载基础能力。

### Modified Capabilities

- `backend-infrastructure`: 增加 MinIO 服务、持久化 volume、健康检查和对象存储环境变量。
- `backend-database-design`: 澄清源码制品和后端生成制品的边界，并新增后端生成制品元数据表要求。
- `backend-api-design`: 澄清不新增通用 Artifact API，但业务下载接口可基于统一制品元数据读取对象存储。
- `kb-scan-runtime`: KB 扫描 artifact 应可保存到对象存储并保留现有业务下载接口。
- `sbom-analysis-runtime`: SBOM 分析 artifact 应可保存到对象存储并保留现有业务查询接口。
- `api-e2e-test-suite`: 增加对象存储连通性、artifact 写入、下载和清理验证。

## Impact

- 基础设施：根目录 `docker-compose.yml` 增加 MinIO 和 console 端口；`.env.example` 增加对象存储配置。
- 后端配置：新增对象存储 properties 和 S3/MinIO client bean。
- 数据库：新增 `stored_artifacts` 或等效后端生成制品元数据表；现有 KB/SBOM 专用 artifact 表可逐步兼容引用对象存储。
- 业务模块：KB、SBOM、迁移报告、归档后续可通过统一 artifact storage service 写入和读取对象。
- 安全：对象 key 不包含服务器真实路径；API 不返回 secret key、bucket 内部结构或未授权对象信息。
- 测试：新增单元测试和 E2E，验证 MinIO 可用、对象写入读取、权限校验、清理和降级错误。
