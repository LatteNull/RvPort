## MODIFIED Requirements

### Requirement: E2E 测试必须覆盖迁移报告 API
API E2E 测试套件 SHALL 覆盖迁移报告 API 的正常流程、异常流程和 edge case。测试 SHALL 使用节点内确认后的迁移输入 reference，并 SHALL 验证零 confirmed 输入也能生成全零报告。

#### Scenario: 正常生成迁移评估报告
- **WHEN** E2E 创建项目、创建源码版本、准备 KB 或依赖分析来源结果，并通过节点内确认规则产生至少一条 `CONFIRMED` reference
- **THEN** E2E SHALL 调用报告创建 API
- **AND** E2E SHALL 等待报告任务成功
- **AND** E2E SHALL 校验报告详情、报告输入快照、HTML 下载和 JSON 下载均可用
- **AND** E2E SHALL 校验报告输出制品已写入对象存储元数据
- **AND** API 响应 MUST NOT 暴露 bucket、object key 或服务器真实路径

#### Scenario: 未确认输入生成全零报告
- **WHEN** E2E 在有效源码版本下不存在迁移输入，或只存在 `CANDIDATE`、`EXCLUDED` 迁移输入
- **THEN** 报告 readiness SHALL 允许生成报告
- **AND** 报告生成任务 SHALL 成功
- **AND** 报告输入数量、高风险数量和预计工作量 SHALL 为 0
- **AND** HTML 与 JSON 报告制品 SHALL 可下载

#### Scenario: 报告快照不可变
- **WHEN** E2E 成功生成报告后修改原迁移输入状态或备注
- **THEN** 后续查询报告输入快照和下载 JSON 报告 SHALL 保持生成时内容不变

#### Scenario: 越权访问报告失败
- **WHEN** E2E 使用普通用户访问其他用户项目的报告详情、输入快照或下载接口
- **THEN** 后端 SHALL 拒绝访问

#### Scenario: 非法下载格式失败
- **WHEN** E2E 调用报告下载接口并提交不支持的 `format`
- **THEN** 后端 SHALL 返回统一业务错误

### Requirement: API E2E 必须覆盖任务日志内容读取
API E2E 测试套件 SHALL 覆盖完成态任务日志内容读取 API 的正常流程、异常流程和 edge case，并 SHALL 使用按时间正序追加的真实日志文件顺序。

#### Scenario: 默认读取三类日志
- **WHEN** E2E 创建包含 merged/stdout/stderr 日志的任务 fixture 并调用 `GET /api/tasks/{taskId}/log-content`
- **THEN** 响应 SHALL 包含三类日志
- **AND** 每类默认最多返回文件尾部的最新展示页 100 行
- **AND** 每类返回页内部 SHALL 按日志产生时间正序排列

#### Scenario: 单类日志读取
- **WHEN** E2E 调用 `GET /api/tasks/{taskId}/log-content?types=stdout`
- **THEN** 响应 SHALL 只包含 stdout 日志内容
- **AND** 响应 SHALL 不包含 merged 或 stderr 内容

#### Scenario: 多类不同 offset
- **WHEN** E2E 使用不同 offset 请求 merged、stdout 和 stderr
- **THEN** 每类日志 SHALL 从各自文件尾部跳过对应数量的最新行后返回文本片段
- **AND** 每个文本片段 SHALL 保持页内时间正序
- **AND** `hasMore` SHALL 正确表达是否还有更早日志

#### Scenario: 正序追加日志首屏返回最新内容
- **WHEN** E2E 创建文件头为最早日志、文件尾为最新日志的任务日志 fixture
- **AND** E2E 调用 `GET /api/tasks/{taskId}/log-content?types=merged&mergedOffset=0&lines=2`
- **THEN** 响应 SHALL 返回文件尾部的最新两行
- **AND** 两行 SHALL 按产生时间正序排列
- **AND** 响应 MUST NOT 返回文件头部的最早两行

#### Scenario: offset 返回更旧内容
- **WHEN** E2E 创建文件头为最早日志、文件尾为最新日志的任务日志 fixture
- **AND** E2E 调用 `GET /api/tasks/{taskId}/log-content?types=merged&mergedOffset=2&lines=2`
- **THEN** 响应 SHALL 跳过最新两行并返回其前方更旧的日志
- **AND** 返回页内部 SHALL 保持时间正序
- **AND** `hasMore` SHALL 正确表达是否仍有更旧日志

#### Scenario: 非法参数
- **WHEN** E2E 使用未知日志类型、负数 offset 或超过上限的 lines
- **THEN** API SHALL 返回统一参数校验错误

#### Scenario: 越权读取日志内容
- **WHEN** 普通用户读取其他用户项目任务的日志内容
- **THEN** API SHALL 返回安全错误
- **AND** 响应 MUST NOT 泄漏日志是否存在

#### Scenario: 构建和测试详情暴露日志引用
- **WHEN** E2E 查询构建详情和自动化测试详情
- **THEN** 响应 SHALL 暴露 merged/stdout/stderr 日志引用或明确缺失状态
- **AND** 前端可使用同一个任务日志内容接口读取这些日志内容

### Requirement: E2E 必须覆盖评估报告 readiness 和输入预览
API E2E 测试套件 SHALL 覆盖迁移输入合并节点移除后的评估报告页 readiness、输入预览、生成报告和历史快照行为，并 SHALL 将 confirmed 输入数量作为统计事实而非生成门禁。

#### Scenario: readiness 展示可生成状态
- **WHEN** E2E 创建项目、激活源码版本并准备至少一条 `CONFIRMED` migration input reference
- **THEN** E2E SHALL 调用评估报告 readiness API
- **AND** 响应 SHALL 返回 `canGenerate=true`
- **AND** 响应 SHALL 返回 confirmed 输入数量、来源统计和当前源码版本摘要

#### Scenario: readiness 展示零 confirmed 输入
- **WHEN** E2E 创建源码版本但不存在 reference，或只准备 `CANDIDATE`、`EXCLUDED` reference
- **THEN** E2E SHALL 调用评估报告 readiness API
- **AND** 响应 SHALL 返回 `canGenerate=true`
- **AND** confirmed 输入数量 SHALL 为 0
- **AND** blockers MUST NOT 包含没有 confirmed 输入的错误码

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
