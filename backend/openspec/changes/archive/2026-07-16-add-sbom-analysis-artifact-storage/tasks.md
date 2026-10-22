## 1. 数据库和生成代码

- [x] 1.1 新增 Liquibase changeset 创建 `sbom_analysis_result_items` 表
- [x] 1.2 为结果明细表添加 `project_id`、`task_id`、`sbom_run_id` 外键
- [x] 1.3 为结果明细表添加 `sbom_run_id + created_at`、`project_id + task_id`、`sbom_run_id + component_type`、`sbom_run_id + source_name`、`sbom_run_id + risk_level`、`sbom_run_id + target_match_status` 索引
- [x] 1.4 新增 Liquibase changeset 创建 `sbom_analysis_artifacts` 摘要表
- [x] 1.5 为 artifact 表添加 `project_id`、`task_id`、`sbom_run_id`、`project_id + task_id` 索引
- [x] 1.6 添加 `artifact_type`、`size_bytes`、唯一性和外键约束
- [x] 1.7 运行 jOOQ 生成脚本并确认生成 `SbomAnalysisResultItems` 和 `SbomAnalysisArtifacts` 相关代码

## 2. 后端领域模型和 Repository

- [x] 2.1 新增 SBOM 结果明细 DTO、查询条件 DTO 和排序白名单
- [x] 2.2 新增 SBOM artifact 类型枚举或稳定常量
- [x] 2.3 新增 artifact 列表响应和详情响应 DTO
- [x] 2.4 在 `SbomRepository` 中实现结果明细批量写入、分页列表查询、过滤和排序
- [x] 2.5 在 `SbomRepository` 中实现 artifact upsert/insert、分页列表查询和按类型查询
- [x] 2.6 确保结果明细和 artifact 查询可通过 `sbom_run_id` 关联 `project_id`、`task_id`
- [x] 2.7 为 artifact 写入计算 `sha256` 和 `size_bytes`
- [x] 2.8 实现结果明细过滤条件：`componentType`、`sourceName`、`sourceVersion`、`sourcePackageName`、`targetMatchStatus`、`targetName`、`targetVersion`、`targetPackageName`、`riskLevel`、`matchStrategy`、`recommendation`
- [x] 2.9 实现结果明细排序白名单：`componentType`、`sourceName`、`sourceVersion`、`targetMatchStatus`、`riskLevel`、`matchStrategy`、`createdAt`
- [x] 2.10 实现 artifact 列表过滤条件：`artifactType`、`schemaVersion`、`taskId`、`sha256`、`createdFrom`、`createdTo`、`minSizeBytes`、`maxSizeBytes`
- [x] 2.11 实现 artifact 列表排序白名单：`artifactType`、`schemaVersion`、`createdAt`、`sizeBytes`、`sha256`

## 3. SBOM Runtime Artifact 生成

- [x] 3.1 在 `SbomAnalysisRuntimeService` 成功路径中将分析结果逐条写入 `sbom_analysis_result_items`
- [x] 3.2 在 `SbomAnalysisRuntimeService` 成功路径中生成 `AUDIT_SUMMARY_JSON`
- [x] 3.3 生成 `ANALYZER_INPUT_SUMMARY_JSON`，只包含输入摘要和组件数量
- [x] 3.4 生成 `ANALYZER_OUTPUT_SUMMARY_JSON`，只包含输出摘要、warnings、tool、counts 和有限候选样本
- [x] 3.5 使用字段白名单构造结果 evidence 和 artifact，避免复制完整 analyzer input/output/raw snapshot
- [x] 3.6 结果明细或 artifact 写入失败时将 SBOM run 和任务按失败处理

## 4. API 和权限

- [x] 4.1 将列表类接口必须支持分页、排序和过滤同步为全局 API 约定
- [x] 4.2 实现 `GET /api/sbom-analyses/{analysisId}/results` 分页列表
- [x] 4.3 实现 `GET /api/sbom-analyses/{analysisId}/artifacts` 分页列表
- [x] 4.4 实现 `GET /api/sbom-analyses/{analysisId}/artifacts/{artifactType}`
- [x] 4.5 复用 SBOM run 的项目访问权限校验
- [x] 4.6 对不存在 artifact、analysis 和无权限访问返回安全错误
- [x] 4.7 确认本 change 不新增通用 `GET /api/tasks/{taskId}/artifacts`
- [x] 4.8 为结果明细和 artifact 列表 API 增加分页、过滤、排序参数 DTO 和校验

## 5. 单元测试

- [x] 5.1 Repository 正常流程测试：批量写入并分页查询结果明细
- [x] 5.2 Repository 正常流程测试：写入并分页查询 artifact
- [x] 5.3 Repository 异常流程测试：重复 artifact type、非法 size 或缺失关联失败
- [x] 5.4 Repository edge case 测试：空结果集、单条结果和多页边界
- [x] 5.5 Runtime 正常流程测试：成功分析写入结果明细和 3 类 artifact
- [x] 5.6 Runtime 异常流程测试：结果明细或 artifact 写入失败导致任务失败
- [x] 5.7 Runtime edge case 测试：空组件清单和仓库缺失 warning 仍生成 artifact
- [x] 5.8 API 正常流程测试：有权限用户分页查询结果明细、artifact 列表和详情
- [x] 5.9 API 异常流程测试：无权限、analysis 不存在、artifact type 不存在
- [x] 5.10 API edge case 测试：响应不暴露敏感路径、凭据、完整日志、完整 analyzer output 或 raw snapshot
- [x] 5.11 API 过滤和排序测试：覆盖结果明细与 artifact 的多条件过滤、升降序排序和非法排序字段

## 6. E2E 和真实验证

- [x] 6.1 更新 SBOM E2E 用例，校验 `sbom_analysis_result_items` 和 `sbom_analysis_artifacts` 副作用
- [x] 6.2 更新 E2E 清理逻辑，删除本次 run 创建的结果明细和 SBOM artifact
- [x] 6.3 扩展真实 SBOM 验证记录，优先从结果明细 API 获取列表数据，从 artifact API 获取轻量摘要 JSON
- [x] 6.4 验证结果明细和 artifact 查询 API 的越权行为
- [x] 6.5 验证结果明细和 artifact 列表分页、过滤和排序行为

## 7. 验证

- [x] 7.1 运行 `python -m unittest discover -s tests` 于 `tools/sbom-analyzer`
- [x] 7.2 运行相关 Maven 单元测试
- [x] 7.3 运行 `mvn -q test`
- [x] 7.4 运行 SBOM E2E 或真实验证脚本
- [x] 7.5 运行 `openspec validate --all`
