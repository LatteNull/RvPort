## 1. 固定性能基线与测试范围

- [x] 1.1 核验 libarchive commit、完整快照、默认参数及 810 个输入（802 C/C++、8 构建输入），生成项目相对路径/内容 SHA-256 manifest 和 PROVENANCE.json；只提交清单与必要缩减/合成 fixture，不提交完整第三方源码或临时报告。
- [x] 1.2 将已有 300.04 秒超时、四次 normalizer 栈采样、资源上限和扫描器基线版本固化到性能文档，明确 9 文件预览不代表全项目；核验缺失事实，不编造峰值内存或旧全量 finding baseline。
- [x] 1.3 建立 large-project-performance unit inventory，映射 normalizer 和计划新增性能支撑模块的 fake/mock 边界、对应单元文件及每模块 90% line / 80% branch 门禁。
- [x] 1.4 添加宏密集合成 snapshot 和优化前小规模语义基线，包含多 producer/context、空集合、非法引用、派生 Evidence、乱序及连续不同项目；加入能在当前实现失败的重复遍历计数断言。

## 2. 建立独立容器性能验收入口

- [x] 2.1 实现测试侧阶段 decorator，复用正式 PipelineProfile 并记录开始/结束、状态、数量和时间；对返回对象/异常透传、失败阶段和 fake clock/writer 分别补隔离单元测试。
- [x] 2.2 实现 provenance/输入清单校验与测试资源记录；用 fake 文件系统/resource 覆盖摘要不符、缺失/新增输入、运行时与知识版本缺失以及资源值 unavailable，禁止自动下载或静默跳过。
- [x] 2.3 实现父进程 300 秒 timeout、进程回收、退出分类与独立性能工件，复用既有子进程支撑的可用部分；以 fake process 测试 timeout/native signal/普通失败/OOM证据不足、旧报告和半套 artifact 不能通过。
- [x] 2.4 增加显式 tests/run_performance_tests.py 和最小独立容器启动入口，限制 2 CPU / 2 GiB / 无额外 swap、network none、只读 code/fixture、独立输出，只操作本次容器；补命令构造及退出传播测试，不改根 Compose/生产镜像/后端。
- [x] 2.5 在独立测试容器执行新增性能支撑模块的逐模块隔离覆盖；分离 profiler/coverage 诊断模式与无额外采样开销的验收模式，验证观测不改变同一 fixture 的正式结果。

## 3. 修复 Normalizer 重复定义枚举

- [x] 3.1 在完整 Evidence 合并后建立单次调用的宏定义 ID 索引，复用全部宏附属引用查询，保留现有排序、fatal、Diagnostic、canonical/scope 和 provenance，不增加跨扫描缓存。
- [x] 3.2 完成 macro reference 正常/缺失/类型错误、乱序、跨调用和多上下文等价单元测试，校验整个 StageResult/NormalizedSnapshot；用受控访问计数证明索引构建次数不随宏 token 数增加。
- [x] 3.3 在独立容器通过 normalizer 的 90% line / 80% branch 门禁和既有 knowledge/frontends 回归，记录该查询部分的复杂度与内存变化。

## 4. 按阶段证据处理剩余瓶颈

- [x] 4.1 对同一完整 libarchive 做有界 phase profile，记录归一化修复后各阶段耗时/数量与剩余热点；明确是否需要修改 graph/detector/projection，而非预先进行全面重写。
- [x] 4.2 对确有必要的重复查找复用现有索引或增加单次调用多值索引，逐项记录证据与语义边界；没有必要修改的阶段记录理由并保持不动，超出局部优化范围时先报告并调整设计。
- [x] 4.3 为每个实际修改的后续业务模块补充内存 snapshot 单元映射，覆盖多值关系、稳定顺序、不同 configuration/producer、完整与未知 proof、非法引用和跨扫描隔离，并逐模块通过 90% line / 80% branch。
- [x] 4.4 复用现有 fact/knowledge matcher 生成 Evidence 需求，注入正式源码 Analyzer，保留候选、hint、基础关系与最终 Detector 顺序。
- [x] 4.5 实现需求关系下游目标与反向可达起点计划、图邻接缓存；详细搜索保留原算法并与全目标小图 oracle 比较全部需求相关 proof。
- [x] 4.6 隔离构建和测试阶段新增关系/proof 预算，增加继承大量无关图、局部耗尽及诊断一致性回归；记录外部结果差异。

