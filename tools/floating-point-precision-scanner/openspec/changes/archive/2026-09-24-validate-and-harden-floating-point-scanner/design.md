## Context

扫描器当前以版本化 Clang AST facts、共享 LLVM BC facts、AST↔IR evidence、profiles 和 build contexts 驱动十类规则，已经具备稳定 ID、确定性排序、双语诊断、原子结果写出以及 Python/C++ 双覆盖率门禁。现有 fixture 主要验证单条规则和协议分支，没有独立 reviewed oracle、按规则统计的检测质量、规模基线或统一的全流程预算控制。请求 schema 虽声明 wall/CPU/内存和多种逻辑预算，但部分限制只作用于 LLVM worker，部分尚未形成稳定 frontier；现有实现也没有正式的分析缓存和 suppression 过期语义。

本变更是 RvPort 集成前的 P5 质量阶段。使用者包括扫描器维护者、规则评审者、CI 和后续 RvPort 编排层。所有验证必须离线、可重复、使用锁定的 Clang/LLVM 21.1.8，并保留“未分析不等于安全”的失败语义。

## Goals / Non-Goals

**Goals:**

- 用版本化 reviewed corpus 和显式 oracle 衡量十条规则的 TP、FP、FN、abstention、exact match 与失败语义。
- 将 wall time、CPU、峰值 RSS、文件/字节、facts、evidence、规则、诊断和 suppression 预算统一为可审计的执行模型。
- 为 canonical source facts、IR facts 和 evidence 提供安全、原子、内容寻址的可选本地缓存，并证明冷、热缓存语义等价。
- 使用显式 `policy_as_of` 审核 suppression 有效期，不依赖宿主时钟。
- 固定 benchmark 环境、三档规模语料和数值门禁，并为所有新增逻辑提供正常、边界、异常和故障注入单元测试。

**Non-Goals:**

- 不新增或改变十类浮点风险规则的业务判断含义。
- 不在本阶段接入 RvPort 服务、调度、数据库或 UI。
- 不执行目标程序，不实现跨架构动态差分。
- 不缓存最终 finding、suppression 结果或完整 scan result。
- 不把 benchmark 数值推广为其他硬件上的通用 SLA。

## Decisions

### 1. 将验证作为独立、版本化的离线协议

新增 `validation-corpus@1.0`、`validation-oracle@1.0` 和 `validation-result@1.0`。每个 case 固定源码、标准、profiles、build contexts、输入模式和预期 assessment；oracle 使用 `rule_code + normalized scope + semantic evidence key + location` 描述预期，而不是只比较展示文本。固定规则版本时同时保存预期稳定 ID，以发现身份漂移。

验证入口读取已经版本控制的 corpus，不联网、不调用 AI，也不从当前实现自动生成 oracle。oracle 必须记录 reviewer、review revision、依据和 fixture digest；变更 oracle 必须经过代码评审。

选择独立验证协议而不是把真值塞入 scan result，是为了避免生产输出携带测试专用字段，也让同一 scan result 可被不同质量策略重新评分。

### 2. 明确定义指标和 abstention 计数

以 oracle 的 rule/scope 为评价单元：

- TP：预期 `matched` 且实际发布相同 semantic key 的 matched assessment/finding。
- FP：预期 `not_matched` 却发布 finding，发布 oracle 未声明的额外 finding，或在 strict 模式下对预期保守 abstain 的范围发布确定 finding。
- FN：预期 `matched` 但缺少对应 finding；实际 `unknown`、`skipped` 或 `failed` 时同时计为 FN 和 abstention。
- supported-only 指标只排除 oracle 明确标记为工具不支持或证据必然不足的 case，不能排除扫描器意外产生的 unknown/failed。
- strict precision/recall 使用全部可判定 case，并对越界 finding 和意外 abstention 处罚；零分母序列化为 `null`。
- exact match 要求 assessment 状态、semantic finding 集、suppression 集和规定的 diagnostic code 集全部一致。

每条规则至少包含 6 个正例、6 个反例、3 个预期 unknown/unsupported 以及 suppression、边界或异常 case。门禁要求每条规则的 strict precision 和 strict recall 均至少 90%，整体 exact-match rate 至少 95%，所有失败/预算/suppression 生命周期 case 必须 100% exact match。启发式规则评估“是否形成需要人工确认的合规候选”，不把业务缺陷或容差臆造为 oracle。

### 3. 使用统一 BudgetCoordinator 和可注入资源采样器

请求解析后创建单个 `BudgetCoordinator`，使用注入的 monotonic clock、CPU/RSS sampler 和稳定逻辑计数器。Clang 前端、LLVM worker、facts 映射、evidence、规则、诊断、suppression、缓存和输出在开始新工作前向 coordinator 预约，在完成后提交消耗。全局 wall deadline 不按 worker 重置；CPU 和 RSS 同时约束父进程及子进程，POSIX 使用进程组/rlimit，无法提供同等强制能力的平台必须在启动前返回可识别的 unsupported/partial 语义，而不是假装预算已生效。

候选先稳定排序再截断。预算结果只在 scan result 中记录 limit、稳定逻辑用量、受影响 scope 和最后完成 frontier；易波动的实际 wall/CPU/RSS 采样写入独立 validation/benchmark report，不进入 scan semantic digest。

选择中央 coordinator 而不是各模块独立 timeout，避免每个 TU 都重新获得完整 wall budget，也能保证不同完成顺序保留同一 frontier。

