## Context

`demo-test1` 的最新浮点分析包含 3 个 C++ 翻译单元。共享 BC 的 3 个成员均可由 IR worker 正常解析，但 Clang 21 对这些翻译单元执行 `-ast-dump=json` 后分别产生约 94 MiB、138 MiB 和 230 MiB 输出。当前 `SubprocessRunner` 使用 `capture_output=True` 收集完整 stdout，再按默认 16 MiB 截断字符串并调用 `json.loads()`，所以所有翻译单元均被错误归类为 `frontend_invalid_json`。由于没有生成 source facts，证据关联阶段继续产生 3 个 `source_fact_bundle_missing`，后端又固定读取 `diagnostics[0]`，最终只展示了派生错误。

将请求中的 `max_frontend_output_bytes` 临时提高到 300 MiB 后，AST 和 IR 均能完成，但结果生成把大量标准库 source facts 聚合进单条 Finding 的 `fact.provenance` 和 occurrence provenance，超过 Schema 的 `maxItems: 128`，扫描转为 `internal_error/schema_validation_error`。这说明修复必须同时覆盖 AST 传输边界、项目源码事实边界、provenance 生成和后端失败可观测性。

## Goals / Non-Goals

**Goals:**

- 在明确的文件大小、时间和资源预算内可靠处理常见 C++ 翻译单元产生的大型 Clang AST JSON。
- 明确区分 AST 输出超限、进程失败、输出截断和真正的 JSON 损坏。
- 仅将项目源码以及结论直接依赖的 facts 纳入 Finding provenance，确保结果稳定、可审计且满足 v2 Schema。
- 在分析失败时保留安全的原始结果 JSON，并向任务和运行记录暴露最接近根因的诊断。
- 对不可重试的输入、协议、Schema 和资源预算错误停止自动重试。
- 使用不依赖真实 Clang 进程、数据库、对象存储或消息队列的单元测试覆盖正常、异常和边界路径，并满足 90% 覆盖率门禁。

**Non-Goals:**

- 不修改 `SharedLlvmBitcodeArtifactSet@2.0` 的生产协议、BC 内容或构建成功语义。
- 不改变浮点分析 API 路径、Finding 业务确认流程或迁移报告纳入策略。
- 不把系统头文件中的实现细节作为迁移风险 Finding 展示给用户。
- 不以无限提高内存、stdout 或结果大小限制代替有界处理。

## Decisions

### 1. Clang AST 使用任务级临时文件承接，并在写入阶段执行硬预算

Clang stdout SHALL 直接写入任务私有临时文件，stderr 继续使用有界缓冲。父进程在执行期间监控文件大小；超过 `max_frontend_output_bytes` 时终止子进程并返回 `frontend_output_limit_exceeded`，成功退出后再从文件解析 JSON。临时文件在单个翻译单元处理结束以及任务成功、失败、取消或超时时清理。

后端 request adapter SHALL 显式写入 `max_frontend_output_bytes`，默认值必须能够覆盖已验证的真实 C++ 用例，同时继续受 worker 配置硬上限约束。扫描器不得把超预算输出截成前缀继续解析。

选择文件承接而不是继续扩大 `capture_output`，是为了避免 Clang 输出、Python 字符串副本和 JSON 解析对象同时常驻内存。首轮实现仍可使用标准 JSON 文件解析，但必须保留替换为增量解析器的边界，并通过大 AST fixture 验证峰值资源不会突破 worker 限制。

### 2. 输出状态必须先依据进程与截断信息分类，再执行 JSON 解析

Frontend 处理顺序固定为：进程启动/版本校验、超时或取消、退出码、输出预算、完整 JSON 解析、顶层结构校验。只有完整输出确实不能解析时才返回 `frontend_invalid_json`。诊断必须包含稳定 code、翻译单元 ID、是否可重试和脱敏建议，不包含绝对路径或原始命令。

### 3. source fact 的业务边界是项目源码，不是整个编译器 AST

fact mapper SHALL 根据规范化 location 判断节点是否来自 `project_root` 内的源码或项目头文件。系统头文件、标准库头文件和 project root 外部文件的声明不得作为独立 source facts 或对象目录项写入结果；它们只可作为某个项目源码事实不可缺少的类型/调用描述，并以有界、脱敏的外部符号信息表达。

