## Context

调查发现两类问题：分析器内部的编排/协议缺陷，以及外部应用对候选、证据和完整性的误读。本 change 的当前责任只覆盖分析器和其输出合同。

2026-10-28 用户明确：当前 root 同时限定实施文件范围。所有新增修改只允许位于 D:/projects/RvPort/tools/memory-order-analyzer/。后端和前端的实现、测试、数据库、页面及报告业务逻辑不由本 change 管理。此前后端修改作为用户接受的本次历史例外保留；前端任务移交到前端 root，不再阻塞本工具变更。

## Goals / Non-Goals

目标：
- 恢复实际协议校验下的有效分析编排，准确表达阶段适用性、缺依赖及局部失败。
- 抑制缺乏内存序相关依据的对外源码候选，同时保留完整事实、分母和审计。
- 用版本化投影表达证据等级、置信度未知、主路径及断点，避免伪造正式结论。
- 保留完整诊断、跨配置身份及缓存隔离，在 Docker 中完成工具质量门槛。

非目标：
- 修改当前 root 之外的任何文件，或把前后端工作留作本 change 的实施任务。
- 实现前端页面、后端导入/API、Workflow、报告纳入业务或其测试。
- 新增通用 HB 求解器、现场生成 BC、证明全程序安全，或批量改写历史结果。
- 将外部未验收功能标记完成，或自动同步/归档本 change。

## Decisions

### 1. 在调用边界规范化身份和依赖

AST source requests 按 TU/profile 合同排序，LLVM binding 按 artifact key，R3 members 按 physical TU。相同身份同值重复可幂等归并，内容冲突显式失败；record/TU/artifact 映射与计划分母不丢失。

P4 消费协调器选定并校验的显式 P3 请求，取消目录通配及后缀转整数猜测。R3/R2/对象分析在调用前检查 members、EffectSummary、root plan、thread-entry overlay 和 source/LLVM 请求；缺依赖记录根因，不提交无效请求或伪造 complete empty。

### 2. 标准、profile 与阶段完整性独立判断

compiler-default 无可信有效标准时保留未知；legacy 使用 schema 接受的 legacy-no-iso-atomics-v1，不能获得 ISO 原子证明。按标准分组绑定输入，一组失败不删除其他组证据。

C++ thread/RAII profile 严格检查 standard、vendor、target、DataLayout、ABI；零匹配、多匹配及未知 vendor 均有明确诊断，不能借用其他 TU 配置。只有完整可信证据证明不存在相关构造时才跳过阶段；AST/IR 缺失、ModuleFacts partial 或相关 frontier 均影响完整性，产物存在不能代替证据完整。

### 3. 候选准入与去重可审计

保留 SourceSemanticFacts 和原始 SourceCandidate；统一报告只发布具有显式原子、线程、同步形状或同 Scope/TU/profile 直接关联访问的候选。未知 wrapper 只作为需核实线索，普通读写、循环或条件本身不准入。

data/candidate-admission/<scope>.json 保留 raw/admitted/excluded 与逐项原因。身份按 Scope、TU/profile、形状、节点和关系规范化，保留不同问题及全部 occurrences；预算截断和未准入均不能解释为安全。

### 4. 3.0 投影与历史 2.0 明确区分

MemoryOrderFindingProjection 3.0 保留 fact、occurrences、evidenceChain，conclusion 新增 evidenceLevel：source-only、incomplete、bounded-model。未评估 confidence 为 null；source candidate 输出 info、非阻断、unknown/partial，正式风险保留实际评估与模型边界。

title/reason/detail/suggestion 提供具体双语解释，按实际形状列适用缺口；不机械要求 mutex 候选具备原子 RF/MO，也不臆造符号、线程或共享关系。

工具 validator 仍读取合法 2.0，保留其原始数值和制品；未知版本或顶层/逐项版本冲突显式拒绝。统一报告 finding_schema_version=3.0，其他分析协议独立演进。外部展示适配只在交接说明中记录。

### 5. 诊断、证据链与缓存

诊断按 Scope/TU/record、code 和细节归并，references 保留所有受阻阶段；诊断与 frontier 分别保留含义。summary 的 diagnostics_total/frontier_total 是截断前数量；超过预算保留 diagnostic-budget-exhausted，完整诊断写入 diagnostics/full.json 并纳入制品索引。

steps 使用稳定 ID 存储，primaryPath 表达逻辑顺序，edges 表达分支，breaks 表达缺口。工具校验引用与身份一致；无直接源码的断点保留缺口，不能冒用其他 occurrence。

缓存命名空间 unified-project-analysis-results-v3 与投影阶段 memory-order-finding-v3 隔离旧语义。制品索引和缓存复制过滤嵌套 .task-* 目录及点号开头的 .tmp 暂存项，防止跨 Scope 并发读取未发布文件导致结果丢失。

### 6. 工具自身的 Docker 验证

单元测试覆盖正常、边界、异常及 partial/unknown。真实 validator 不被 mock 成成功；真实 worker 集成与单元覆盖 profile 分开，仅预生成合成 fixture BC，不在产品流程编译被分析程序。

工具全量 Python/C++、每语言及每模块的行/可用分支均至少 90%，包含未加载源码、可执行头和自有质量入口。仅排除有理由的第三方、测试框架/纯输入夹具、生成元数据和经摘要核对的纯声明头；不降低门槛或缩小分母。

编译、安装与测试在 Docker 中完成，独立容器/卷、network none、CPU/内存/并发限制。工作目录固定工具 root，新报告输出到专用 Docker volume；需要导出时仅写当前 root 下的非公开目录。历史根目录报告仅供读取，本次不移动或改写。

容器内的可重复入口：

```sh
python3 -m memory_order_analyzer.quality --output /output/repair-memory-order-analysis-results-<新编号> --integration
```

已实际通过的最终运行是 quality-005：884 Python 单元、118 C++ 单元、98 集成；行 19863/20259（98.05%），分支 11403/12185（93.58%），所有独立门槛通过。精确历史命令和报告位置见 implementation-notes.md。本次纯 artifacts 修订仅执行内容、链接、范围和 OpenSpec 校验，不声称重跑代码测试。

## Risks / Trade-offs

- 候选准入过窄：保留原始事实和审计，以普通循环负例、原子/线程/wrapper 正例及混合证据夹具验证。
- 诊断归并丢失身份：跨 Scope/TU 分离，同根因保留受阻阶段和完整审计。
- 外部消费者仅支持 2.0：提供 3.0 合同与历史兼容交接，由外部 root 负责接入；不能以此扩展本 change 文件范围。
- profile 不覆盖真实 ABI：保守输出不支持/未知，不解除配置约束。
- 外部页面仍误读结果：前端问题独立移交，不用工具测试冒充页面验收。

## Migration Plan

1. 工具实现和全量质量验收已经完成，当前收紧 artifacts 到工具 root。
2. 移除原 memory-order-result-consumption delta 和前后端任务；保留非规范性前端交接说明及历史后端记录。
3. 外部团队在自己的 root 安排接入和验证，不再回到本工具 change 修改外部文件。
4. 后续如需本工具归档，单独由用户触发；不自动同步或归档。回滚工具时保持生产者、validator 和缓存版本匹配，不改写旧制品。

## Open Questions

本工具范围内无待决定事项。前端接入进度由前端项目跟踪。