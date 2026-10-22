## Why

当前 SBOM 分析已经将结构化结果写入 `sbom_runs`、`sbom_components` 和 `replacement_candidates`，但分析完成后的轻量审计 JSON 只存在于本地验证文件中，不能通过数据库稳定追溯和查询。随着真实 x86/RISC-V 分析结果变大，前端和审计流程需要一个受权限控制、可按项目、任务和 SBOM 运行查询的轻量分析产物存储。

## What Changes

- 新增 SBOM 分析结果持久化能力，将每条分析结果明细按行入库，避免把完整结果塞进单个 JSON 字段。
- 新增 `sbom_analysis_result_items` 明细表，并同时绑定 `project_id`、`task_id` 和 `sbom_run_id`。
- 新增 `sbom_analysis_artifacts` 摘要表，只保存轻量、非敏感、可审计的运行级摘要或 manifest。
- SBOM 分析成功后保存结构化结果明细，并生成非敏感摘要 artifact，例如审计摘要 JSON、分析器输入摘要 JSON、分析器输出摘要 JSON。
- 新增 SBOM 分析结果和 artifact 查询 API，允许有项目权限的用户按分析运行分页、排序、过滤查看结果明细和摘要内容。
- 明确该能力不是通用 artifact 表，不覆盖日志、源码包、报告、归档等其他领域产物。
- 更新 E2E/真实验证要求，校验 artifact 入库、副作用、脱敏和清理。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `backend-database-design`: 增加 SBOM 分析结果明细表和专用 artifact 摘要表要求，并说明其不违反“不引入通用 artifact 表”的约束。
- `sbom-analysis-runtime`: 增加 SBOM 分析成功后按行持久化结果明细，并生成轻量分析 artifact 的要求。
- `backend-api-design`: 增加 SBOM 分析结果明细查询 API、artifact 查询 API 及权限控制要求，并将列表类接口必须支持分页、排序和过滤提升为全局 API 约定。
- `api-e2e-test-suite`: 增加 SBOM 结果明细、artifact 入库、查询、脱敏和清理验证要求。

## Impact

- 数据库：新增 Liquibase migration 创建 `sbom_analysis_result_items` 和 `sbom_analysis_artifacts`，jOOQ 代码生成脚本需要重新运行。
- 后端：影响 `cn.rvport.backend.sbom` repository/service/controller/runtime。
- API：新增 `GET /api/sbom-analyses/{analysisId}/results`、`GET /api/sbom-analyses/{analysisId}/artifacts` 和 `GET /api/sbom-analyses/{analysisId}/artifacts/{artifactType}`。
- 测试：新增 repository/service/controller/runtime 单元测试，并扩展 SBOM E2E 测试。
- 安全：artifact 内容不得保存明文凭据、私钥、token、passphrase、完整任务日志或服务器真实绝对路径。
