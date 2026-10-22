## ADDED Requirements

### Requirement: API E2E 必须覆盖依赖分析主链路
API E2E 测试套件 SHALL 覆盖构建事实驱动依赖分析的正常流程、异常流程、edge case 和清理。

#### Scenario: 覆盖前置 source-only 构建
- **WHEN** E2E 运行依赖分析模块
- **THEN** 测试 SHALL 创建或复用项目、源码版本、运行双环境和 source-only 构建运行
- **AND** 测试 SHALL 验证构建记录包含 `buildScope=SOURCE_ONLY`

#### Scenario: 覆盖依赖分析任务
- **WHEN** source-only 构建成功
- **THEN** E2E SHALL 调用依赖分析创建 API
- **AND** E2E SHALL 等待 `DEPENDENCY_ANALYSIS` 任务进入终态
- **AND** E2E SHALL 校验依赖分析运行、结果明细、任务事件、日志和 artifact 副作用

#### Scenario: 覆盖依赖分析查询
- **WHEN** 依赖分析成功产生结果
- **THEN** E2E SHALL 查询依赖分析列表、详情、结果列表、结果详情和 artifact 下载
- **AND** E2E SHALL 验证分页、过滤、排序和敏感信息边界

#### Scenario: 覆盖依赖分析异常流程
- **WHEN** 没有成功 source/x86 构建、缺少运行双环境、环境不属于项目或用户无权限
- **THEN** E2E SHALL 验证 API 返回明确错误
- **AND** E2E SHALL 验证不会创建成功态依赖分析结果

#### Scenario: 覆盖迁移输入导入
- **WHEN** 依赖分析结果存在
- **THEN** E2E SHALL 将 `DEPENDENCY_RESULT` 导入迁移输入
- **AND** E2E SHALL 验证重复导入幂等跳过和详情回查 evidence

#### Scenario: SBOM E2E 兼容
- **WHEN** 保留 SBOM E2E 用例
- **THEN** 测试 SHALL 明确标记该覆盖为 deprecated 兼容验证
- **AND** 新依赖分析 E2E MUST NOT 依赖旧 SBOM E2E 先运行
