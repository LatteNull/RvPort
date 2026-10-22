## 1. 数据库和 jOOQ

- [x] 1.1 新增 Liquibase 迁移，为 `reports` 增加 `source_revision_id`、外键和 `project_id/source_revision_id/generated_at` 索引
- [x] 1.2 视情况补充 `report_inputs.input_type` 的应用层常量或数据库约束，支持 `MIGRATION_INPUT_REF`
- [x] 1.3 运行 Liquibase 更新本地数据库
- [x] 1.4 运行 jOOQ 生成脚本，更新生成代码
- [x] 1.5 验证数据库中 `reports`、`report_inputs` 和新增索引结构正确

## 2. 报告领域模型和 Repository

- [x] 2.1 新增 `report` 包和报告状态、类型、下载格式、请求、响应、视图对象
- [x] 2.2 实现 `ReportRepository`，支持创建报告、按 taskId 查询、更新运行状态、写入摘要和读取报告元数据
- [x] 2.3 实现报告列表、latest、详情查询，并支持分页、过滤和排序白名单
- [x] 2.4 实现 `report_inputs` 批量写入和分页查询
- [x] 2.5 确保 repository 不向响应对象暴露 `html_path`、`json_path`、bucket、object key 或服务器真实路径
- [x] 2.6 报告 service 复用 `StoredArtifactService` 保存和读取 HTML/JSON 报告制品

## 3. API 和权限

- [x] 3.1 新增 `ReportController`
- [x] 3.2 实现 `POST /api/projects/{projectId}/reports/evaluation`
- [x] 3.3 实现 `GET /api/projects/{projectId}/reports/evaluation`
- [x] 3.4 实现 `GET /api/projects/{projectId}/reports/evaluation/latest`
- [x] 3.5 实现 `GET /api/reports/{reportId}`
- [x] 3.6 实现 `GET /api/reports/{reportId}/inputs`
- [x] 3.7 实现 `GET /api/reports/{reportId}/download?format=HTML|JSON`
- [x] 3.8 所有 reportId 入口必须通过报告反查 projectId 并执行项目访问权限校验
- [x] 3.9 创建报告时校验 `sourceRevisionId` 属于项目；未提交时使用 active source revision

## 4. 报告生成 Runtime

- [x] 4.1 在 `RvPortTaskTypes` 中新增 `REPORT_GENERATE`
- [x] 4.2 实现报告生成输入模型，包含 `projectId`、`sourceRevisionId`、`reportId`
- [x] 4.3 实现 `ReportGenerateHandler` 并注册到 worker handler registry
- [x] 4.4 worker 读取指定源码版本下 `CONFIRMED` 的迁移输入；为空时抛出 `REPORT_NO_CONFIRMED_INPUTS`
- [x] 4.5 根据 `source_type/source_ref_id` 获取真实来源详情并生成 `report_inputs.input_snapshot`
- [x] 4.6 生成 `migration-report/v1` JSON 报告
- [x] 4.7 生成对应 HTML 报告
- [x] 4.8 将 HTML/JSON 报告保存到对象存储，并写入 `stored_artifacts(owner_type=MIGRATION_REPORT, owner_id=reportId)`
- [x] 4.9 成功后更新 `reports.status`、`summary`、`risk_level` 和 `generated_at`
- [x] 4.10 失败或取消时将 `reports.status` 与任务终态保持一致，并尽力清理本次写入的对象存储制品

## 5. 下载安全和摘要

- [x] 5.1 报告下载按 reportId 和 format 查询 `stored_artifacts`，校验项目权限后代理读取对象内容
- [x] 5.2 下载接口使用安全文件名和正确 Content-Type
- [x] 5.3 报告摘要统计 confirmed 输入总数、来源类型分布和等级分布
- [x] 5.4 总体风险等级按 `CRITICAL > HIGH > MEDIUM > LOW > INFO > COMMENT` 聚合，SBOM `risk/status` 取 `/` 前风险部分
- [x] 5.5 确保报告详情、输入列表和下载内容不包含明文凭据、服务器真实路径、bucket 或 object key

## 6. 单元测试

- [x] 6.1 Repository 测试覆盖报告创建、状态更新、列表过滤排序、latest 查询和输入快照分页
- [x] 6.2 Service 测试覆盖正常创建报告任务
- [x] 6.3 Service 测试覆盖无 active source revision、sourceRevision 跨项目、无权限访问
- [x] 6.4 Runtime 测试覆盖 confirmed 输入生成 HTML/JSON 和写入 report_inputs
- [x] 6.5 Runtime 测试覆盖没有 confirmed 输入时失败
- [x] 6.6 Runtime 测试覆盖生成后修改迁移输入不影响报告快照
- [x] 6.7 下载测试覆盖 HTML、JSON、不支持格式、文件不存在和路径非法

## 7. E2E 测试

- [x] 7.1 新增 E2E report 模块，可通过 module runner 单独运行
- [x] 7.2 正常流程：创建项目和源码版本，准备 KB/SBOM 来源结果，导入并确认迁移输入，创建报告并等待成功
- [x] 7.3 校验报告详情、输入快照分页、HTML 下载和 JSON 下载
- [x] 7.4 异常流程：没有 confirmed 输入时报告任务失败并返回明确错误
- [x] 7.5 异常流程：普通用户不能访问其他项目报告详情、输入快照和下载
- [x] 7.6 Edge case：报告生成后修改迁移输入状态或备注，历史报告快照保持不变
- [x] 7.7 Edge case：非法下载格式返回统一业务错误
- [x] 7.8 E2E 校验报告对象存储元数据存在、业务下载可用且响应不泄露内部存储位置
- [x] 7.9 E2E 清理脚本清理报告、报告输入、stored artifact 元数据、对象存储对象、任务和测试数据

## 8. 文档和验证

- [x] 8.1 更新 `docs/API_DESIGN.md` 的报告接口字段、过滤排序和错误码说明
- [x] 8.2 更新 `docs/DATABASE_DESIGN.md` 的 `reports.source_revision_id` 和报告输入快照说明
- [x] 8.3 运行 `mvn test`
- [x] 8.4 运行报告模块 E2E
- [x] 8.5 运行 `openspec validate --specs`
- [x] 8.6 检查 task 列表全部完成后准备 archive 和 sync
