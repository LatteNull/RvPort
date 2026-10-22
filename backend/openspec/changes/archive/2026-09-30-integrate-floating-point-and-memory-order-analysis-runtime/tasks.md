## 1. 数据模型与领域常量

- [x] 1.1 增加专项分析运行表和逐条 Finding 表的 Liquibase 迁移，包含主外键、唯一约束、分页过滤排序索引以及可空环境配置版本关联
- [x] 1.2 运行 Liquibase 与 jOOQ 代码生成，确认迁移只由 changelog 创建表和索引，不手工预建数据库对象
- [x] 1.3 增加 analyzer type、运行状态、verdict、两个 task type、两个 stageId 和 `FLOATING_POINT_FINDING`/`MEMORY_ORDER_FINDING` source type
- [x] 1.4 实现运行与 Finding repository，支持事务导入、latest、活动运行优先、当前源码版本、历史查询、分页、过滤、白名单排序和 included-in-report 投影

## 2. Worker 镜像与工具健康检查

- [x] 2.1 更新 backend-worker 多阶段 Docker 构建，固定安装浮点扫描 Python 包、memory-order Python 模块和 LLVM/Clang 21 运行库
- [x] 2.2 构建并复制 `fp-ir-worker`、`moa-worker` 与 `memory-order-source-worker`，确保运行镜像不包含不必要的编译缓存和开发输出
- [x] 2.3 增加两类分析器的可执行路径、workspace、cache、超时、输出/解压预算和 enable 配置，并同步 `.env`/compose 示例
- [x] 2.4 实现 Worker 启动期版本与 doctor 检查，向 readiness 提供 AVAILABLE/UNAVAILABLE、工具版本和安全原因码
- [x] 2.5 验证镜像在无网络、无 Docker socket、无宿主工具源码挂载时可以执行两个工具的 version/doctor 和最小 fixture

## 3. 共享输入解析与安全物化

- [x] 3.1 实现专项分析 artifact resolver，只根据项目、当前源码版本和成功 x86 构建解析源码、compile database 与 Shared LLVM BC v2 制品
- [x] 3.2 实现任务私有 materializer，流式下载并校验大小、SHA-256、源码身份、compile context、manifest counts 和 produced/missing/failed 分母
- [x] 3.3 对解压路径、链接、设备文件、重复条目、未声明文件、文件数量和总体积执行安全校验，并保证失败/取消后清理临时目录
- [x] 3.4 实现浮点 artifact-set adapter，固定 manifest digest、profile/capability 和同源码 compile database 映射
- [x] 3.5 实现 Shared LLVM BC v2 到 memory-order external bundle/record/scope 的确定性 adapter，并验证平台 artifact key 未进入工具内部 ArtifactKey 字段
- [x] 3.6 用两类工具提供的 schema/fixture 建立 adapter 契约测试，覆盖 READY、PARTIAL、开放/闭合 Scope、失败记录和身份不一致

## 4. 公共专项分析执行内核

- [x] 4.1 实现公共分析 workspace、请求原子写入、受控 ProcessBuilder、UTF-8 merged/stdout/stderr 日志、超时和进程树终止
- [x] 4.2 将 memory-order cancel file 与现有任务取消机制连接，在宽限期后强制终止且不导入未原子发布结果
- [x] 4.3 实现 request/result/output tree 的 schema、路径、大小、引用和 digest 校验，拒绝绝对路径及协议版本漂移
- [x] 4.4 实现对象存储上传与安全制品元数据，保存 request、原始 JSON、HTML 和 memory-order 审计 bundle
- [x] 4.5 保证结果导入、运行终态和迁移输入刷新使用事务边界，失败时不暴露半导入 Finding

## 5. 浮点精度分析运行时

- [x] 5.1 实现浮点分析创建服务和 readiness 校验，锁定当前源码、x86 构建、BC artifact set、compile database、环境配置版本及 source/target profile
- [x] 5.2 实现浮点 request builder，默认启用当前 schema 的全部稳定规则并配置 build context、共享 BC、预算和 cache
- [x] 5.3 实现 `validate-request` 与 `scan` Handler，按 0/4/2/3/5 退出码及结果状态映射任务和分析状态
- [x] 5.4 实现 result schema v2 导入，将公共摘要与每条 Finding 的双语内容、位置、occurrences、evidenceChain、validationPlan 和 semantic digest 落库
- [x] 5.5 生成与 JSON 同口径的轻量浮点 HTML，并保存 diagnostics、assessments、层级分母、profile 和 build-context 摘要

## 6. 强弱内存序分析运行时

