## 1. 协议与兼容演进

- [x] 1.1 新增 scan request/result schema 1.4，定义 `policy_as_of`、suppression `expires_on`、cache 配置、预算 limits/稳定用量/frontier 和 cache 统计，并保持 schema 1.0–1.3 的解析、默认规则与无过期 suppression 行为。
- [x] 1.2 新增 cache envelope、validation corpus、oracle 和 `FloatingPointScannerValidationResult@1.0` JSON Schema，注册独立 kind/version 并为全部跨文档 digest/ref 增加严格校验。
- [x] 1.3 更新版本输出、示例和协议不变量，确保 wall/CPU/RSS telemetry、绝对 cache root、系统日期与 benchmark 字段不进入生产 scan semantic digest。
- [x] 1.4 为 1.4 正常输入、未知字段、不兼容版本、旧版本回归、跨文档摘要冲突和双语字段完整性补充 contract/unit tests。

## 2. 统一预算协调与资源强制

- [x] 2.1 实现可注入 monotonic clock、CPU/RSS sampler 和稳定逻辑计数器的 `BudgetCoordinator`，定义共享 deadline、预约/提交、超限分类和稳定 frontier 数据模型。
- [x] 2.2 将 Clang verify/AST 进程接入请求 wall、CPU、内存和输出预算，使用剩余共享 deadline，隔离超限子进程并保留对应 TU 分母和双语诊断。
- [x] 2.3 将 LLVM worker、source facts、IR facts、evidence 构造接入同一 coordinator，统一 artifact/BC 字节、文件数、worker 输出、facts、use-chain 和 candidate 预算。
- [x] 2.4 补齐 `max_rule_candidates`、`max_rule_assessments`、evidence refs、related locations、diagnostics 和 suppression records 的实际执行，所有截断先稳定排序并记录未分析范围。
- [x] 2.5 实现结果大小预算和诊断终止槽；超限时保留既有正式结果并产生可解析的最小失败信息，不写出截断 JSON。
- [x] 2.6 为共享 deadline、CPU/RSS、每类逻辑预算、平台不支持资源强制、结果过大和不同调度顺序补充正常、边界、异常及稳定 frontier 单元测试。

## 3. Canonical 中间产物缓存

- [x] 3.1 实现 source facts、LLVM IR facts 和 AST↔IR evidence 的 cache key builder，纳入 kind/schema/producer、源码/compile-context、profiles/build contexts、Clang/LLVM、artifact/mapping digest 及影响语义的预算。
- [x] 3.2 实现 cache envelope 校验和 `off|read-only|write-only|read-write` 模式，限制 cache root、拒绝路径穿越/软链接逃逸，并对大小、schema、key、payload SHA-256 和依赖摘要执行校验。
- [x] 3.3 实现同目录临时文件、flush/fsync、原子替换和并发同 key 发布；缓存损坏、不兼容、越界或冲突时聚合双语诊断并安全降级为重新计算。
- [x] 3.4 在应用编排中逐层接入缓存，确保最终 finding/assessment/suppression/result 始终重算，cache hit/miss/corrupt/write 统计与 semantic digest 分离。
- [x] 3.5 为命中、未命中、关闭、只读/只写、输入变化、版本变化、损坏、摘要冲突、路径逃逸、并发写、fsync/replace 失败和底层输入同时缺失补充单元测试。

## 4. Suppression 生命周期与审计

- [x] 4.1 扩展 suppression 模型和解析器，支持 ISO 日期 `expires_on` 与请求 `policy_as_of`，禁止在核心扫描路径读取系统当前日期。
- [x] 4.2 实现有效、到期、未匹配和预算未记录的稳定审计状态；到期 suppression 保持 finding 可见、输出双语理由且不增加 `summary.suppressed`。
- [x] 4.3 为日期相等、已过期、缺少 policy 日期、非法日期、旧 schema、request/source suppression、宏/模板歧义和审计预算补充单元及 contract tests。

## 5. Reviewed corpus 与质量指标