该过滤在 fact 建模入口执行，而不是在最终 Finding 序列化后清理，以防无关事实进入规则评估、缓存键、evidence 和 provenance。无法确定位置的节点默认不作为项目源码事实，除非规则显式证明它由项目节点引用并使用受控的 external 标记。

### 4. Finding provenance 只引用直接证据并遵守 Schema 上限

Finding fact、每个 occurrence 和 evidence chain SHALL 从规则 assessment 的直接 evidence 构建各自的去重引用集合，不得把整个翻译单元或整个 source fact bundle 注入每条 Finding。引用按稳定键排序，重复引用只保留一次。

若单个结论的合法直接证据仍超过协议上限，生成器 SHALL 使用确定性的聚合或分组表达，并记录 `provenance_budget_exceeded`/partial frontier；不得静默截断后声称证据链完整，也不得发布不符合 Schema 的结果。结果在原子发布前必须经过与随包 Schema 相同的验证器。

### 5. 后端保存失败结果并按因果优先级选取公开诊断

只要扫描器原子发布了大小合规且可解析为 JSON 对象的结果，后端 SHALL 在判断退出码/状态组合之前完成结构化路径脱敏并保存原始结果制品。运行失败时 `result_json_artifact_id` 仍可关联该不可变制品，便于审计完整 diagnostics。

任务错误与运行摘要不再固定读取数组第一项，而按阶段因果优先级选择：frontend/input/budget/resource → IR/source → evidence → result validation → 派生缺失。响应同时保留主诊断 code、message 和总诊断数量；完整列表由结果制品承载。

### 6. 重试由稳定错误分类决定

`frontend_output_limit_exceeded`、`frontend_invalid_json`、`source_fact_bundle_missing`、Schema 校验失败、请求无效和不支持的协议属于不可重试错误。超时、临时进程启动失败等只有在诊断显式 `retryable=true` 时才进入既有重试策略。后端通过专用异常或任务失败分类把该属性传递给 worker，避免相同输入连续执行三次。

### 7. 测试使用合成进程结果和固定 fixture

工具侧使用注入的 `ProcessRunner`/临时文件 writer 模拟小 AST、大于 16 MiB 的合法 AST、超过硬上限、非零退出、超时、取消、损坏 JSON和系统头文件密集 AST。结果侧使用超过 128 个候选事实的 fixture 验证直接证据收敛、确定性、Schema 合法性及 partial frontier。

后端使用 mock 的进程、对象存储、repository 和任务上下文返回值验证失败制品保存、根因诊断优先级、路径脱敏和可重试分类；测试不得连接真实 PostgreSQL、MinIO、RabbitMQ、Redis、SSH 或 Clang。

## Risks / Trade-offs

- [大型 AST 临时文件增加磁盘 I/O 和空间压力] → 使用任务级目录、每 TU 硬上限、执行期大小监控和 finally 清理，并测试取消与异常清理。
- [标准库过滤过度可能丢失必要语义] → 保留由项目事实直接引用的有界 external symbol/type 摘要，但不生成独立系统头文件 Finding。
- [提高默认 AST 预算可能增加单任务资源占用] → 配置默认值与 worker 硬上限分离，保持并发下的总资源预算，并在超限时明确失败而非交换或 OOM。
- [失败结果可能包含服务器路径] → 保存前执行结构化字段脱敏和安全校验；无法安全处理时只保存最小诊断摘要，不上传原文。
- [provenance 聚合影响现有稳定 ID] → Finding 业务 ID继续基于规则和语义位置计算；聚合仅改变证据表达，并用确定性排序与回归 fixture 固定结果。

## Migration Plan

1. 先更新扫描器 frontend、facts/result 生成及其单元测试和 Schema fixture。
2. 更新后端 request adapter、失败结果持久化、诊断优先级和任务重试分类。
3. 构建 worker 镜像，在不依赖外部服务的测试中通过 90% 覆盖率门禁。
4. 使用 `demo-test1` 当前源码、compile database 和共享 BC 制品执行真实回归，确认不再出现 AST 截断或 provenance Schema 错误，并保存完整 JSON/HTML。
5. 若新实现异常，可回滚镜像；数据库新增字段或约束如非必要不引入，已有可空结果制品关联保持向后兼容。

## Open Questions

- 无。默认采用任务临时文件承接完整 AST、项目根过滤 facts、直接证据 provenance 和失败结果制品留存方案。
