## Context

当前 V2 直接消费 staged snapshots。chain.py 将 classification/assessment 追加到 primaryPath；非 RPM 链按 step kind 排序取代表，再生成相邻连线。RPM 已使用部分实际 proof 端点，枚举也有专门关系映射，但普通宏/guard/build 仍不能统一保证真实拓扑。context.py 默认为前后各 2 行，模型/Schema 限制 16 行、4096 字符，截断从尾部删行可能先丢失命中。

已有 source graph 的 invokes_macro/expands_to/guarded_by、Make target/source/include 关系和 compiler argument facts 可以复用；它们不等于已经完整证明 -D 参数作用于某个条件宏。当前工作区其他任务的 tools/memory-order-analyzer 不在范围。openspec/config.yaml 中旧 V1/YAML 背景不代表恢复旧运行时，本次以正式默认 V2 与显式 V1 合同为准。

## Goals / Non-Goals

**Goals:**

- 每条 Finding 显示当前命中的真实上游，保留多级同类宏、条件、构建参数及各自源码，不显示分析阶段节点。
- 实现可验收的 Makefile → 目标/源码配置 → 条件宏 → 宏调用/展开 → intrinsic 最小完整链，并对缺失段明确 unknown。
- 所有代码位置统一前后各 20 行，受硬预算保护，精确命中不能被普通上下文挤掉。
- 保持事实、结论、项目评估与知识来源，不通过少报 Finding 或删除原始事实换取简短链路。

**Non-Goals:**

- 不开发前后端详情页面，不更新服务/生产容器，不创建 V3 或第二报告。
- 不执行 Make、编译器、RPM/Shell 或项目测试，不实现完整 Make/C 预处理器，不建模 uname 交叉编译误选。
- 不采集或改写两份 GCC/Clang 事实数据，不扩展 ARM/OS/内核或内存模型分析。
- 不重做分类评估政策；确有新增证据引起结论变化必须单独审校，不把投影调整当作重新分类。

## Decisions

### 1. 分离代码证据、知识依据和结论

生产输出 steps 不再生成 classification/assessment，edges 不生成 classified_as/impacts_assessment。conclusion 和 summary 保留现有职责；内部 Classification/Assessment snapshot 和 typed provenance 类型保留。

知识仍以紧凑 knowledge_match step 留在同一 Finding，真实命中 Evidence 通过 matches_knowledge 指向它，作为旁支依据，不进入代码 primaryPath。不得把某知识关联到未命中的普通调用。没有知识匹配的链不造空 knowledge 节点。

impactStepIds 保留但新结果输出 []。JSON Schema 放宽 minItems，历史 classification/assessment kind 仍可被读取/校验，新 producer 禁止输出；生成行为和旧数据接受能力分开测试。不把 deprecated 字段改指 intrinsic 来伪装兼容。

替代方案：仅前端隐藏节点不解决 JSON 冗余和伪连线；彻底删字段或新增报告版本会扩大迁移范围，均不采用。这里是保留外形的受控 V2 语义修订，不是对旧严格消费者完全透明的扩展。

### 2. 命中驱动闭包，实际端点生成边

Mapper 明确当前 matched Evidence/primary occurrence，并把锚点传给链构造，不再让 kind 排序抢占主事实。按 occurrence + configuration 查询，最终在一个 Finding 内去重合并；某个 occurrence 的证明不能替另一个 occurrence 补齐。

构建一次 Entity↔Evidence/入边/出边索引，复用已有 fact 驱动 proof 需求。优先使用相关 ProofPath，再按类型受限遍历补齐宏定义、嵌套 guard、include 和构建作用依据；不对每条 Finding 扫描全图，不恢复全 root×terminal 查询。允许从宏命中沿展开关系向终端 intrinsic 查询，不能把反查误写为纯入边 BFS。

每条可展示 source-to-source edge 必须解析出真实两端及 Relation provenance。建立显式关系映射表：
- invokes_macro：调用 → 定义；expands_to/calls：定义/调用 → replacement/终端。
- guarded_by：底层为被保护对象 → 条件；上游优先展示时可投影为条件 → 对象的 selects，记录原始 relation 和可选 org.rvport.kb-scanner.source-chain 扩展中的原始端点/方向。此为已验证关系的方向映射，不重新求值选择。
- build 参数 → 目标源码/条件：只能使用新分析层的作用域证明。
- includes/defines/contains/alternative_to：仅在真实端点和语义相符时投影，禁止“相同 kind”作为 contains 依据。

允许折叠没有独立位置的结构性 Entity，但折叠 edge 必须保留组成它的全部连续 Relation provenance；不为抽象 selector 伪造文件/行号。无法投影的段保留断点，不能取任意第一条 relation ID 填充 provenance。

