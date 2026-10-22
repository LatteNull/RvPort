## 1. 数据库与代码生成

- [x] 1.1 新增 Liquibase changelog 创建 `archive_candidates` 表，包含源码版本、节点类型、候选类型、候选 key、资源引用、摘要、artifact refs、状态和时间字段。
- [x] 1.2 为 `archive_candidates` 增加 `(project_id, source_revision_id, node_type, candidate_type, candidate_key)` 唯一约束和当前候选查询索引。
- [x] 1.3 扩展 `archives` 表，新增 `source_revision_id` 和归档包 artifact 引用所需字段或兼容结构。
- [x] 1.4 扩展 `archive_items` 表，固化 candidate 快照字段：`candidate_id`、`node_type`、`candidate_type`、`candidate_key`、资源引用、标题、artifact refs 和 metadata。
- [x] 1.5 更新 `stored_artifacts` 约束，确认 `ARCHIVE` 归档包类型可保存，并运行 jOOQ 生成脚本。

## 2. 归档候选模型与登记能力

- [x] 2.1 新增归档候选枚举、DTO、artifact ref 结构、repository 和 service。
- [x] 2.2 实现候选 upsert，按 `project_id + source_revision_id + node_type + candidate_type + candidate_key` 更新最新候选。
- [x] 2.3 实现候选查询，只返回当前 active 源码版本下 `ACTIVE` 候选。
- [x] 2.4 实现候选安全校验，禁止保存对象存储 key、服务器真实路径、完整日志、完整报告正文、完整 agent 输入或明文凭据。
- [x] 2.5 为候选登记补充单元测试，覆盖正常流程、重复 upsert、跨源码版本隔离和非法敏感内容。

## 3. 已有节点接入归档候选

- [x] 3.1 迁移评估报告生成成功后登记 `MIGRATION_REPORT / REPORT / latest` 候选，包含 HTML 和 JSON artifact refs。
- [x] 3.2 KB 扫描成功后登记 `KB_SCAN` 相关候选，包含 HTML、JSON 和 LOG artifact refs。
- [x] 3.3 SBOM 分析成功后登记 `SBOM_ANALYSIS` 相关候选，包含分析输入摘要、输出摘要和审计摘要 artifact refs。
- [x] 3.4 复检完成后登记 `RECHECK / DIFF_REPORT / latest` 候选。
- [x] 3.5 构建验证完成后按环境登记 `BUILD_VALIDATION / BUILD_SUMMARY / <environmentRole>` 候选。
- [x] 3.6 自动化测试完成后按环境登记 `AUTOMATED_TEST / TEST_SUMMARY / <environmentRole>` 候选。
- [x] 3.7 测试结果比较完成或不可用时登记 `TEST_COMPARISON / COMPARISON_REPORT / latest` 候选。

## 4. 归档运行时

- [x] 4.1 新增归档领域模型、列表查询对象、响应对象、repository 和 service。
- [x] 4.2 实现 `POST /api/projects/{projectId}/archives` 创建归档任务，绑定当前 active `sourceRevisionId`。
- [x] 4.3 新增 `ARCHIVE_PROJECT` 任务类型和 worker handler，从候选表读取当前源码版本候选。
- [x] 4.4 实现归档项固化，将 candidate 快照写入 `archive_items`。
- [x] 4.5 实现归档包生成，包含 `manifest.json`、`summary.json` 和归档项引用的 HTML/JSON/LOG 文件。
- [x] 4.6 将归档包保存到对象存储 `stored_artifacts(owner_type=ARCHIVE)`，并回写归档状态、大小、sha256 和 summary。
- [x] 4.7 实现归档任务失败处理，写入 `archives.status=FAILED` 和脱敏错误摘要。

## 5. 归档 API

- [x] 5.1 新增 `GET /api/projects/{projectId}/archives/overview`，返回最新归档信息和 included items 摘要。
- [x] 5.2 新增或完善 `GET /api/projects/{projectId}/archives`，支持分页、过滤和排序。
- [x] 5.3 新增或完善 `GET /api/archives/{archiveId}`，返回归档详情和归档项列表。
- [x] 5.4 新增 `GET /api/archives/{archiveId}/items/{itemId}?format=...`，支持查看或下载单项报告内容。
- [x] 5.5 新增或完善 `GET /api/archives/{archiveId}/download`，代理下载归档包。
- [x] 5.6 所有归档 API 接入项目访问权限校验，越权时不泄漏项目、源码版本、候选或归档是否存在。
- [x] 5.7 更新 `backend/docs/API_DESIGN.md` 和必要的开发文档。

## 6. 测试与验证

- [x] 6.1 补充 repository/service 单元测试，覆盖归档创建、候选读取、归档项固化、空候选处理和对象存储失败。
- [x] 6.2 补充 controller/API 测试，覆盖正常流程、异常流程和 edge case。
- [x] 6.3 补充节点候选登记测试，确认各节点成功后写入正确 `nodeType`、`candidateType`、`candidateKey` 和 artifact refs。
- [x] 6.4 新增独立 E2E 模块，覆盖归档当前状态、overview、列表、详情、单项内容和归档包下载。
- [x] 6.5 E2E 覆盖源码版本隔离：新源码版本没有候选时不得归档上一版本内容，旧归档仍可查看。
- [x] 6.6 E2E 覆盖越权访问归档接口和归档响应不暴露服务器路径、对象存储 key 或明文凭据。
- [x] 6.7 运行 `mvn test`。
- [x] 6.8 重建 backend Docker 容器并运行归档 E2E 模块。
- [x] 6.9 运行 `openspec validate add-project-archive-runtime --strict`。
