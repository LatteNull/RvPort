## Context

后端当前有 618 个主源码文件、130 个测试源码文件，最近一次全量执行得到 639 个测试、行覆盖率 55.22%、分支覆盖率 45.11%。约 5,194 行 Repository 代码的行覆盖率仅为 5.4%，且 Repository 分支覆盖率接近 0；此外 AutomatedTestHandler、DependencyAnalysisService、ApacheMinaSshClientAdapter、ProcessGitClientAdapter、归档与报告相关服务仍存在较大缺口。

现有测试以 Mockito 和 standalone MockMvc 为主，但有 5 个 `@SpringBootTest` 会加载完整应用上下文，真实 Liquibase 测试依赖显式外部 PostgreSQL，真实 SSH smoke test 默认跳过。普通单元测试需要在没有 PostgreSQL、Redis、RabbitMQ、MinIO、SSH、外部 HTTP、Agent CLI 和 Docker 的环境中稳定运行。

本 change 覆盖整个后端测试体系。业务逻辑保持不变；测试若暴露疑似业务错误，只记录证据，不顺带修改尚未确认的行为。

## Goals / Non-Goals

**Goals:**

- 使后端项目自有可执行代码的整体行覆盖率和分支覆盖率均达到至少 90%。
- 对本次盘点涉及的业务包建立不低于 90% 的覆盖约束，防止高覆盖代码掩盖低覆盖模块。
- 所有新增测试覆盖正常流程、异常流程和 edge case，并包含有效行为断言。
- 普通单元测试可在纯 JVM、无网络、无 Docker、无外部服务条件下独立运行。
- 尽量只修改测试代码；确需调整生产代码时，仅提取可注入边界或拆分纯函数，不改变现有行为。
- 建立测试发现疑似业务缺陷的记录与阻塞规则。

**Non-Goals:**

- 不在本 change 中修复测试发现但尚未经过产品或规格确认的业务缺陷。
- 不使用 Testcontainers、共享开发数据库或真实远程环境来换取单元测试覆盖率。
- 不以 API E2E、真实联通测试、启动成功或静态检查代替单元测试。
- 不为达到数字而排除业务类、删除分支、添加无断言测试或只调用 getter。

## Decisions

### 1. 以应用边界模拟外部连接

Service 和 Handler 测试模拟现有 Repository、CacheClient、QueueClient、ObjectStorageService、SshClientAdapter、GitClientAdapter、AgentRuntimeAdapter 或 HTTP client 边界的返回值、超时和异常，不连接真实服务。优先模拟项目自有接口，而不是模拟第三方客户端内部的长调用链。

数据库 Repository 本身就是待测边界，不能把 Repository 整体 mock 掉。其测试使用 jOOQ `MockConnection`/`MockDataProvider` 在 JDBC Connection 边界返回模拟 Record，并校验 SQL 类型、关键条件、bind 值、排序、分页、批处理和映射结果。相比 H2，该方案不会因 PostgreSQL JSONB、RETURNING、ON CONFLICT 等方言差异制造伪兼容；相比 Testcontainers，它不依赖 Docker。

### 2. 建立可复用的 Repository 测试工具

在测试源码中建立统一 fixture，用 PostgreSQL dialect 创建 `DSLContext`，捕获每次 jOOQ execution，并按测试声明返回 `MockResult`。fixture 需要支持：

- select/count/insert/update/delete/returning；
- 单条、空结果、多条和 null 字段；
- batch execution；
- JSONB、UUID、时间、枚举与生成 Record；
- 数据库异常和非预期 SQL 的立即失败；
- 对 SQL 结构和 bind values 的可读断言。

Repository 测试关注本项目负责的查询构造和映射，不宣称替代 PostgreSQL 方言兼容集成测试。

### 3. 按风险和覆盖收益分波次推进

```text
隔离基线
   |
   +-- Repository 查询与映射
   +-- 低覆盖 Handler / Service
   +-- Controller / DTO / Validator
   +-- 外部进程与协议 Adapter
   |
   +-- 全量缺口复查 -> 90% 行/分支门槛
```

第一波先确保普通测试生命周期不会发起真实连接。第二波覆盖约 4,911 条未覆盖 Repository 行。随后处理高缺口 Handler、Service、Controller 和 Adapter，并用最终 JaCoCo 报告反复定位剩余分支。每个模块都按正常、异常、边界组织测试，而不是只按方法逐行调用。

