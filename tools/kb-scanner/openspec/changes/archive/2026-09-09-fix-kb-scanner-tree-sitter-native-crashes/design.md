## Context

当前 C/C++ Tree-sitter adapter 会把整棵树的 `Node` 保存为 tuple，并在普通 Evidence、宏、枚举守卫和 partial-parse Diagnostic 中读取 `Node.start_point`/`end_point`。在 `tree-sitter==0.26.0` 下，真实项目已证明 `Point` 字段读取可能返回指针形态的异常整数，并随后在 JSON 编码或垃圾回收等无关 Python 位置表现为 SIGSEGV。三个无 `compile_commands.json` 的项目均沿同一路径退出 139，说明故障位于 baseline frontend，而不是 libclang 或单个项目。

同时，`_node_kind` 会把每个 `condition_clause` 和带 value 的 `case_statement` 直接转换为 `selection_condition`。这既把 `case '0'`、`case 0` 和普通状态机分支错误地放进架构选择证据，又使 Evidence 构造和稳定 ID 序列化的规模与所有控制流节点数量一起增长。

本 change 只修复 Scanner 的静态 C/C++ 分析链路。Scanner 不编译、链接或运行被扫描项目；不处理 OS、内核、系统调用、驱动或板级迁移；`uname` 等架构探测仍可作为静态 selector 分析，但假定运行时返回正确架构，不建模交叉编译选错分支。

## Goals / Non-Goals

**Goals:**

- 从生产 Tree-sitter 路径完全移除 Python 对 `start_point`/`end_point` 的读取，并保持现有 1-based 行号、1-based UTF-8 字节列号和 end-byte 位置语义。
- 将位置计算降为每文件一次建索引、每次查找对数复杂度，统一服务普通节点、宏、枚举、错误恢复和 Diagnostic。
- 只为可验证的枚举成员引用保留对应选择上下文，消除普通条件和字面量/state-machine case 的宽泛 Evidence。
- 明确 Tree/Node 生命周期，避免将原生 Node 集合泄漏到 adapter 外或在文件分析后继续持有。
- 在独立测试容器中对三个固定上游版本建立可复现的崩溃、语义、性能和输出兼容回归。
- 保持 Schema V2 默认、V1 显式兼容、三类 artifact、现有 Evidence 链表达和两份编译器事实数据不变。

**Non-Goals:**

- 不修改后端、根 Compose 或生产镜像。
- 不通过降级到 Tree-sitter 0.25.2 掩盖根因；版本降级只保留为人工应急回滚选项。
- 不在本 change 引入 parser 子进程隔离。未来可单独设计 worker isolation，将新的原生崩溃降级为文件级 partial Diagnostic。
- 不扩大 enum 词汇、知识采集或迁移分类规则，也不重新设计 V1/V2 schema。
- 不执行被扫描项目的配置、构建、编译、测试或真实 RISC-V 运行。

## Decisions

### 1. 使用源字节索引计算全部位置

新增一个小型、不可变的 `SourceByteIndex`（最终文件名可遵循现有模块命名），输入为本次 parse 使用的原始 `bytes`。构造时保存 `0` 以及每个 `\n` 后的 byte offset，形成递增的 line-start tuple。`location(offset)` 使用二分查找得到所在行：行号和列号均转换为 1-based，列按 UTF-8 原始字节计算；`span(start_byte, end_byte)` 复用两个 location。CRLF 中 `\r` 仍属于前一行内容，换行以 `\n` 为界，从而与当前 byte-column 语义一致。

所有 Tree-sitter 位置只读取稳定的整数属性 `start_byte`/`end_byte`。无效的负数、逆序或超出 source 长度的范围不得被静默截断，而应在可恢复的文件路径产生结构化 Diagnostic；Tree-sitter 的合法 ERROR/MISSING node 仍能用 byte offset 定位。宏 token 的现有 `_span_from_byte_range` 也迁移到同一索引，消除每次切 prefix/count 的 O(n) 成本。

