## Why

当前后端已经具备环境、任务、SSH、源码和基础 SBOM 表结构，但还缺少可执行的 SBOM 替代分析闭环。需要先把环境采集扩展到 SBOM 所需清单，并引入独立分析器，使 Java 后端能够启动分析任务、调用工具、持久化结果并通过 API 展示。

## What Changes

- 增强环境采集结果：源侧 x86 采集已安装软件包、已安装库、独立 native/so 文件；目标侧 RISC-V 除已安装内容外，还采集软件源可用包和 provides/so 能力。
- 新增独立 SBOM 分析器运行约定：在根目录 `tools/sbom-analyzer` 下作为独立 CLI 工具存在，读取标准输入 JSON，输出标准结果 JSON。
- 新增 Java SBOM runtime：后端从数据库环境快照导出分析输入，调用独立工具，读取结果并写入 `sbom_runs`、`sbom_components`、`replacement_candidates`。
- 补齐 SBOM 分析 API：创建分析任务、查询运行列表、查询摘要、查询组件替代结果、查询采集详情。
- 将 SBOM 分析接入既有任务运行时、RabbitMQ worker、任务事件、任务日志、tool runs 和项目级 SSE。
- 补齐测试要求：Java 单元测试和 API E2E 需要覆盖正常流程、异常流程和 edge case；分析器自身也需要独立测试。
- 暂不实现 issue 管理联动、报告生成、复检 diff、复杂包知识库和自动源码构建建议。

## Capabilities

### New Capabilities
- `sbom-analysis-runtime`: 定义独立 SBOM 分析器、Java 调用运行时、结果导入和 SBOM API 的行为契约。

### Modified Capabilities
- `project-source-environment`: 环境采集需要扩展组件来源和目标仓库清单，满足 x86 与 RISC-V 替代分析输入要求。
- `task-runtime`: 增加 `SBOM_ANALYSIS` 长任务类型、worker handler、事件、日志和 tool run 接入要求。
- `backend-api-design`: 补齐 SBOM 分析 API 的请求、响应、权限和 MVP 边界。
- `backend-database-design`: 明确现有 SBOM 表和环境组件字段的使用方式，不默认新增表。

## Impact

- 后端代码：`cn.rvport.backend.environment`、`cn.rvport.backend.task`、新增 `cn.rvport.backend.sbom` 相关 controller/service/runtime/repository。
- 独立工具：根目录 `tools/sbom-analyzer`，作为 Java 后端调用的外部 CLI。
- 数据库：优先复用已存在的 `environment_snapshots`、`environment_components`、`sbom_runs`、`sbom_components`、`replacement_candidates`、`tool_runs`、`tasks`、`task_events`、`task_logs`；仅在实现确认必须时补充迁移。
- API：新增和实现 `POST /api/projects/{projectId}/sbom-analyses`、`GET /api/projects/{projectId}/sbom-analyses`、`GET /api/sbom-analyses/{analysisId}`、`GET /api/sbom-analyses/{analysisId}/components`、`GET /api/sbom-analyses/{analysisId}/collection-detail`。
- 安全：所有 SBOM API 必须执行项目访问守卫；任务输入、日志、事件和 API 响应不得泄露服务器真实路径或凭据。
- 运维：需要配置分析器可执行文件路径、工作目录、超时和输出大小限制。