### 4. 缓存 canonical 中间产物而不是最终结论

缓存对象限定为 source facts、IR facts 和 AST↔IR evidence。缓存 key 为规范化输入摘要：对象 kind/schema/producer、源码内容和 compile-context digest、profile/build-context fingerprints、Clang/LLVM/reader/extractor 版本、artifact digest、mapping 配置及影响该层语义的预算。缓存包络包含 key、payload SHA-256、字节数和依赖摘要。

缓存采用 `<cache-root>/<kind>/<key-prefix>/<key>.json`，先在同目录临时文件完整序列化、flush/fsync，再原子替换；并发相同 key 的 writer 可以重复计算，但只能发布相同摘要。读取时先做路径边界、大小、schema、key 和 payload digest 校验。损坏、不兼容、越界或未完成临时文件视为 miss，聚合双语诊断并重新计算；若输入本身无法重新计算，则按原有分析失败语义处理。

最终 findings、assessments、suppressions 和 scan result 不缓存，因为它们依赖规则版本、policy 日期和展示/审计策略。缓存命中统计不参与 semantic digest；移除缓存目录即可完整回滚。

### 5. Suppression 过期由显式策略日期决定

scan request schema 1.4 增加可选 `policy_as_of`（ISO 8601 完整日期）和 suppression `expires_on`。带 `expires_on` 的 suppression 必须同时提供 `policy_as_of`；当 `policy_as_of > expires_on` 时 suppression 已过期，candidate 保持可见并发布审计诊断。当二者相等时仍有效。核心扫描路径禁止读取系统当前日期。

旧 schema 的 suppression 没有过期字段并保持原行为。这样既能实现生命周期治理，又不破坏相同请求的确定性。

### 6. 固定 benchmark 工作负载和门禁

benchmark 使用仓库锁定的 Linux/amd64 Docker 镜像、Clang/LLVM 21.1.8、4 vCPU、4 GiB memory、关闭网络，运行三次取中位数。规模语料由 reviewed 模板确定性展开，固定摘要：

| 档位 | 翻译单元 | 约源码行 | 冷缓存 wall | CPU | 峰值 RSS | 结果上限 |
|---|---:|---:|---:|---:|---:|---:|
| S | 20 | 10,000 | 60 s | 180 s | 1.5 GiB | 16 MiB |
| M | 100 | 50,000 | 240 s | 720 s | 2.5 GiB | 64 MiB |
| L | 500 | 250,000 | 900 s | 2,700 s | 3.5 GiB | 256 MiB |

热缓存 wall 中位数必须不超过相同档位冷缓存的 60%，且扫描语义文档逐字节等价（允许独立 benchmark telemetry 不同）。与同一镜像和语料保存的已接受基线相比，wall、CPU 或 RSS 回退超过 20% 即失败；绝对上限与相对门禁同时适用。若宿主不能提供 4 vCPU/4 GiB 隔离，报告为环境不适用，不能标记性能验收通过。

### 7. 故障注入通过适配器完成

为 clock、resource sampler、process runner、cache store、serializer、fsync 和 replace 提供可注入接口。单元测试精确触发 timeout、CPU/RSS 超限、worker kill、输出截断、损坏缓存、摘要冲突、诊断上限、fsync/replace 失败；生产路径不提供随机故障开关。诊断上限预留一个终止槽，确保 `budget_exceeded` 本身不会被上限静默删除。

## Risks / Trade-offs

- [固定语料可能被过度拟合] → oracle 以语义类别和 hard negative 组织，修改规则或 oracle 必须说明理由，并在后续阶段引入独立真实工程样本。
- [性能门禁受宿主抖动影响] → 使用固定容器资源、三次中位数、绝对与 20% 相对门禁；环境不满足时明确不适用而非伪通过。
- [缓存键漏掉语义输入导致陈旧结果] → 每类缓存对象维护显式 key schema 和依赖摘要，未知字段/版本直接 miss；最终 finding 永不缓存。
- [全流程资源限制在 Windows 与 POSIX 能力不同] → 锁定的验收环境为 Linux/amd64；其他平台必须公开 enforcement capability，不能声称强制了无法实现的限制。
- [strict 指标把保守 unknown 计为漏检会降低分数] → 同时发布 supported-only 和 abstention 指标，但 strict 门禁继续处罚可判定正例上的意外 abstention，防止通过全部返回 unknown 获得虚假安全。
- [suppression 过期字段造成协议演进] → 只在 schema 1.4 启用，旧 schema 保持原有无过期语义，并提供清晰迁移文档。

## Migration Plan

1. 增加 schema 1.4、validation/cache schema 和兼容解析；旧 schema 1.0–1.3 保持原默认规则与 suppression 行为。
2. 引入 BudgetCoordinator 并逐层接入，先使用现有默认值保持行为，再启用统一门禁和稳定 frontier。
3. 实现可关闭的缓存，默认在验证环境显式指定 cache root；验证冷缓存与热缓存语义等价后再决定后续集成默认值。
4. 提交 reviewed corpus、oracle、基准摘要和接受基线，运行质量、故障、覆盖率及性能门禁。
5. 回滚时可禁用缓存、继续使用旧 schema 请求；缓存目录为派生数据，可直接丢弃，不影响源码或共享 BC。

## Open Questions

- 本变更没有阻塞实施的开放问题。未来若要在 RvPort 中改变缓存位置、共享策略或性能 SLA，必须在 P6 集成 change 中按部署环境重新设计，不修改本阶段固定验收基线。