备选方案是“每个 Point 只读取一次并立即转整数”。真实 cJSON 复现证明第一次字段读取本身就可能破坏内存，因此拒绝。另一个方案是固定 0.25.2；该版本在原触发点未立刻崩溃，但真实 cJSON 扫描持续高 CPU，且不能解决宽泛选择 Evidence，所以不作为正式设计。

### 2. 选择 Evidence 由已绑定枚举引用驱动

从通用 `_node_kind` 中移除 `condition_clause`/`case_statement` 到 selection kind 的无条件映射。枚举阶段按如下顺序工作：

1. 遍历 enum declaration/enumerator，建立只含字符串、byte range、style 和声明身份的本地符号表。
2. 再次从 `tree.root_node` 遍历引用候选；只接受 qualified reference，或在 `if`/`if constexpr`/`switch`/`case` 中能唯一或明确标记为 ambiguous 的本地 enum member 候选。
3. 为命中的 reference 找最近的 selection guard，按 guard byte range 去重；只有 guard 内存在上述 enum reference 时，才产生 `constexpr_condition`/`selection_condition`，并显式记录关联 reference Evidence ID、selection context 和 guard byte span。

因此，`case '0'`、`case 0`、没有本地 enum 绑定的 `case TYPE` 和普通 `if` 不产生 selection Evidence。真正的 `Backend::avx2` 会保留 declaration → member → reference → condition 的完整上游链。非架构 enum 的语义事实仍可存在，但是否为 x86/RISC-V 架构候选继续由 Normalizer/Detector 和知识数据决定；Frontend 不加载知识集，也不直接给出迁移结论。

备选方案是继续采集全部条件，再让 Detector 过滤。它仍会经过危险的 SourceSpan/稳定 ID 路径并造成证据膨胀，故拒绝。

### 3. 原生对象只在单文件 parse session 内存活

`Parser`、`Tree` 和当前遍历 Node 的所有权限定在 `_parse_candidate` 调用内，Tree 在所有遍历结束前保持强引用。后续阶段和 `_ParseCandidate` 只接收 Python 自有的 Evidence、Diagnostic、字符串、整数、tuple 和 byte range，绝不接收 Node/Tree。

adapter 不再创建整棵树的持久 `tuple(_walk(...))`。需要两次扫描时从仍存活的 root 重新遍历；跨 pass 保存的是轻量枚举符号快照、错误 byte range 和 Evidence ID。辅助函数不得返回或缓存原生 Node。这样不能消除原生库自身的所有风险，但能缩短对象持有时间并避免 Node 与 Tree 生命周期脱节。

### 4. 依赖版本先保持，增加可执行兼容门禁

正式方案先保留当前锁定的 `tree-sitter==0.26.0`、C grammar ABI 15 和 C++ grammar ABI 14。测试启动时记录 binding/package/grammar 版本及 ABI，并断言 grammar ABI 位于 binding 支持范围内。ABI 范围通过不代表无 bug，所以还必须通过 Point 禁用测试与真实项目进程级回归。

任何未来依赖变更必须只修改 `tools/kb-scanner` 的测试/runtime lock，并重新运行全部门禁；不得在宿主机安装包。若紧急人工回滚到 0.25.2，应视为临时运维动作，并在后续 change 中重新验证和恢复，不替代本修复。

### 5. 单元、组件与真实项目回归分层

如果新增 `SourceByteIndex` 模块，它必须有独立单元测试，覆盖空文件、LF、CRLF、多字节 UTF-8、行首/行尾/EOF、超界和逆序范围，行覆盖率至少 90%、分支覆盖率至少 80%。Tree-sitter adapter 单元测试使用 fake Node，其 `start_point`/`end_point` getter 直接抛出 `AssertionError`，覆盖普通 Evidence、宏、enum guard 及 ERROR/MISSING Diagnostic，证明生产代码从不访问 Point。fake parser/Tree 隔离原生依赖边界。

