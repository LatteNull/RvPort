## 1. 通用模型和查询基础

- [x] 1.1 增加 `ProjectContextSnapshot`，集中读取当前 active source revision 和当前 runtime environment version
- [x] 1.2 增加 latest 统一响应 DTO，包含 `context`、`freshness`、`execution` 和领域 `result`
- [x] 1.3 增加 readiness 响应 DTO，包含 `stageId`、`context` 和 prerequisite 列表
- [x] 1.4 增加 prerequisite 状态、stageId、reasonCode 的稳定枚举或常量
- [x] 1.5 为任务和领域运行记录补充 latest 查询所需 repository 方法

## 2. 阶段 Readiness

- [x] 2.1 新增 `GET /api/projects/{projectId}/readiness?stageId={stageId}` controller 和 service
- [x] 2.2 实现 `kb` readiness，返回 `ACTIVE_SOURCE`
- [x] 2.3 实现 `x86-build` readiness，返回 `ACTIVE_SOURCE`、`SOURCE_ENVIRONMENT` 和可用的 `SOURCE_DEPLOYMENT`
- [x] 2.4 实现 `rv-dependency-analysis` readiness，返回 `X86_BUILD` 和 `TARGET_ENVIRONMENT`
- [x] 2.5 实现 `report` readiness，返回 `KB_SCAN`、`DEPENDENCY_ANALYSIS`、`INCLUDED_FINDINGS` 和 `COMPARABLE_REPORT`
- [x] 2.6 实现 `build` readiness，返回 `ACTIVE_SOURCE`、`SOURCE_ENVIRONMENT` 和 `TARGET_ENVIRONMENT`
- [x] 2.7 实现 `test` readiness，返回 `BUILD_VALIDATION`
- [x] 2.8 实现 `archive` readiness，返回当前 Context 下可归档内容事实

## 3. 领域 Latest

- [x] 3.1 增加 `GET /api/projects/{projectId}/kb-scans/latest`
- [x] 3.2 增加 `GET /api/projects/{projectId}/builds/latest?mode=SOURCE_ONLY|VALIDATION`
- [x] 3.3 增加 `GET /api/projects/{projectId}/dependency-analyses/latest`
- [x] 3.4 调整 `GET /api/projects/{projectId}/reports/evaluation/latest` 为统一 latest 外壳
- [x] 3.5 增加 `GET /api/projects/{projectId}/automated-tests/latest`
- [x] 3.6 增加 `GET /api/projects/{projectId}/optimization-cycles/latest`
- [x] 3.7 增加 `GET /api/projects/{projectId}/archives/latest`，并保留或兼容现有 archive overview
- [x] 3.8 确保 latest 不跳过当前 Context 下最新失败、取消或运行中记录

## 4. 写接口二次校验

- [x] 4.1 为依赖分析创建接口接入 `X86_BUILD` 和 `TARGET_ENVIRONMENT` 当前事实校验
- [x] 4.2 为自动化测试创建接口接入 `BUILD_VALIDATION` 当前事实校验
- [x] 4.3 为评估报告生成接口接入当前输入和报告 readiness 校验
- [x] 4.4 为归档创建接口接入当前可归档内容校验
- [x] 4.5 统一 `PREREQUISITE_NOT_SATISFIED` 错误结构，返回 `stageId`、`prerequisite`、`status` 和 `reasonCode`

## 5. 测试与验证

- [x] 5.1 增加 readiness service 单元测试，覆盖正常流程、异常流程和 edge case
- [x] 5.2 增加 latest service/controller 单元测试，覆盖无记录、当前失败、旧 Context 和权限隔离
- [x] 5.3 更新 API E2E，覆盖阶段 readiness 和领域 latest 外壳
- [x] 5.4 更新 API E2E，覆盖 Context 改变后写接口拒绝创建任务
- [x] 5.5 运行 `mvn test`
- [x] 5.6 运行相关 E2E 模块
- [x] 5.7 运行 `openspec validate --change add-stage-readiness-and-domain-latest --strict`
