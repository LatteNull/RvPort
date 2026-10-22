## ADDED Requirements

### Requirement: 优化闭环必须提供 latest
优化闭环领域 SHALL 提供当前 Context 下的 latest 接口，用于展示当前优化轮次和后续动作摘要。

#### Scenario: 查询优化闭环 latest
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/optimization-cycles/latest`
- **THEN** 后端 SHALL 返回统一 latest 外壳
- **AND** `result` SHALL 包含当前源码版本下最新优化轮次、各节点结果聚合和 `nextAction`

#### Scenario: 优化闭环 latest 识别旧源码
- **WHEN** 只有旧源码版本的优化轮次存在
- **THEN** 后端 MUST NOT 将该结果标记为 `CURRENT`
- **AND** latest SHALL 返回 `freshness=STALE` 或 `freshness=EMPTY`
