## 1. 固化基线与独立运行边界

- [x] 1.1 运行并记录当前全量测试数量、跳过项、JaCoCo 行/分支覆盖率、各 package 与高缺口 class 清单
- [x] 1.2 建立普通单元测试专用配置，禁用 Liquibase、Rabbit listener、Redis SSE subscriber、对象存储初始化、worker 与定时任务等外部副作用
- [x] 1.3 将真实 PostgreSQL/Liquibase、SSH smoke 和其他联通测试与普通 `mvn test` 生命周期明确隔离，并保留显式运行入口
- [x] 1.4 在所有外部服务不可用且不启动 Docker 的条件下运行普通测试，确认无真实连接、重试等待或依赖宿主机 CLI 的行为

## 2. 建立纯 JVM 测试工具

- [x] 2.1 增加基于 jOOQ `MockConnection`/`MockDataProvider` 的 PostgreSQL dialect 测试 fixture，支持捕获 SQL、bind values 和返回 `MockResult`
- [x] 2.2 为 fixture 增加 select/count/returning、空结果、多结果、batch、JSONB/UUID/时间/枚举映射和数据库异常自测
- [x] 2.3 增加统一的测试数据 builder/fixture，减少 Project、Task、Environment、SourceRevision、Artifact 与运行记录构造重复
- [x] 2.4 建立 `test-discovered-issues.md` 记录格式，包含最小复现、规格依据、实际行为、影响范围、characterization test 和待确认项

## 3. 回补核心 Repository 测试

- [x] 3.1 覆盖 TaskRepository、TaskEventRepository、TaskLogRepository、TaskLogEventRepository、TaskRuntimeHandleRepository、TaskSecretPayloadRepository、TaskScriptPayloadRepository 与 ToolRunRepository 的正常、异常和边界路径
- [x] 3.2 覆盖 ProjectRepository、ProjectRuntimeEnvironmentRepository、EnvironmentRepository、CredentialRepository、SourceRepository、SourceCompareRepository 与 SourceDeployRepository 的正常、异常和边界路径
- [x] 3.3 覆盖 BuildValidationRepository、AutomatedTestRepository、TestComparisonRepository 与 ReportComparisonRepository 的正常、异常和边界路径
- [x] 3.4 覆盖 DependencyAnalysisRepository、DependencyAutoFixRepository、KbScanRepository 与 KbAiExtensionRepository 的正常、异常和边界路径
- [x] 3.5 覆盖 ReportRepository、ProjectArchiveRepository、ArchiveCandidateRepository、MigrationInputRepository、OptimizationCycleRepository 与 StoredArtifactRepository 的正常、异常和边界路径
- [x] 3.6 覆盖 ModelProfileRepository、AgentRuntimeRepository、WorkerInstanceRepository、WorkerTaskRepository、UserRepository、UserActionTokenRepository、SystemConfigRepository 及其余小型 Repository 的正常、异常和边界路径
- [x] 3.7 复查 Repository 层 SQL 条件、排序、分页、空值映射、并发状态条件、批处理与数据库异常分支，并确认 Repository package 行/分支覆盖率达到 90%

## 4. 回补任务 Handler 与运行时测试

- [x] 4.1 完整覆盖 AutomatedTestHandler 的成功、非零退出码、报告文件/目录收集、大小与深度边界、超时、取消、SSH 异常、归档和比较触发路径
- [x] 4.2 补齐 BuildValidation、DependencyAnalysis、DependencyAutoFix、KB Scan/AI、Report、Archive、Source Fetch/Deploy 与 TestComparison Handler 的未覆盖状态和异常分支
- [x] 4.3 补齐 Task worker 消费、重试分类、死信、取消、并发控制、heartbeat、清理与 dispatch repair 的正常、异常和边界路径
- [x] 4.4 对必须直接创建本地进程、SSH client 或 Agent CLI 的类先用特征测试锁定行为，再按需提取可注入执行边界并模拟返回值
- [x] 4.5 复查 Handler 与 runtime package 行/分支覆盖率并补齐至 90%

## 5. 回补 Service 与业务规则测试

- [x] 5.1 补齐 DependencyAnalysisService、MigrationInputService/SourceResolver、ProjectArchiveService/Registrar 与 ReportService 的状态、过滤、刷新、空输入和错误路径
- [x] 5.2 补齐 ModelProfileService、CodexProviderProbeService、TestComparisonService/AgentRuntime 与 StageReadinessService 的兼容性、超时、解析失败、缺失配置和边界路径
- [x] 5.3 补齐 Project、Environment、Source、BuildValidation、AutomatedTest、KB、Artifact、Auth/User/Mail 和任务日志/SSE 服务的剩余正常、异常和 edge case
- [x] 5.4 对幂等、权限、staleness、latest/readiness、报告纳入状态、敏感信息脱敏和路径安全规则增加明确断言
- [x] 5.5 复查 Service 与业务规则 package 行/分支覆盖率并补齐至 90%

## 6. 回补 Controller、DTO、配置与 Adapter 测试

- [x] 6.1 使用 standalone MockMvc 覆盖所有 Controller 的成功响应、鉴权/权限失败、参数校验、资源不存在、分页排序过滤和统一错误包络
- [x] 6.2 覆盖 Request parser、validator、response mapper、record factory、枚举转换与排序白名单的有效值、null/blank、非法值和边界值
- [x] 6.3 使用最小上下文或直接实例化覆盖配置绑定与条件 bean，不启动真实 listener、scheduler 或客户端连接
- [x] 6.4 通过模拟连接和执行结果覆盖 Redis、RabbitMQ、S3、SSH、Git、HTTP 与 Agent Adapter 的成功、超时、失败、编码和输出上限路径
- [x] 6.5 复查 Controller、DTO、Configuration 与 Adapter package 行/分支覆盖率并补齐至 90%

## 7. 缺陷处置与等价重构审查

- [x] 7.1 汇总新增测试发现的疑似业务缺陷，按“明确规格违例”或“语义待确认”分类，禁止在本 change 中顺带修复
- [x] 7.2 对明确规格违例保留最小失败复现并将对应任务标记阻塞，给出独立修复 change 建议
- [x] 7.3 对语义待确认项增加 characterization test 并登记决策问题，不将未经确认的假设写成新逻辑
- [x] 7.4 审查所有生产代码 diff，确认仅包含有特征测试保护的依赖注入、执行边界或纯函数提取，且 API 与业务语义未变化

## 8. 覆盖率门槛与最终验收

- [x] 8.1 更新 JaCoCo 自动化检查，保持仅排除生成 jOOQ 代码，并强制 BUNDLE 行/分支覆盖率均不低于 90%
- [x] 8.2 增加项目自有业务 package 的行/分支 90% 检查，确保未加载类仍进入统计且高覆盖模块不能掩盖低覆盖模块
- [x] 8.3 执行 `mvn -B clean verify`，确认测试零失败零错误、普通单元测试不依赖任何外部服务，并记录测试数量和跳过项原因
- [x] 8.4 报告最终整体及各 package 行/分支覆盖率、统计范围、合法排除项和 `target/site/jacoco/index.html` 报告位置
- [x] 8.5 检查测试中不存在空断言、仅为覆盖而调用代码、随意 `@Disabled`、真实凭据、固定本机路径或隐式网络依赖
