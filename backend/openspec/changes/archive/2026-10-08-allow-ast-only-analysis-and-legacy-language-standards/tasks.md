## 1. 共享协议与数据模型

- [x] 1.1 版本化扩展 Shared LLVM BC manifest schema、Java model 与 validator，增加真实基础标准、方言、标准来源和原始标准参数，并保留 failed/missing/unsupported record 的 AST 关联身份。
- [x] 1.2 修改远端 BC producer 的语言标准解析，支持 C89/C90、C99、C11、C17/C18、C++98/C++03、C++11、C++14、C++17、C++20 及常见 GNU 别名；无 `-std` 时记录 `compiler-default`，禁止静默升级标准。
- [x] 1.3 增加 Liquibase 变更，使专项分析运行允许空 `artifact_set_id`，并持久化 analysis mode、BC 状态、计划/可用/失败计数和降级原因；按仓库约束重新生成并同步 jOOQ 元数据，不手工创建已由 Liquibase 管理的数据库结构。
- [x] 1.4 为既有专项分析记录实现兼容投影：不重写历史制品，根据 artifact set、运行摘要和缺失字段返回 legacy/unknown 证据模式。

## 2. 后端 BC 能力解析与任务创建

- [x] 2.1 实现独立 BC capability resolver，以当前源码、构建和 compile database 为输入，将制品分类为 `AST_BC_COMPLETE`、`AST_BC_MIXED` 或 `AST_ONLY`，并返回稳定 BC 状态、覆盖分母和降级原因。
- [x] 2.2 修改专项分析创建校验，只将当前源码、成功 source/x86 构建、真实 compile database 和工具健康状态作为硬前置；BC 缺失、失败、零 produced 或校验失败时安全降级而不拒绝任务。
- [x] 2.3 修改任务输入和运行记录，使 manifest、bundle、artifact-set ID 作为同进同出的可选组合，并在 Worker 再次校验后固定实际分析模式。
- [x] 2.4 重构 runtime materializer，始终先独立物化完整 compile database；仅在 BC 可用时下载、校验和解包制品，损坏或身份不匹配的 BC 不得进入分析器。
- [x] 2.5 修改编译数据库本地化逻辑，以全部合法 C/C++ compile entry 建立 AST 分母，并按源码路径、physical TU ID、context ID、compile record digest 和源码摘要关联可选 BC，不再用 produced record 列表裁剪源码输入。

## 3. 浮点精度扫描集成

- [x] 3.1 修改浮点请求 adapter：`AST_ONLY` 省略 `bitcode_artifact_set`，`AST_BC_MIXED` 和 `AST_BC_COMPLETE` 仅引用校验成功的 BC 成员并保留完整失败分母。
- [x] 3.2 扩展浮点扫描器的生产协议投影和编译上下文验证，保留旧标准及 GNU/ISO 方言，并验证锁定 Clang 可按真实 `-std` 参数生成 AST facts。
- [x] 3.3 修正混合模式聚合，使无 BC 的翻译单元仍运行全部适用 AST 规则，并使结果层级、diagnostics 和 evidence chain 准确区分 AST-only 与 AST+BC。
- [x] 3.4 为 C89/C90、C99、C++98/C++03、GNU 方言、无显式标准和单 TU 不支持场景增加固定 fixture、oracle 与双语诊断。

## 4. 强弱内存序分析集成

- [x] 4.1 在 memory-order-analyzer 中建立复用的语言标准/方言 value object 与 validator，替换生产路径中散落的四标准白名单和 C17/C++17 静默回退。
- [x] 4.2 版本化扩展 source profile、external bitcode、source evidence、统一分析及相关生产 schema，使旧标准可以进入 source assistance，同时保留既有协议的明确版本边界。
- [x] 4.3 修改后端 memory adapter，为每个可重放的 compile entry 生成 SourceSemanticRequest；无 BC 时创建 AST-only record，部分 BC 时按 TU 创建 `ast-only`/`ast-ir` 混合输入。
- [x] 4.4 调整内存序规则适用性：旧标准下继续识别 pthread、GNU atomic builtin 和普通共享访问候选；依赖 C11/C++11 及以后能力的规则返回不适用或 unknown，不阻断项目。
- [x] 4.5 确保 AST-only 结果只进入 source candidates、frontier 或 unknown，禁止提升为已证明 runtime risk 或无风险结论，并保留双语 evidence break。

## 5. Readiness 与查询 API

- [x] 5.1 修改专项分析 readiness，返回硬前置事实、建议 analysis mode、BC 状态、计划/可用/失败/AST-only TU 计数和稳定降级原因，BC 不可用时不得将整个阶段标记为不可执行。
- [x] 5.2 修改创建、列表、详情和 latest 响应，返回实际 `analysisMode`、可空 `artifactSetId`、BC 覆盖和降级信息，并在创建时重新计算而不信任前端传值。
- [x] 5.3 在运行摘要和 Finding/诊断投影中保留语言、基础标准、方言、标准来源及双语 unsupported/unknown 信息，禁止把旧标准显示成 C17 或 C++17。
- [x] 5.4 更新 OpenAPI/接口文档和示例，分别展示完整 BC、部分 BC、无 BC、旧标准以及单 TU 不支持的响应。

## 6. 单元测试与覆盖率门禁

- [x] 6.1 为后端 capability resolver、创建校验、可选制品 materializer、数据库兼容投影、readiness 和 DTO 补充正常流程、异常流程及边界条件单元测试；mock repository、对象存储、进程、任务和 connection 返回值，不连接任何外部服务。
- [x] 6.2 为浮点扫描器补充完整 BC、部分 BC、零 BC、损坏 BC、旧标准、GNU 方言、compiler default、混合 TU 和单 TU 隔离的离线单元测试，并对模式、分母、诊断和结果 schema 做有效断言。
- [x] 6.3 为 memory-order-analyzer 补充协议、标准规范化、AST-only、AST/IR 混合、旧标准规则适用性、候选降级和未知标准隔离测试；Python 与 C++ 测试均不得依赖网络或外部服务。
- [x] 6.4 将后端、浮点扫描器和内存序分析器中未被测试加载的项目自有生产源码按 0 命中纳入覆盖率统计；测试代码、fixture、第三方依赖和生成代码不进入覆盖率分母。执行项目整体与受影响模块门禁，行覆盖率和工具可用的分支覆盖率均达到至少 90%，并保存可审计报告。

## 7. 协议与真实流程验证

- [x] 7.1 执行 OpenSpec 严格校验、共享 manifest/request/result schema 示例校验及旧协议兼容测试，确认新消费者明确识别版本且旧消费者不会误读新字段。
- [x] 7.2 使用固定 C89、C99、C++98/C++03 和现有标准工程分别验证 BC COMPLETE、PARTIAL 与 FAILED/MISSING 三条流程，确认所有合法 TU 均进入 AST 分母且结果标准未被篡改。
- [x] 7.3 通过真实 API 验证浮点和内存序分析的 `AST_BC_COMPLETE`、`AST_BC_MIXED`、`AST_ONLY` 创建、运行、latest、详情、Finding 与制品下载，并核对任务日志和数据库状态一致。
- [x] 7.4 记录实际测试命令、测试数量、失败/跳过项、行/分支覆盖率、统计范围、排除理由、报告位置和 E2E 结果；任何测试失败或覆盖率未达 90% 时不得完成质量验收或提示归档。
