## ADDED Requirements

### Requirement: 优化轮次必须按源码版本落库
系统 SHALL 使用优化轮次记录表达项目多轮优化边界，每个优化轮次 SHALL 绑定一个项目和一个源码版本。

#### Scenario: 首次源码版本创建优化轮次
- **WHEN** 项目首次成功激活源码版本
- **THEN** 后端 SHALL 创建该项目的第一个优化轮次
- **AND** 该轮次 SHALL 绑定当前源码版本
- **AND** `cycleNumber` SHALL 为 1

#### Scenario: 新源码版本创建下一轮
- **WHEN** 项目激活新的源码版本
- **THEN** 后端 SHALL 为该源码版本创建或复用优化轮次
- **AND** 新轮次的 `cycleNumber` SHALL 为该项目已有最大轮次号加 1
- **AND** 后端 MUST NOT 将上一源码版本的迁移输入复制到新轮次

#### Scenario: 同一源码版本不重复创建轮次
- **WHEN** 同一项目同一源码版本已经存在优化轮次
- **THEN** 后端 SHALL 复用已有优化轮次
- **AND** 后端 MUST NOT 创建重复记录

### Requirement: 优化轮次只做数据聚合展示
优化轮次运行时 SHALL 只聚合展示前序节点结果，不 SHALL 自动判断是否收敛，也不 SHALL 自动触发下游任务。

#### Scenario: 聚合当前轮次结果
- **WHEN** 用户查询当前优化概览
- **THEN** 后端 SHALL 返回当前 active 源码版本对应的优化轮次
- **AND** 响应 SHALL 聚合该轮次相关迁移输入、报告、复检、源码部署、构建、测试和测试结果比较摘要
- **AND** 响应 MUST NOT 返回完整日志、完整报告正文、完整 agent 输入、明文凭据或服务器真实路径

#### Scenario: 不做自动决策
- **WHEN** 构建、测试或测试比较结果显示失败或高风险
- **THEN** 优化轮次 API SHALL 原样展示这些事实摘要
- **AND** 后端 MUST NOT 在优化轮次中写入 `PASSED`、`FAILED`、`CONVERGED` 或等效决策结论
- **AND** 后端 MUST NOT 自动创建修复、复检、构建或测试任务

#### Scenario: 子节点尚未运行
- **WHEN** 当前轮次尚未产生报告、复检、构建、测试或测试比较记录
- **THEN** 后端 SHALL 在对应摘要中返回空状态或 `null`
- **AND** 后端 MUST NOT 因缺少子节点数据导致概览查询失败

### Requirement: 优化轮次必须支持多轮列表和详情查询
系统 SHALL 提供项目级优化轮次查询能力，使前端能够展示当前轮和历史多轮优化结果。

#### Scenario: 查询优化轮次列表
- **WHEN** 用户调用项目优化轮次列表 API
- **THEN** 后端 SHALL 校验用户对项目有访问权限
- **AND** 响应 SHALL 返回分页轮次列表
- **AND** 每条轮次 SHALL 包含轮次 ID、源码版本摘要、轮次号、展示状态、关键时间和聚合摘要

#### Scenario: 查询优化轮次详情
- **WHEN** 用户查询单个优化轮次详情
- **THEN** 后端 SHALL 校验该轮次属于请求项目
- **AND** 后端 SHALL 校验用户对项目有访问权限
- **AND** 响应 SHALL 返回该轮次完整聚合摘要和相关资源引用

#### Scenario: 越权访问优化轮次
- **WHEN** 用户访问无权限项目的优化轮次列表、概览或详情
- **THEN** 后端 SHALL 返回访问拒绝错误
- **AND** 响应 MUST NOT 泄漏项目、源码版本或轮次是否存在

### Requirement: 优化轮次查询必须支持分页过滤和排序
优化轮次列表 API SHALL 支持分页、过滤和排序，并 SHALL 使用白名单字段。

#### Scenario: 分页查询
- **WHEN** 用户查询优化轮次列表
- **THEN** 请求 SHALL 支持 `page` 和 `pageSize`
- **AND** 响应 SHALL 包含 `items`、`page`、`pageSize`、`total` 和 `hasMore`

#### Scenario: 过滤轮次
- **WHEN** 用户查询优化轮次列表并提交过滤条件
- **THEN** 后端 SHALL 支持按源码版本、轮次状态和创建时间范围过滤
- **AND** 后端 MUST NOT 将任意请求字段拼接到 SQL

#### Scenario: 排序轮次
- **WHEN** 用户查询优化轮次列表并提交排序字段
- **THEN** 后端 SHALL 支持按 `cycleNumber`、`createdAt`、`updatedAt` 和 `startedAt` 排序
- **AND** 后端 SHALL 拒绝不在白名单中的排序字段