primaryPath 是包含命中锚点的一条真实连通路径；完整构建上游存在时按上游到命中/终端顺序展示。多条等价路径用稳定位置/ID 决定主路径；非等价候选保留分支和 ambiguous，不选一个假装确定。多级同 kind 全部保留，不拼接互不连通的候选。只有局部命中时 primaryPath 可以是单节点；已知缺失的上游用 break 解释，不能构造虚假入口。

链完整性由相关事实/关系/预算推导；unknown candidate 仍遵守结论与链的 unknown 合同，但原因用缺失目标配置、未知候选相关性等具体事实，不再用 classification 阶段作为代码断点。源码 context 缺失/截断保留 span 并给出局部 partial 原因，不改变内部风险结论。

### 3. Makefile 参数到条件宏的有界桥接

计划拆出独立 build macro binding 模块，复用已有 Make 变量/target/source facts 与原始参数位置，避免 Projector 推理 Make 语义。

首批支持输入：
- 简单已知变量赋值/追加及引用链形成的 CPPFLAGS/CFLAGS/CXXFLAGS。
- 已有可证明目标/源码成员关系，及可静态词法恢复的编译 recipe 参数引用；只读结构，不启动命令。
- -DNAME、-DNAME=value、分离 token 的 -D NAME[=value]，以及 -UNAME，保留参数顺序、定义来源、configuration 和精确位置。
- 简单 #ifdef/#ifndef、defined(NAME)、已知整数宏的 #if NAME 或受限等值比较及嵌套条件；未覆盖表达式保持 unknown。
- 同一 translation unit 可证明的 include 可见性与局部 #define/#undef/覆盖顺序；多配置分别处理。

关键区别：CFLAGS 中写了 -D 不等于该变量被当前编译命令使用；目标成员关系也不等于参数作用关系。必须分别证明参数来源、实际静态引用、目标源码归属和条件宏绑定。缺少任一项可保留候选关联/断点，不得确认启用。-DNAME=0 对 #ifdef 为真，对 #if NAME 为假；-U 或源内覆盖不能被忽略。同名出现在其他 target、注释或无关文件时不能连到命中。

函数式条件、复杂递归 Make、eval/shell/response file、无法恢复的 recipe、未知外部宏和冲突配置保持 unknown。-mavx2 不直接等价于任意用户宏；编译器预定义宏若没有适用且可追溯语义映射，本 change 不猜测。

关联写入现有 scanner-owned Evidence/Relation/ProofPath，复用合法关系种类与内部 metadata，不把声明位置变成真实运行/编译证明。投影层只消费结果。新增证据可能修正部分 reachability，必须通过白名单差异账本解释每个分类变化。

### 4. 上下各 20 行与命中优先预算

统一 source projector：beforeLines=20、afterLines=20；窗口为命中起始行之前 20 行到结束行之后 20 行，文件首尾自然收缩，单行通常 41 行。默认硬上限建议 maxLines=256、maxCharacters=65536，模型/Schema 同步；本轮扩大上下文不放宽图预算。

先保留命中行，再公平分配距离最近的前后文。正常预算内多行命中必须完整返回；命中自身超预算时保留有界可定位部分、原始完整 span、partial 和 context_budget_exceeded，不能声称完整窗口。单条超长行也必须遵守字符上限：无法提供包含命中列的原文行时允许省略该行并标记 partial/unavailable，不输出越界 highlights 或伪造列号；不为凑高亮读取无限长文本到输出。

按文件缓存读取与 splitlines 结果，按规范 span/窗口缓存不可变投影；不同节点使用自己的位置，不能复制另一命中的 context。缓存仅本次投影生命周期有效，继续限制根外读取、路径穿越和解码失败。共享 projector 的 Diagnostic context 默认也遵循同一窗口，纳入回归。

替代方案：只调 before/after 会被 16 行上限再次裁掉；按需前端读源码违反自包含合同；取消预算会造成大文件放大，均不采用。

### 5. 契约、历史结果和性能

保留默认 2.0 与显式 1.0、scan-result.json/scan-report.html/scan.log。同步 Pydantic model、JSON Schema、reference rules、vocabulary、examples、迁移说明与 schema-v2-design。旧 V2 严格校验器需升级：impactStepIds 可为空，上下文预算提高，生产主链不含判断阶段。保留历史枚举值可读取不意味着新输出允许继续使用旧节点。

不额外扩展完整交互式 HTML；核对 scanner 自有 renderer 在新链/空 impact 上不崩溃，仍安全转义文本。V1 继续走既有 projector，不能以 V1 补链。

GCC/Clang compiler JSON 的哈希、类别、ID 和 provenance 固定；knowledge 分支仍能离线追到原 entry/source digest。因上下文增加造成的 JSON 字节增长单独记录，不能误报成分析耗时退化或无条件接受任意增长。固定容器、输入、配置对比索引构建/查询、上下文投影耗时、RSS、报告字节；验收设置在实施首阶段冻结既有基线，至少保证每文件一次读取/拆行、相同 span 命中缓存、不重开全 root×terminal 搜索、原图预算未放宽。

