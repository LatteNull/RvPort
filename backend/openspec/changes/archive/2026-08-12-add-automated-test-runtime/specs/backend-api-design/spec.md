## ADDED Requirements

### Requirement: 自动化测试 API 必须支持远程测试任务
后端 API SHALL 提供自动化测试任务创建、列表、详情和取消接口，并 SHALL 以项目访问权限作为授权边界。

#### Scenario: 创建自动化测试任务
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/tests` 并提交源码版本、执行环境、测试命令或脚本、工作目录、超时配置、可选 `environmentVariables` 和可选 `reportTargets` 数组
- **THEN** 后端 SHALL 校验用户有权访问该项目
- **AND** 后端 SHALL 校验源码版本、执行环境和可选构建运行都属于该项目
- **AND** 后端 SHALL 创建 `AUTOMATED_TEST` 任务并返回 `taskId`、任务类型和初始状态
- **AND** 响应 MUST NOT 返回明文凭据、服务器真实路径或完整任务输入快照

#### Scenario: 创建带多个报告回收目标的测试任务
- **WHEN** 创建测试任务请求包含非空 `reportTargets` 数组
- **THEN** 后端 SHALL 校验数组中的每个报告目标包含合法 `type` 和 `path`
- **AND** `type=FILE` SHALL 表示明确报告文件路径
- **AND** `type=DIRECTORY` SHALL 表示报告输出目录
- **AND** 后端 SHALL 拒绝绝对路径、`..` 越界、空路径和不允许的目录扫描
- **AND** 任务完成后测试详情 SHALL 能返回已回收报告的 artifact 摘要

#### Scenario: 创建不回收报告的测试任务
- **WHEN** 创建测试任务请求未传 `reportTargets` 或传入空数组
- **THEN** 后端 SHALL 创建只回收退出码、stdout 和 stderr 的测试任务
- **AND** 后端 MUST NOT 因缺少报告路径拒绝请求

#### Scenario: 创建带环境变量的测试任务
- **WHEN** 创建测试任务请求包含 `environmentVariables`
- **THEN** 后端 SHALL 校验环境变量名格式和值长度
- **AND** 后端 SHALL 将环境变量作为任务级运行参数传递给 worker
- **AND** API 响应、任务事件和审计摘要 MUST NOT 返回环境变量明文值

#### Scenario: 测试任务依赖构建结果
- **WHEN** 创建测试任务请求包含 `buildRunId`
- **THEN** 后端 SHALL 校验该构建运行已完成且属于同一项目和源码版本
- **AND** 后端 MAY 拒绝未成功的构建运行作为自动化测试前置条件

#### Scenario: 查询项目测试列表
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/tests`
- **THEN** 后端 SHALL 返回该项目的分页测试运行列表
- **AND** 列表接口 SHALL 支持按 `sourceRevisionId`、`environmentId`、`status` 和时间范围过滤
- **AND** 列表接口 SHALL 支持按 `startedAt`、`finishedAt`、`status` 和 `createdAt` 排序
- **AND** 响应 MUST NOT 返回服务器真实路径或完整日志

#### Scenario: 查询测试详情
- **WHEN** 已登录用户调用 `GET /api/tests/{testRunId}`
- **THEN** 后端 SHALL 根据测试运行所属项目校验访问权限
- **AND** 响应 SHALL 返回测试运行 ID、项目 ID、源码版本、执行环境摘要、任务 ID、状态、退出码、输出摘要、日志引用摘要和报告 artifact 摘要
- **AND** 响应 MUST NOT 返回服务器真实路径、明文凭据或完整日志

#### Scenario: 取消测试任务
- **WHEN** 已登录用户调用 `POST /api/tests/{testRunId}/cancel`
- **THEN** 后端 SHALL 根据测试运行所属项目校验访问权限
- **AND** 后端 SHALL 复用任务取消机制取消关联任务
- **AND** 响应 SHALL 返回取消后的任务或测试运行摘要

### Requirement: 自动化测试 API 继续保持 MVP 摘要边界
自动化测试 API SHALL 只返回测试运行摘要，不 SHALL 承诺结构化测试报告解析、日志比较或用例级操作。

#### Scenario: 不提供失败用例重跑
- **WHEN** 前端请求失败用例重跑能力
- **THEN** 后端 MUST NOT 在本 change 中新增 `rerun failed cases` API

#### Scenario: 不返回用例级列表
- **WHEN** 前端查询测试详情
- **THEN** 后端 MUST NOT 返回 JUnit、CTest、pytest 或类似报告中的单个测试用例列表
- **AND** 后端 MAY 返回用户命令给出的摘要计数字段

#### Scenario: 不提供日志比较
- **WHEN** 前端请求测试日志比较结果
- **THEN** 后端 MUST NOT 在本 change 中新增测试日志比较 API

### Requirement: 构建 API 必须支持任务级环境变量
构建验证 API SHALL 允许前端为单次构建任务传入环境变量，并 SHALL 在远程构建命令或脚本执行时注入这些变量。

#### Scenario: 创建带环境变量的构建任务
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/builds` 且请求包含 `environmentVariables`
- **THEN** 后端 SHALL 校验用户有权访问该项目
- **AND** 后端 SHALL 校验环境变量名格式和值长度
- **AND** 后端 SHALL 将环境变量作为任务级运行参数传递给 worker
- **AND** 环境变量 MUST NOT 写入正式环境配置或凭据表

#### Scenario: 构建环境变量脱敏
- **WHEN** 后端返回构建详情、任务事件、审计摘要或错误信息
- **THEN** 后端 MUST NOT 返回环境变量明文值
- **AND** 名称包含 `TOKEN`、`PASSWORD`、`SECRET`、`KEY` 或 `PASS` 的变量 MUST 被视为敏感变量
