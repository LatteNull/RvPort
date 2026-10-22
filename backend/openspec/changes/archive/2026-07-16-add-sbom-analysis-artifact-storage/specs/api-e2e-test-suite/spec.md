## MODIFIED Requirements

### Requirement: API E2E 必须覆盖 SBOM 分析验证和清理
API E2E 测试套件 SHALL 覆盖 SBOM 分析相关的端到端验证入口、真实副作用检查、artifact 入库检查和测试数据清理。

#### Scenario: 覆盖 SBOM 分析主链路
- **WHEN** 运行 SBOM API E2E 用例且基础设施与后端服务可用
- **THEN** 测试 SHALL 创建或复用测试项目、源环境、目标环境和必要快照
- **AND** 测试 SHALL 创建 `SBOM_ANALYSIS` 任务并等待任务终态
- **AND** 测试 SHALL 校验 `sbom_runs`、`sbom_components`、`replacement_candidates`、`sbom_analysis_artifacts`、`tasks`、`task_events` 和 `tool_runs` 的真实副作用

#### Scenario: 覆盖 SBOM artifact 查询
- **WHEN** SBOM API E2E 用例完成一次成功分析
- **THEN** 测试 SHALL 调用 `GET /api/sbom-analyses/{analysisId}/artifacts`
- **AND** 测试 SHALL 校验列表包含预期 artifact 类型
- **AND** 测试 SHALL 调用 `GET /api/sbom-analyses/{analysisId}/artifacts/{artifactType}`
- **AND** 测试 SHALL 校验 artifact 关联正确的 `project_id`、`task_id` 和 `sbom_run_id`

#### Scenario: 覆盖 SBOM 分析异常流程
- **WHEN** 运行 SBOM API E2E 异常用例
- **THEN** 测试 SHALL 覆盖源快照不存在、目标快照不存在、环境不属于项目、无项目权限和分析器失败
- **AND** 测试 SHALL 验证失败不会写入成功态 SBOM 结果
- **AND** 测试 SHALL 验证失败不会写入成功态 SBOM artifact

#### Scenario: 覆盖 SBOM 分析 edge case
- **WHEN** 运行 SBOM API E2E 边界用例
- **THEN** 测试 SHALL 覆盖空组件清单、仓库候选为空但有 warning、同名不同架构组件、重复仓库候选和输出脱敏
- **AND** 测试 SHALL 验证 API 响应和 artifact 内容不暴露服务器真实敏感路径或凭据

#### Scenario: 清理 SBOM 验证数据
- **WHEN** SBOM API E2E 或真实验证流程结束
- **THEN** 清理流程 SHALL 删除本次 run id 创建的项目、环境、快照、组件、SBOM 运行、替代候选、SBOM artifact、任务、事件、日志、执行记录和临时 runtime 文件
- **AND** 清理流程 SHALL 保留明确标记为非敏感的验证记录
- **AND** 清理失败时 SHALL 返回非零退出码并说明未清理资源