### 4. Spring 测试采用最小上下文

Controller 优先使用 standalone MockMvc；配置绑定优先使用 `ApplicationContextRunner` 或直接实例化配置对象。必须加载 Spring 上下文的少数测试需要显式禁用 Liquibase、worker/listener、Redis SSE subscriber、对象存储初始化和定时任务，并提供所有外部端口的 mock bean。普通 `mvn test` 不得产生连接重试日志。

Liquibase/PostgreSQL 验证和真实 SSH smoke test继续作为显式集成/联通测试存在，但从普通单元测试生命周期和覆盖率验收中清晰隔离，不用于填充业务覆盖率。

### 5. 仅允许等价的可测试性重构

若类直接构造 `ProcessBuilder`、`HttpClient`、SSH client 或静态时钟，导致无法稳定覆盖异常路径，可提取包内可见的小型执行接口、工厂或纯函数，并保持原调用顺序、参数、默认值、错误码和副作用不变。每次此类调整必须先有特征测试锁定当前行为，并在任务记录中说明必要性。

不为了测试公开 private 方法。优先通过 public 行为覆盖；复杂解析或决策逻辑可以等价提取为 package-private 纯函数。

### 6. 疑似业务缺陷不随测试工作修复

- 现有规格明确且测试证明实现违反规格：保留最小复现证据，将问题写入 change 下的 `test-discovered-issues.md`，测试保持失败，相关任务和覆盖率验收不得标记完成，等待独立修复 change。
- 规格或产品意图不明确：用 characterization test 锁定当前行为，并在问题记录中写明预期假设、实际结果、影响范围和待确认问题；不得擅自改变生产逻辑。
- 不得通过随意 `@Disabled`、吞掉异常或降低断言来隐藏发现的问题。

### 7. 覆盖率门槛覆盖整体和业务包

JaCoCo 继续只排除 `cn/rvport/backend/jooq/**` 生成代码。验收至少包含：

- BUNDLE 行覆盖率 >= 90%；
- BUNDLE 分支覆盖率 >= 90%；
- 项目自有业务 package 行覆盖率 >= 90%；
- 有可执行分支的业务 package 分支覆盖率 >= 90%。

覆盖统计必须包含未被测试加载的生产类。报告固定输出到 `target/site/jacoco/index.html`，同时保留 CSV/XML 供自动核验。

## Risks / Trade-offs

- [Repository mock 只能验证查询构造，不能证明真实 PostgreSQL 执行兼容] -> 保留显式 Liquibase/数据库集成测试，但不把它并入普通单元测试或 90% 覆盖来源。
- [全包 90% 分支覆盖工作量大] -> 按缺口排序分波次交付，但最终门槛未达到前不宣称完成。
- [过度 mock 可能复制实现细节] -> 在应用边界模拟结果，断言业务结果与关键 SQL 语义，避免逐节点 mock fluent API。
- [可测试性重构意外改变行为] -> 先增加特征测试，限制为依赖注入和纯函数提取，并单独审查生产代码 diff。
- [疑似缺陷导致覆盖工作阻塞] -> 用问题台账明确证据和决策人，拆分独立修复 change，不在覆盖任务中暗改逻辑。
- [完整测试集执行时间增长] -> 避免 Spring 全上下文和外部重试，复用 fixture；以稳定性优先，不通过降低覆盖范围换速度。

## Migration Plan

1. 固化当前 JaCoCo 基线和测试清单，建立离线执行检查。
2. 引入纯测试范围的 jOOQ mock fixture，并用一个代表性 Repository 验证模式。
3. 分模块回补 Repository、Service、Handler、Controller、Adapter 测试。
4. 对必要的生产代码执行等价可测试性重构，并记录原因。
5. 逐步启用 package 与 bundle 覆盖率门槛，最终执行 `mvn -B clean verify`。
6. 若出现疑似业务缺陷，暂停对应验收并登记，不回滚已完成的独立测试。

本 change 不涉及运行时数据迁移。测试结构出现问题时可回退测试 helper 和相关测试；任何生产代码结构调整必须可单独回退且不影响外部 API。

## Open Questions

无。执行期间发现的业务语义疑点统一进入问题台账，不在本设计中预判答案。
