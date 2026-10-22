## 1. 基础设施和配置

- [x] 1.1 在根目录 `docker-compose.yml` 增加 MinIO 服务、Console 端口、健康检查、命名卷和网络配置
- [x] 1.2 在根目录 `.env.example` 增加 MinIO root 用户、密码、bucket、API 端口和 Console 端口配置
- [x] 1.3 在 backend service 环境变量中增加对象存储 endpoint、bucket、region、access key、secret key 和 path-style 配置
- [x] 1.4 更新 `backend/docs/INFRASTRUCTURE.md`，说明 MinIO 启停、端口、凭据和职责边界
- [x] 1.5 启动 Compose 并验证 MinIO 健康检查通过

## 2. 后端对象存储客户端

- [x] 2.1 增加 S3/MinIO 客户端依赖
- [x] 2.2 新增对象存储配置 properties，绑定 `RVPORT_OBJECT_STORAGE_*` 环境变量
- [x] 2.3 新增 `ObjectStorageService` 抽象，支持上传、读取、删除和 head
- [x] 2.4 实现 S3 兼容对象存储客户端，支持 path-style endpoint
- [x] 2.5 实现 bucket 初始化或可用性检查，本地开发可自动创建 bucket
- [x] 2.6 对象存储错误统一转换为脱敏业务异常

## 3. 数据库和 jOOQ

- [x] 3.1 新增 Liquibase 迁移创建 `stored_artifacts` 或等效后端输出制品元数据表
- [x] 3.2 表字段包含 `project_id`、`task_id`、`owner_type`、`owner_id`、`artifact_type`、`bucket`、`object_key`、`content_type`、`size_bytes`、`sha256`、`summary` 和 `created_at`
- [x] 3.3 增加 owner 查询、项目时间查询和 task 追溯索引
- [x] 3.4 增加 owner/artifact type 唯一性约束或等效防重策略
- [x] 3.5 视情况为 `kb_scan_artifacts`、`sbom_analysis_artifacts` 增加 `stored_artifact_id` 兼容字段
- [x] 3.6 运行 Liquibase 更新本地数据库
- [x] 3.7 运行 jOOQ 生成脚本并确认生成代码更新

## 4. Artifact 元数据服务

- [x] 4.1 新增 artifact owner type 和 artifact type 枚举
- [x] 4.2 新增 `StoredArtifactRepository`，支持创建、按 owner 查询、按 id 查询和删除
- [x] 4.3 新增 `StoredArtifactService`，封装对象上传、sha256 计算、元数据写入和失败清理
- [x] 4.4 object key 生成不得包含服务器绝对路径或用户提交路径片段
- [x] 4.5 API 响应对象只返回 artifact id、type、content type、size、sha256、summary 和 createdAt 等安全字段
- [x] 4.6 E2E/test-support 清理逻辑支持删除本次测试写入的对象和元数据

## 5. KB artifact 接入

- [x] 5.1 KB 扫描新生成的 `SCAN_RESULT_JSON`、`SCAN_REPORT_HTML`、`SCAN_LOG` 上传到对象存储
- [x] 5.2 KB artifact metadata 关联 `stored_artifacts` 或可通过 owner 反查对象存储元数据
- [x] 5.3 KB artifact 列表继续保持现有响应语义，不暴露 bucket/object key
- [x] 5.4 KB artifact 下载接口优先从对象存储读取新制品
- [x] 5.5 保留历史 `content_path` 文件读取兼容，并继续校验 KB 输出根目录边界

## 6. SBOM artifact 接入

- [x] 6.1 SBOM 新生成的审计摘要、分析器输入摘要和分析器输出摘要 artifact 保存到对象存储
- [x] 6.2 SBOM artifact metadata 关联 `stored_artifacts` 或可通过 owner 反查对象存储元数据
- [x] 6.3 SBOM artifact 列表继续保持现有响应语义，不暴露 bucket/object key
- [x] 6.4 SBOM artifact 内容查询从对象存储读取新制品
- [x] 6.5 保留历史 `content jsonb` 读取兼容

## 7. 单元测试

- [x] 7.1 对象存储配置测试覆盖默认值、必填项和 path-style 配置
- [x] 7.2 ObjectStorageService 测试覆盖上传、读取、删除、对象不存在和异常脱敏
- [x] 7.3 StoredArtifactService 测试覆盖元数据写入、sha256、object key 安全、上传失败和元数据失败清理
- [x] 7.4 KB artifact 测试覆盖对象存储新路径和历史本地路径兼容
- [x] 7.5 SBOM artifact 测试覆盖对象存储新路径和历史 JSON 兼容
- [x] 7.6 测试覆盖源码包和源码工作副本不会写入 `stored_artifacts`

## 8. E2E 测试

- [x] 8.1 E2E check 增加对象存储/MinIO 连通性验证
- [x] 8.2 KB E2E 校验 artifact 上传到对象存储、元数据存在、业务下载可用且不泄露内部位置
- [x] 8.3 SBOM E2E 校验 artifact 上传到对象存储、元数据存在、业务查询可用且不泄露内部位置
- [x] 8.4 E2E 清理流程删除测试 artifact 元数据并尽力删除对象存储对象
- [x] 8.5 验证 MinIO 不可用时相关任务失败信息脱敏

## 9. 文档和验证

- [x] 9.1 更新 `docs/DATABASE_DESIGN.md`，澄清源码输入制品和后端输出制品的区别
- [x] 9.2 更新 `docs/API_DESIGN.md`，澄清不新增通用 Artifact API，但业务接口内部可使用对象存储
- [x] 9.3 更新 `docs/api-e2e-coverage.md` 记录对象存储 E2E 覆盖
- [x] 9.4 运行 `mvn test`
- [x] 9.5 运行受影响 E2E 模块
- [x] 9.6 运行 `openspec validate --specs`
- [x] 9.7 检查本 change 任务完成后再继续 `add-migration-report-runtime`
