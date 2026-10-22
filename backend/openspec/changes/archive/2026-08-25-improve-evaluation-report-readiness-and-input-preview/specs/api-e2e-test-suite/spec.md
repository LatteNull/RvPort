## ADDED Requirements

### Requirement: E2E 必须覆盖评估报告 readiness 和输入预览
API E2E 测试套件 SHALL 覆盖迁移输入合并节点移除后的评估报告页 readiness、输入预览、生成报告和历史快照行为。

#### Scenario: readiness 展示可生成状态
- **WHEN** E2E 创建项目、激活源码版本并准备至少一条 `CONFIRMED` migration input reference
- **THEN** E2E SHALL 调用评估报告 readiness API
- **AND** 响应 SHALL 返回 `canGenerate=true`
- **AND** 响应 SHALL 返回 confirmed 输入数量、来源统计和当前源码版本摘要

#### Scenario: readiness 展示没有 confirmed 输入
- **WHEN** E2E 创建源码版本但只准备 `CANDIDATE` 或 `EXCLUDED` reference
- **THEN** E2E SHALL 调用评估报告 readiness API
- **AND** 响应 SHALL 返回 `canGenerate=false`
- **AND** blockers SHALL 包含没有 confirmed 输入的稳定错误码

#### Scenario: readiness 提示低风险候选
- **WHEN** E2E 准备 `LOW` 风险 dependency 或 KB 结果并保持其 reference 为 `CANDIDATE`
- **THEN** readiness SHALL 返回 LOW candidate 数量
- **AND** warnings SHALL 提示低风险候选未进入报告

#### Scenario: 输入预览分页过滤排序
- **WHEN** E2E 调用评估报告输入预览 API
- **THEN** 响应 SHALL 使用分页格式
- **AND** E2E SHALL 校验按 `sourceType`、`status`、`riskLevel` 和关键字过滤有效
- **AND** E2E SHALL 校验非法排序字段返回统一业务错误

#### Scenario: 人工加入和撤回影响 readiness
- **WHEN** E2E 将 LOW candidate 更新为 `CONFIRMED`
- **THEN** readiness 的 confirmed 数量 SHALL 增加
- **AND** 报告生成 SHALL 使用该输入
- **WHEN** E2E 将默认 confirmed 输入更新为 `EXCLUDED`
- **THEN** readiness 的 confirmed 数量 SHALL 减少
- **AND** 后续报告生成 MUST NOT 使用该输入

#### Scenario: 报告详情区分快照和当前输入状态
- **WHEN** E2E 成功生成报告后修改同源码版本下 migration input reference 的状态或备注
- **THEN** 报告输入快照和 JSON 下载 SHALL 保持生成时内容
- **AND** 报告详情的当前输入摘要 SHALL 反映修改后的状态

#### Scenario: 越权访问 readiness 和输入预览失败
- **WHEN** 普通用户访问其他用户项目的评估报告 readiness 或输入预览接口
- **THEN** 后端 SHALL 拒绝访问
- **AND** 响应 MUST NOT 泄露服务器路径、明文凭据或其他项目详情
