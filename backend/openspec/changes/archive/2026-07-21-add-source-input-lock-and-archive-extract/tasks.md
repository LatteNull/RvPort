## 1. 数据库与代码生成

- [x] 1.1 新增 Liquibase 迁移，为 `projects` 增加 `source_input_type` 字段和取值约束。
- [x] 1.2 在迁移中按 active source 或历史 source 回填已有项目的 `source_input_type`。
- [x] 1.3 运行 Liquibase 并重新执行 jOOQ codegen，提交生成代码。
- [x] 1.4 更新项目领域枚举、`ProjectView`、`ProjectResponse`、overview DTO 和 repository 映射。

## 2. 来源锁定业务逻辑

- [x] 2.1 在项目 repository/service 中增加读取和更新源码来源锁定的能力。
- [x] 2.2 在压缩包上传入口校验 `source_input_type`，拒绝已锁定为 `GIT` 的项目。
- [x] 2.3 在 Git 同步入口校验 `source_input_type`，拒绝已锁定为 `ARCHIVE` 的项目。
- [x] 2.4 在压缩包上传完整成功后将空锁定写为 `ARCHIVE`。
- [x] 2.5 在 Git 同步 worker 完整成功后将空锁定写为 `GIT`。
- [x] 2.6 确保失败的上传、解包或 Git 同步不会锁定项目来源。

## 3. 压缩包解包运行时

- [x] 3.1 评估并引入许可证可接受的归档解包依赖，覆盖 `zip`、`rar`、`7z`、`tar.gz`、`tgz`、`tar.xz` 和 `gzip`。
- [x] 3.2 实现内部 Archive Extractor，统一格式识别、临时目录、解包和清理逻辑。
- [x] 3.3 实现路径逃逸防护，拒绝绝对路径、`..` 和 normalize 后越界 entry。
- [x] 3.4 实现空包、仅目录、单文件 gzip 无效结构和不支持格式的错误映射。
- [x] 3.5 将源码包解包到 `runtime/sources/{projectId}/{sourceRevisionId}` 或配置指定目录。
- [x] 3.6 创建 `ARCHIVE` 源码版本时写入 `archive_path` 和 `working_copy_path` 内部字段。

## 4. API 与文档

- [x] 4.1 更新项目列表、项目详情和项目 overview 响应，返回 `sourceInputType`。
- [x] 4.2 更新源码上传成功响应，确认不暴露 `archive_path` 和 `working_copy_path`。
- [x] 4.3 增加 `SOURCE_INPUT_TYPE_LOCKED`、`SOURCE_ARCHIVE_UNSUPPORTED_FORMAT`、`SOURCE_ARCHIVE_UNSAFE_PATH`、`SOURCE_ARCHIVE_EMPTY` 和 `SOURCE_ARCHIVE_UNSUPPORTED_STRUCTURE` 错误处理。
- [x] 4.4 更新 `backend/docs/API_DESIGN.md` 和相关开发文档。

## 5. 测试

- [x] 5.1 补充正常流程测试：首次 archive 成功锁定 `ARCHIVE`，再次 archive 成功创建新版本。
- [x] 5.2 补充正常流程测试：首次 Git 同步成功锁定 `GIT`，再次 Git 同步允许。
- [x] 5.3 补充异常流程测试：锁定 `ARCHIVE` 后 Git 同步被拒绝，锁定 `GIT` 后 archive 上传被拒绝。
- [x] 5.4 补充异常流程测试：不支持格式、路径逃逸、空包、无效 gzip 和解包失败不创建成功版本。
- [x] 5.5 补充 edge case 测试：历史项目回填、混合历史来源、activate=false、重复上传、文件名异常和清理失败。
- [x] 5.6 更新 source E2E 模块，覆盖 archive 上传解包和 Git 锁定互斥。

## 6. 验证

- [x] 6.1 运行 `mvn test`。
- [x] 6.2 启动后端和基础设施，运行 source 相关 E2E。
- [x] 6.3 通过数据库检查 `projects.source_input_type`、`source_revisions.archive_path`、`source_revisions.working_copy_path` 和 `source_imports` 状态。
- [x] 6.4 确认 API 响应不暴露服务器真实源码路径。
