## MODIFIED Requirements

### Requirement: 后端骨架提供健康检查和基础测试
后端应用 SHALL 提供最小健康检查接口、可运行且不依赖外部服务的 Maven 单元测试命令，并 SHALL 为后续 API change 预留独立 E2E 测试约定。后端项目自有可执行代码的整体及业务包行覆盖率和分支覆盖率 SHALL 均达到至少 90%。

#### Scenario: 调用健康检查
- **WHEN** 客户端调用 `GET /health` 或 `GET /api/health`
- **THEN** 后端 SHALL 返回统一响应包络
- **AND** 响应 SHALL 表示应用进程可用

#### Scenario: 在无外部服务环境运行单元测试
- **WHEN** 开发者在没有 PostgreSQL、Redis、RabbitMQ、MinIO、SSH、外部 HTTP 服务、Agent CLI 和 Docker 的环境执行普通 Maven 单元测试
- **THEN** 应用 SHALL 完成全部普通单元测试
- **AND** 测试 MUST NOT 发起真实网络连接或依赖宿主机外部服务状态
- **AND** 外部依赖的成功、失败、超时和异常 SHALL 通过 mock 应用客户端、适配器或连接边界的返回值进行验证
- **AND** 独立 API E2E、真实数据库迁移测试和真实环境 smoke test MUST NOT 随普通 `mvn test` 自动运行

#### Scenario: 编写后续 change 测试
- **WHEN** 后续 OpenSpec change 涉及后端代码实现
- **THEN** 该 change SHALL 在任务或设计中明确测试覆盖范围
- **AND** 测试 SHALL 覆盖正常流程、异常流程和 edge case
- **AND** 如果该 change 不补充测试，必须在任务或设计中说明原因

#### Scenario: 编写后续 API change 测试
- **WHEN** 后续 OpenSpec change 新增或修改 HTTP API
- **THEN** 该 change SHALL 同步新增或更新独立 API E2E 测试用例
- **AND** E2E 测试 SHALL 覆盖该 API 的正常流程、异常流程和 edge case
- **AND** 如果该 API 不适合 E2E 测试，change 的设计或任务 MUST 说明原因

#### Scenario: 覆盖正常流程
- **WHEN** 为后端能力编写单元测试、API 测试、轻量集成测试或独立 E2E 测试
- **THEN** 测试 SHALL 覆盖合法输入下的成功创建、查询、更新、任务投递或状态流转
- **AND** 测试 SHALL 对业务结果和关键协作行为包含有效断言

#### Scenario: 覆盖异常流程
- **WHEN** 为后端能力编写单元测试、API 测试、轻量集成测试或独立 E2E 测试
- **THEN** 测试 SHALL 覆盖鉴权失败、资源不存在、参数非法、状态不允许、外部依赖不可用、凭据或敏感配置缺失等错误路径
- **AND** 单元测试 SHALL 通过模拟依赖返回值或异常触发错误路径

#### Scenario: 覆盖 edge case
- **WHEN** 为后端能力编写单元测试、API 测试、轻量集成测试或独立 E2E 测试
- **THEN** 测试 SHALL 覆盖空列表、可选字段为空、重复请求、边界分页、边界数值、重复状态切换、幂等行为、脱敏输出和路径隐藏等边界场景

#### Scenario: 测试 jOOQ Repository
- **WHEN** 单元测试验证 Repository 的查询构造和数据映射
- **THEN** 测试 SHALL 在 jOOQ/JDBC 连接边界提供模拟结果
- **AND** 测试 SHALL 验证关键 SQL 条件、绑定参数、排序、分页、空结果、返回 Record 映射和数据库异常
- **AND** 测试 MUST NOT 连接真实 PostgreSQL 或以 mock Repository 自身代替 Repository 测试

#### Scenario: 回补既有测试覆盖缺口
- **WHEN** 盘点发现既有后端能力缺少正常流程、异常流程或 edge case 覆盖
- **THEN** 后端 SHALL 通过独立单元测试回补适合在单元层验证的缺口
- **AND** 如果某个缺口不适合在当前测试层回补，change 的设计或任务 MUST 说明不适用原因和替代验证方式
- **AND** API E2E、真实联通或编译成功 MUST NOT 替代项目自有业务逻辑的单元测试覆盖

#### Scenario: 验收覆盖率
- **WHEN** 开发者执行后端覆盖率验收命令
- **THEN** JaCoCo SHALL 将未被测试加载的项目自有生产类纳入统计
- **AND** BUNDLE 行覆盖率和分支覆盖率 SHALL 分别达到至少 90%
- **AND** 项目自有业务 package 的行覆盖率以及存在分支时的分支覆盖率 SHALL 分别达到至少 90%
- **AND** 默认仅可排除自动生成的 jOOQ 源码，不得排除项目自有业务逻辑或缩小统计范围
- **AND** 无有效断言的调用、空测试或仅加载类 MUST NOT 作为满足覆盖率的手段

#### Scenario: 为测试调整生产代码结构
- **WHEN** 现有实现直接创建外部连接、进程或静态依赖，导致异常路径无法稳定进行单元测试
- **THEN** 实现 MAY 提取可注入执行边界或纯函数
- **AND** 调整 MUST 保持原调用顺序、输入、输出、错误码和副作用语义不变
- **AND** 调整前 SHALL 通过特征测试锁定现有行为

#### Scenario: 单元测试发现明确的规格违例
- **WHEN** 新增单元测试证明现有业务实现违反已确认规格
- **THEN** 本 change MUST 记录最小复现、预期行为、实际行为和影响范围
- **AND** 本 change MUST NOT 未经确认直接修改该业务逻辑
- **AND** 对应测试和质量验收 MUST 保持未通过，直到独立修复 change 处理完成

#### Scenario: 单元测试发现语义尚不明确的可疑行为
- **WHEN** 新增单元测试发现可能错误但缺少明确规格依据的行为
- **THEN** 测试 SHALL 以 characterization test 锁定当前行为
- **AND** 本 change SHALL 登记该疑点和待确认决策
- **AND** 本 change MUST NOT 擅自把假设作为新业务行为实现