### 6. 逐模块隔离单测映射

以下是职责映射，最终新增/拆分/改名必须更新 inventory，不允许因表中未列具体文件而豁免。

| 业务模块/职责 | 隔离 unit suite（计划） | 边界与断言 |
| --- | --- | --- |
| frontends/build/make.py 与参数/recipe 提取 | test_make_macro_arguments.py | fake source/reader；-D/-U、变量引用、目标作用域、未知命令 |
| normalization/build.py | test_build_macro_normalization.py | fake Evidence；原位置、顺序、配置、重复 occurrence |
| analyzers/build_macro_binding.py（拟新增）及 build_selection 接线 | test_build_macro_binding.py | fake facts/context；作用证明、覆盖、真假与未知 |
| analyzers/evidence_graph.py 或宏/guard resolver 的必要调整 | test_source_chain_relations.py | fake frontend nodes/snapshot；宏展开、嵌套 guard、可见性、原始端点 |
| projection/v2/index.py 与 source_chain 查询帮助模块（如拆出） | test_source_chain_query.py | fake DAG；正反向映射、同名隔离、循环、预算、输入乱序 |
| projection/v2/chain.py | test_source_evidence_chain.py | fake index；同 kind 多节点、不造边、主路径锚点、knowledge 旁支、无阶段节点 |
| projection/v2/context.py | test_source_context.py | fake reader；41 行、多行、首尾、超长行、Unicode/CRLF、截断/缓存 |
| projection/v2/mapper.py、projector.py | 各自既有 suite 加 source-chain 案例 | fake snapshots/delegates；锚点、conclusion 保留、V1 隔离 |
| projection/v2/models.py、validation.py | 各自既有 suite 加迁移正反例 | 封闭模型、空 impact、历史读入、端点/主路径、高亮约束 |
| 若改 renderer/serializer 或 diagnostic projector | 对应已有 isolated suite | fake payload/context reader；空 impact、安全文本、确定性 |

每个实质修改模块单独达到 90% line / 90% branch；所有代码测试仅独立 kb-scanner-test 容器运行，原生 Parser、文件读取、进程/网络边界 fake/mock。真实 Bash/C++ 语法、CLI、人工 fixture 和实扫是另列的 component/contract 验收，不计作隔离覆盖。test runner 必须可独立运行本 change 门禁。

## Risks / Trade-offs

- [真实图存在缺口，删除伪连线后链变短] → 明确断点和逐字段 oracle；不能为了保留旧外观恢复排序连线。
- [条件 guard 方向与展示顺序不同] → 显式、受测试的 relation 映射及完整 provenance，不做任意无向遍历。
- [Make 静态子集有限] → 定义输入白名单，最小正例必须真实闭合，反例保持 unknown；不得偷偷执行 make 获取结果。
- [新上下文放大报告/RSS] → 256 行/64 Ki 字符预算、缓存与固定基线记录；不削减正常输入的前后 20 行。
- [旧 V2 消费者依赖 impact 非空或固定行数] → 文档明确兼容边界，历史字段保留，模型与规则一起更新；服务接入留给独立任务。
- [新增作用域证据影响既有结论] → 将语义修正与纯投影差异分别审校；不得自动重写 golden 掩盖回归。

## Migration Plan

1. 冻结当前样例、真实最小链人工 oracle、结论和性能基线，登记模块门禁。
2. 补齐受限参数/条件绑定，建立真实端点与需求驱动闭包；每层带隔离单测。
3. 切换代码主链、旁支 knowledge、空 impact 与上下文窗口，原子更新机器合同/示例。
4. 独立容器完成 unit gate、契约/组件与 AVX、RPM、枚举、候选及 libarchive 等现有可用基线回归，记录差异。
5. 更新本地设计与支持文档，交付 apply 结果；由用户决定 sync/archive 和 commit/push。若需回退，按批准流程回退本 change 的实现与合同，不自动重置工作区、不恢复 Legacy。

## Open Questions

无阻止 proposal 的用户选项。具体帮助模块文件名、既有 Make 子集需要扩展的语法点及性能阈值在首阶段通过代码/固定基线核实；如无法实现最小完整链或必须扩大到完整解释器/新增依赖，应暂停说明，不能仅交付隐藏节点而宣称完成。

## Quality gate update (2026-09-11)

按用户最新全局要求，本 change 采用整体与每个受影响模块的行/分支覆盖率均至少 90%，原 80% branch 门槛不再适用于本次验收。统计必须包括未被单测加载的项目自有可执行源码，不能仅统计改动行或 inventory 子集；明确列出第三方、自动生成资产、测试代码及已归档非运行资产的统计处理。先测量当前生产包与维护脚本的历史基线，历史缺口若需大规模扩展到本 change 之外，则记录真实缺口并请求授权，不能自动改无关模块或标记验收完成。测试与覆盖率只在独立容器执行，交付记录必须列出命令、统计范围、行/分支结果和持久报告位置。