## 5. 全量性能与兼容性验收

- [x] 5.1 在独立容器运行性能相关隔离单元与复杂度门禁，之后运行既有完整回归；验证 ARM/no_sanitize 排除、unknown asm、AVX、架构 enum、三个原生崩溃缩减样例及两份 compiler facts 哈希。
- [x] 5.2 对确定性 fixture 验证默认 V2、显式 V2/V1 的优化前后语义一致，检查 ID、source span、reason、proof/trace/evidenceChain、summary/readiness、Diagnostic 和退出状态；显式审校预算隔离差异，不自动更新 golden。
- [x] 5.3 在固定 2 CPU / 2 GiB 容器、无 coverage/cProfile 下连续运行两次独立新进程的完整 libarchive 默认 V2；每次须 <300 秒、exit 0、覆盖完整 810 输入且三个 artifact/schema/引用校验通过，记录两次实际耗时和峰值资源。
- [x] 5.4 对首次完整 libarchive 报告抽查代表性源码、命中根/证据链及 unknown/诊断，审校后记录性能与语义基线；明确旧全量超时不可做 finding 数量等价比较，预览零命中不可替代此步骤。
- [x] 5.5 更新性能维护文档和模块 inventory，说明固定输入准备、独立容器命令、计时边界、超时回收、profiling 方法与尚存限制；不得以提高预算、降低分析范围或跳过 fixture 宣称完成。
- [x] 5.6 对 change 执行 OpenSpec strict validation，确认单元覆盖、全量兼容与两次性能门禁均闭合后再提出 sync/archive；任何性能验收未通过时保留任务未完成。

## Apply 完成记录（2026-09-09）

24/24 完成。事实需求、反向查询计划、邻接缓存、局部预算隔离和构建按需知识匹配均实现；350 项隔离单元与逐模块 90/80 门槛通过，完整 runner 的 14 个门禁和 204 项回归通过，golden 未更新。完整 libarchive 两轮 153.601/131.985 秒，峰值 RSS 611272/611168 KiB，exit 0、OOMKilled=false，810 输入及 V2 引用校验通过，两份报告 digest 一致。139 个源码 context / 829 行文本与固定源码逐行核对通过；已知 checksum/格式枚举候选噪声已写入审校记录，不宣称其为真实迁移阻塞。详见性能文档与 review-baseline.json。未执行 sync/archive/commit/push，未修改其他任务文件。

## Apply 暂停记录（2026-09-09）

用户现已确认复用现有 facts 的按需反向追溯设计并授权继续 apply；此节以下为历史暂停证据，当前按新增 4.4–4.6 任务继续。

已完成局部宏/合并/分支/关系/枚举查找索引，340 项隔离单元及 7 模块覆盖门槛通过，小 fixture V1/V2 与优化前完整 JSON 一致。最新完整 libarchive 仍在 300.043 秒超时，未通过 5.3，也不存在可供 5.4 审校的完整报告。

有界 profile 已定位剩余开销为 ProofPathResolver 的 36,304 × 3,737 = 135,668,048 对路径查询。继续优化需要讨论候选目标收敛/同源遍历复用的设计，超出当前“不更换图算法”的局部查找优化边界；4.2 保留未完成，proof/store 尚未修改。详见 docs/large-project-performance.md。OpenSpec strict validation 已通过，但不等于实现验收通过。