- [x] 5.1 建立 versioned corpus/oracle 目录和维护说明，固定 case/fixture/oracle digest、reviewer、review revision、规则/范围、预期 assessment、semantic finding key、suppression 和 diagnostic code。
- [x] 5.2 为十条规则分别补齐至少 6 个正例、6 个反例、3 个预期 unknown/unsupported 及 suppression、边界或异常 case，覆盖 C11/C17/C++17/C++20、x86/RISC-V、AST-only、共享 BC 和 AST↔IR evidence。
- [x] 5.3 实现验证运行器和 TP/FP/FN、strict/supported-only precision/recall、exact match、abstention/unknown 计算，零分母输出 `null`，可判定正例的 unknown/skipped/failed 同时计入 FN 和 abstention。
- [x] 5.4 实现逐 finding code 与总体门禁：每条规则 strict precision/recall 至少 90%、整体 exact match 至少 95%、失败/预算/缓存/suppression 生命周期 case 100% exact match。
- [x] 5.5 实现稳定排序的 `validation-result@1.0` 报告，引用 corpus/oracle/tool/schema/profile/container digests，并为指标边界、额外 finding、重复/遗漏 case、oracle 不完整和不同工作区补充单元测试。

## 6. 固定规模 Benchmark

- [x] 6.1 固定 Linux/amd64、Clang/LLVM 21.1.8、4 vCPU、4 GiB、禁网 benchmark 环境描述和 S=20 TU/约 10k 行、M=100 TU/约 50k 行、L=500 TU/约 250k 行的确定性语料摘要。
- [x] 6.2 实现三次运行取中位数的 wall/CPU/峰值 RSS/结果大小采集，并执行 S/M/L 冷缓存绝对上限 60/240/900 秒、180/720/2700 CPU 秒、1.5/2.5/3.5 GiB、16/64/256 MiB 门禁。
- [x] 6.3 实现热缓存 wall 不超过对应冷缓存 60%、wall/CPU/RSS 相对接受基线回退不超过 20% 的门禁，并将 telemetry 保存在独立验证报告中。
- [x] 6.4 验证冷/热缓存和不同绝对工作区的 scan 语义输出逐字节等价；环境资源不满足时标记不适用并保持性能验收未完成。
- [x] 6.5 为 benchmark 配置、median、绝对/相对阈值、零/缺失采样、环境不适用和语义不等价补充可离线执行的单元测试。

## 7. 故障注入与安全恢复

- [x] 7.1 为 clock、resource sampler、process runner、cache store、serializer、fsync 和 replace 提供仅代码注入的测试适配点，确认生产 request/schema 不暴露故障注入字段。
- [x] 7.2 增加 timeout、OOM/RSS、worker kill、输出截断、缓存损坏、诊断洪泛、原子缓存写失败和原子结果写失败测试，断言 status、退出码、分母、frontier、旧文件保留及临时文件处置。
- [x] 7.3 加固诊断聚合与脱敏，确保预算终止槽、根因计数和代表范围完整，且堆栈、源码、凭据、环境变量值、项目/cache/artifact 根外绝对路径不进入默认输出。
- [x] 7.4 验证所有预算、缓存和注入故障均不会生成由未完成分析推导出的 finding 或 `not_matched`，没有可用结果时稳定返回 failed/internal_error。

## 8. 自动化、覆盖率与交付文档

- [x] 8.1 更新 Makefile/容器验证入口，提供 unit、contract、validation corpus、benchmark、Python coverage、C++ coverage、lint、typecheck 和完整 verify 的可重复命令。
- [x] 8.2 为全部新增或修改的项目自有 Python/C++ 逻辑补齐正常、边界和异常单元测试；coverage source 显式纳入未加载源码，不用集成/benchmark 测试替代单元测试。
- [x] 8.3 实际运行 Python 与 C++ 单元测试和覆盖率门禁，确认项目整体及本次受影响模块的行覆盖率、分支覆盖率均至少 90%，列出第三方/生成文件排除项及理由。
- [x] 8.4 实际运行 reviewed corpus 和固定 benchmark 门禁，保存逐规则质量、三档资源、冷/热等价、相对基线及环境适用性报告；任一未达标时保持任务未完成。
- [x] 8.5 更新 README、schema/cache/corpus/benchmark 维护文档和中文验证报告，记录完整命令、测试数量、统计范围、报告位置、兼容迁移、已知限制和回滚方式。
- [x] 8.6 运行格式、lint、mypy、全部 unit/contract、严格 schema 校验、`openspec validate validate-and-harden-floating-point-scanner --strict --no-interactive` 与 `git diff --check`，修复全部失败后才进入同步归档阶段。