- [x] 6.1 实现内存序分析创建服务和 readiness 校验，锁定当前源码、x86 构建、compile database 与 BC artifact set
- [x] 6.2 实现 `UnifiedMemoryOrderAnalysisRequest v1` builder，固定 policy/preset、scope all、source assistance auto、预算、cache/resume 和 cancel file
- [x] 6.3 实现只调用 `analyze-project` 的 Handler，并按 exit 0/3/2/1 以及 report status/verdict 一致性映射终态
- [x] 6.4 导入 Finding schema 2.0 的 formal findings 与 source candidates，保存双语结论、位置、occurrences、evidenceChain、breaks、assumptions、limitations 和 semantic digest
- [x] 6.5 保存 discharged assessments、unsupported、frontier、diagnostics、scope execution 和 data 审计目录，并生成轻量内存序 HTML
- [x] 6.6 验证 exit 3 发布成功事件且不触发 RabbitMQ 重试，exit 2 的 partial 结果可查询且不被描述为全程序安全

## 7. API、工作流状态与事件

- [x] 7.1 为两个领域分别实现创建、latest、运行列表、运行详情、Finding 列表、Finding 详情和 JSON/HTML 下载 Controller/DTO
- [x] 7.2 实现运行和 Finding 的分页、过滤、关键字与白名单排序，覆盖非法参数、空页、稳定 tie-breaker 和大页限制
- [x] 7.3 在所有创建、查询、确认和下载接口接入项目权限校验，确保跨项目请求不泄漏资源存在性
- [x] 7.4 将两个 stage 接入项目 readiness、overview、领域 latest、currentSourceRevision、staleReasons 和活动任务优先语义
- [x] 7.5 将任务创建、排队、开始、进度、日志、成功/失败/取消及 project.context.changed 接入 Redis 跨进程 SSE
- [x] 7.6 在任务 metadata/resource resolver、运行中任务冲突规则、取消和 Worker 可观测性中登记两个新任务类型

## 8. 迁移输入、报告与归档闭环

- [x] 8.1 为两类 Finding 创建 migration input reference，按全局风险政策设置默认状态并在列表/详情返回确认与报告纳入字段
- [x] 8.2 实现同项目、源码版本、source type 的成功重跑刷新，确保失败/取消不清空旧输入且不继承旧人工排除状态
- [x] 8.3 扩展评估报告输入解析和聚合，将浮点/内存序 Finding 纳入模块、文件、问题类型、行号、风险、主要问题和工作量统计
- [x] 8.4 在报告 JSON/HTML 中展示浮点影响/测试建议/validation plan，以及内存序风险/候选、同步缺口、证据限制和人工确认提示
- [x] 8.5 为两类分析登记当前源码版本的可插拔归档候选，保存安全轻量摘要、JSON、HTML 和受控 memory-order 审计 bundle
- [x] 8.6 验证源码更新、浮点相关环境配置更新和同类重跑的 staleness/刷新边界，同时保持历史运行和 report_inputs 快照不变

## 9. 单元测试与覆盖率

- [x] 9.1 为数据库、resolver、materializer、adapter、request builder、result importer、状态映射、API、迁移输入、报告和归档补充正常流程单元测试
- [x] 9.2 补充异常流程测试：权限拒绝、对象存储错误、外部进程失败、schema 不匹配、哈希错误、路径逃逸、超时、取消、退出码/报告冲突和事务回滚
- [x] 9.3 补充 edge case：空 Finding、无位置 Finding、重复 ID、PARTIAL BC、开放 Scope、source candidate、超预算、分页边界、稳定排序和历史失效
- [x] 9.4 所有单元测试 mock JDBC/jOOQ、对象存储和进程/文件服务返回值，不连接 PostgreSQL、Redis、RabbitMQ、MinIO、SSH 或网络服务
- [x] 9.5 运行完整单元测试和 JaCoCo 覆盖率，确保项目整体与本次受影响模块行覆盖率及可用分支覆盖率均至少 90%，并保存报告位置和统计范围

## 10. 真实 API E2E 与交付验证

- [x] 10.1 增加可分模块运行的 floating-point-analysis E2E，使用真实源码、真实 x86 构建、真实 compile database、Shared BC v2 和容器内工具验证完整流程
- [x] 10.2 增加可分模块运行的 memory-order-analysis E2E，使用真实 risk、no-finding、partial 和 failed fixture 验证 exit 0/2/3/1、证据链和任务状态
- [x] 10.3 验证两类 API 的权限、latest/readiness/overview、分页过滤排序、Finding 详情、节点确认、报告、JSON/HTML 下载、归档和 SSE
- [x] 10.4 验证 E2E 成功或失败后只清理本次数据库、对象存储、cache namespace 和 runtime 临时数据，不残留测试数据且不删除既有数据
- [x] 10.5 重新构建 backend 与 backend-worker 镜像，在 compose 环境运行完整 E2E、单元测试和覆盖率门禁，并记录工具版本、命令、结果及制品位置