enum 单元测试覆盖 `case '0'`、`case 0`、无 enum 绑定的状态常量、普通 if 的负例，以及 `Backend::avx2`、C enum switch 和 ambiguous binding 的正/降级路径。测试清单必须映射所有新增或修改的业务模块，并由独立 coverage gate 执行 90% line / 80% branch。

真实项目回归固定 cJSON、zlib、libarchive 的提交和来源许可证。默认离线门禁使用仓库内最小但保持原触发语法/文件来源的合法夹具；可重复的完整项目 gate 使用预先固定的只读 source fixture，不在测试时联网，也不运行项目代码。每个项目从独立子进程启动 Scanner，以便明确断言没有信号退出/139；同时断言 exit 0、三类 artifact 可解析、V2 默认和显式 V1 均符合合同，并限制扫描耗时与 Evidence 数量，防止恢复两分钟高 CPU或全条件采集。

Clang/GCC x86 facts 通过既有 SHA-256 防变更断言：Clang `ADF187416C006B120E43F2D2CE0677EE2104A4C27DE4DD9CABD1DF12ADD352F7`，GCC `89775341EE880B13AC4F10A30558FF5D52875B25A3233114A5765601F0A9DAD9`。

### 6. 输出只做行为保持验证

本 change 不增加新的顶层结果结构。修复后的 Evidence 继续进入现有 Normalizer、Evidence Graph、Detector、Classifier、Assessor 和 Versioned Projector。V2 仍为默认；调用方明确请求 `1.0` 时走 V1 兼容投影；`scan-result.json`、`scan-report.html`、`scan.log` 仍是唯一三类正式 artifact。

移除误采集 selection Evidence 会减少错误的上游步骤和关联 Finding，这是批准的正确性修复，不是 schema 变更。缺少可验证 enum binding 时结果应表达为没有该项架构 enum 证据或 unknown，不得据此声明 RISC-V ready。

## Risks / Trade-offs

- [字节列号与用户感知字符列不同] → 明确保持既有 Tree-sitter UTF-8 byte-column 语义，并以多字节测试锁定合同。
- [多次树遍历增加 CPU] → 取消整树 Node tuple 和全条件 Evidence 后总体工作量下降；以真实项目耗时与 Evidence 数量预算验证。
- [局部 Tree-sitter binding 可能遗漏跨文件 enum] → 保留 ambiguous/partial 语义并由可选 Clang enrichment 补充，缺证据按 unknown 处理。
- [原生库仍可能在其他 API 崩溃] → 进程级回归捕获当前风险；通用 parser worker 隔离留给后续 change。
- [上游完整项目夹具体积或许可证成本] → 默认保存最小合法来源快照与 provenance，完整项目使用固定、只读、离线 fixture；实现时先审查各许可证和仓库策略。
- [性能门禁受机器差异影响] → 使用宽松的墙钟上限并同时检查 Evidence 数量/文件进度，避免只依赖绝对耗时。

## Migration Plan

1. 先加入位置索引、Point 禁用测试和旧行为对照，迁移所有 node/macro/diagnostic 位置调用点。
2. 再移除通用 selection 映射，实施由 enum reference 驱动的 guard Evidence，并更新正反例。
3. 加入依赖 ABI/版本审计、三个固定上游回归、性能预算和 V1/V2/artifact/fact hash 合同测试。
4. 只在 `kb-scanner-test` 中运行单元覆盖、组件、真实项目及完整回归；通过后随正常 scanner 发布进入使用。

回滚时可回退本 change 的 scanner 代码和测试锁变更，不触碰后端、生产 Compose 或知识事实文件。若线上必须临时规避，可由维护者单独锁回已验证版本，但必须保留退出 139 监控并尽快恢复正式修复。

## Open Questions

- 三个上游项目的默认离线回归采用“最小来源快照 + 可选完整项目 gate”还是仓库内完整 source archive，需要实现阶段依据仓库体积与许可证审查决定；无论选择哪种，三个固定提交的进程级扫描都必须存在于可重复验证流程。
- 性能门禁的具体墙钟阈值需在目标 CI/test 容器基线测量后固定；Evidence 数量上限可直接按修复后的确定结果固化。
