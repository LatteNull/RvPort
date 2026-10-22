## 1. 数据库与代码生成

- [x] 1.1 新增 Liquibase changelog 创建 `optimization_cycles` 表，包含项目、源码版本、轮次号、展示状态、轻量摘要和时间字段。
- [x] 1.2 为 `optimization_cycles` 增加 `(project_id, source_revision_id)`、`(project_id, cycle_number)` 唯一约束和查询索引。
- [x] 1.3 编写历史数据迁移逻辑，按每个项目的源码版本创建初始优化轮次，并将 active 源码版本对应轮次标记为 `ACTIVE`。
- [x] 1.4 实际运行 Liquibase 校验空库和已有数据场景，并运行 jOOQ 生成脚本。

## 2. 领域模型与轮次创建

- [x] 2.1 新增优化轮次枚举、DTO、列表查询对象、响应对象和聚合摘要结构。
- [x] 2.2 新增 `OptimizationCycleRepository`，支持创建、复用、查询当前轮次、分页列表和详情。
- [x] 2.3 新增 `OptimizationCycleService`，实现按源码版本创建或复用轮次、计算项目内轮次号和状态更新。
- [x] 2.4 接入源码版本激活流程，在源码包上传或 Git 同步激活源码版本后创建或复用优化轮次。
- [x] 2.5 处理并发激活和唯一约束冲突，确保同一源码版本不会创建重复轮次。

## 3. 聚合摘要实现

- [x] 3.1 聚合当前源码版本的迁移输入数量，包含 `CANDIDATE`、`CONFIRMED` 和 `EXCLUDED` 计数。
- [x] 3.2 聚合当前源码版本的最新迁移评估报告摘要，包含报告状态、风险等级、高风险数量和工作量摘要。
- [x] 3.3 聚合当前轮次与上一源码版本的复检状态和差异摘要。
- [x] 3.4 聚合当前源码版本的源码部署、构建验证、自动化测试和测试结果比较摘要。
- [x] 3.5 确保聚合摘要只返回资源引用和安全摘要，不返回完整日志、完整报告正文、agent 输入、对象存储内部 key 或服务器真实路径。

## 4. API 实现

- [x] 4.1 新增 `GET /api/projects/{projectId}/optimization/overview`，返回当前 active 源码版本对应轮次聚合。
- [x] 4.2 新增 `GET /api/projects/{projectId}/optimization/cycles`，支持分页、过滤和排序。
- [x] 4.3 新增 `GET /api/projects/{projectId}/optimization/cycles/{cycleId}`，返回单轮详情。
- [x] 4.4 所有优化轮次 API 接入项目访问权限校验，越权时不泄漏项目、源码版本或轮次是否存在。
- [x] 4.5 更新后端 API 文档，明确优化轮次 API 只做展示聚合，不触发任务、不做收敛决策。

## 5. 测试与验证

- [x] 5.1 补充 repository/service 单元测试，覆盖首次源码版本、新源码版本、重复源码版本、并发唯一约束和历史迁移。
- [x] 5.2 补充聚合摘要单元测试，覆盖有完整数据、缺少子节点数据、多个历史轮次和敏感字段不返回。
- [x] 5.3 补充 controller/API 测试，覆盖正常流程、异常流程和 edge case。
- [x] 5.4 补充独立 E2E 模块，创建项目、导入多轮源码版本并验证优化轮次列表、详情和当前概览。
- [x] 5.5 运行 `mvn test`。
- [x] 5.6 运行相关 E2E 模块并清理测试数据。
- [x] 5.7 运行 `openspec validate add-optimization-cycle-runtime --strict`。
