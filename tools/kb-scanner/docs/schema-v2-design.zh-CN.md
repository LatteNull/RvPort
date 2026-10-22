# KB Scanner 结果协议

[English](schema-v2-design.md) | 简体中文

## 设计结论

schema v2 以单个 Finding 为详情边界。每条 `findings[]` 自包含 `fact`、`conclusion`、`occurrences[]` 和 `evidenceChain`；前端点击 Finding 后可以一次取得完整主链、分支、断点、每个命中位置及逐行代码上下文，不需要通过顶层 Explanation、Catalog 或 scanner 内部 snapshot 再拼装。

列表与详情是不同消费投影：列表只读取 Finding 的 ID、fact 主位置和 conclusion 摘要；详情返回完整 Finding。`scan-result.json` 仍保存完整 `findings[]` 以支持离线审计，但后端不得把整个文件作为一个不可查询 JSON 字段代替逐 Finding 持久化。

```text
Finding
├─ fact：scanner 实际找到的静态事实
├─ conclusion：severity、actionability、blocking、迁移理由和建议
├─ occurrences[]：全部命中位置、配置和选择状态
└─ evidenceChain
   ├─ primaryPath[]：详情页默认展示顺序
   ├─ steps[]：构建、源码、宏节点，以及旁支 knowledge 依据
   ├─ edges[]：节点关系和候选/替代分支
   └─ breaks[]：缺失、冲突、歧义、循环或预算截断
```

## schema 1.0 compatibility baseline

Scanner 默认生成 `schemaVersion: "2.0"`；依赖旧字段合同的消费者必须显式传入 `--schema-version 1.0`。单次扫描只生成所选版本的同名三个 artifact，V2 失败不得静默回退 V1，也不存在 V1→V2 转换层。后端与前端通过当前 V2 合同消费列表、详情和证据链。

## 字段职责

| 字段 | 负责表达 | 不负责表达 |
| --- | --- | --- |
| `fact` | 实际命中的事实类型、symbol、文本、主位置和事实 provenance | severity、blocking 或项目 readiness |
| `conclusion` | 对该事实的分类、严重性、actionability、blocking、理由、建议和静态 Assessment 影响 | 原始代码证据 |
| `occurrences[]` | 同一 Finding 聚合的全部 source/build/test 位置、配置与 selection status | 用 occurrence 数量替代 Finding 计数 |
| `evidenceChain` | 从构建参数/选择条件到源码、宏调用/展开的真实关系子图，knowledge 为旁支 | classification/assessment 阶段节点、整个项目的无关 Evidence Graph |
| `summary` | 以 Finding 为单位的项目计数、静态 readiness 与完整性摘要 | 从零命中推断 ready |
| `diagnostics[]` | 扫描级或可关联 Finding 的结构化异常、聚合数量和引用 | 将机器字段编码进文案字符串 |

## 代码上下文与位置

所有代码型 fact、occurrence 和 step 都使用同一 `source` 结构：规范化项目相对路径；一基、end-exclusive 的完整 span；带真实行号的 `context.lines[]`；以及精确的 `highlights[]`。宏调用、宏定义、replacement、intrinsic 和 Makefile selector 各自携带自己的位置，禁止复制另一步的位置。

默认上下文窗口为命中范围前后各 20 行，单行命中通常返回 41 行；每个 location 硬上限为 256 行、65536 字符。命中优先，再均衡分配距离最近的前后文。读取失败或超过预算时保留原始 span，将 context 标记为 `partial`/`unavailable` 并给出 reason。过长行可以省略，但不能伪造列号或输出越界高亮。每次扫描共享文件拆行与 span 投影缓存；不跨扫描复用。扩大上下文由后端独立 code-context 接口负责。

## 链路与完整性

`primaryPath[]` 是确定性的默认展示顺序，不要求前端自行从任意图中找路。`steps[]` 包含与该 Finding 有关的全部候选和支撑对象，`edges[]` 保留实际 Relation/ProofPath provenance，`breaks[]` 把断点作为一等信息展示。

新 producer 的主路径必须包含本次命中锚点，按真实端点连通，不按 kind 选代表节点。多层同类宏各自保留；`guarded_by` 的方向可映射为条件 → 被保护对象，并在 `org.rvport.kb-scanner.source-chain.incoming` 扩展中保留原关系端点/方向。无位置结构节点可以折叠，但须携带全部连续关系。无关 occurrence 或同名候选不能拼成一条 complete 路径。

`classification`/`assessment` 不再生成，`impactStepIds` 固定为 `[]`。判断从 `conclusion`/`summary` 读取。`knowledge_match` 仅通过实际命中的 `matches_knowledge` 旁支展示，不进入主路径。已有历史 V2 阶段节点仍可被新版 reader 读取，不代表 producer 继续输出它们。

- `complete`：所展示的相关主路径全部 step/edge 完整且没有已知 break；只证明局部源码关系，不证明所有调用者已穷尽或 RISC-V 编译成功。
- `inactive`：完整证明 x86 路径未被目标配置选择；只表示 guarded/non-actionable，不单独证明项目 ready。
- `partial`：已有部分证据，但输入、引用或预算不足。
- `ambiguous`：存在多个可验证但无法唯一选择的候选。
- `unknown`：静态分析无法形成足够结论。

`partial`、`ambiguous` 和 `unknown` 必须至少包含一个 break。空数组、零计数和字段缺失不得表示“没有问题”。详细跨字段规则由 `schemas/scan-result-v2-reference-rules.json` 冻结。

## Knowledge 与静态边界

Knowledge step 只携带当前 Finding 实际引用的紧凑投影：entry ID、category、symbol、producer、source identity/digest 和 provenance。它不会复制完整 compiler fact 文件。现有 `clang-x86-entries.json` 与 `gcc-x86-entries.json` 保持原字节、六类计数和来源，v2 只改变报告投影。

顶层 scope 固定声明 `staticAnalysisOnly=true`、`compiled=false`、`linked=false`、`testsExecuted=false`。x86-only、blocking 或 ready-like 字样只能解释静态 proof；真实 RISC-V 编译和测试属于后续 RvPort 阶段。OS、内核、系统调用、驱动和板级迁移不在本 schema 范围内。

## 确定性和扩展

Finding、occurrence、step、edge、break、Diagnostic、context line 和 highlight 的排序由 `schemas/scan-result-v2-vocabulary.json` 冻结。ID 不得包含绝对 checkout 根、时间、随机数、对象地址或遍历顺序。核心对象使用封闭字段；扩展键必须匹配 `org.rvport.kb-scanner.<capability>` 命名空间，禁止重新引入无约束 `trace`。

## 消费端兼容

版本号仍为 2.0，Finding 外层结构不变，但旧严格消费者须同步升级模型及校验器，不能视为完全透明的扩展：

- 接受 `impactStepIds: []`；不再从链中的 classification/assessment 读结论，改读 `conclusion` 与 `summary`。
- 按 `primaryPath` 引用的真实 edge 展示源码链，不按节点 kind 分组去重；同类宏可以出现多次。knowledge 放旁支，不是末尾必经节点。
- source 默认上下各 20 行；接受 256 行/65536 字符硬预算。按 `context.lines[].line` 标行号，按 highlights 标命中，不假设连续行、不重新推算截断列。
- 显示 partial/unknown/ambiguous 的 breaks。单节点或局部 complete 不能解释为已穷尽全部构建与调用路径；静态结果仍需后续编译验证。
- 历史阶段 kind 继续保留在 reader vocabulary。新 producer 不输出这些 kind；不要把旧结果中的阶段步骤冒充源码。

`org.rvport.kb-scanner.source-chain.incoming` 是可选审计扩展，提供折叠关系 ID、原始实体端点和方向；基础渲染仍仅依赖已有 steps/edges/source。

## 双语建议合同

版本号仍为 `2.0`。新 producer 在每个 `finding.conclusion` 中同时输出：

| 字段 | 新报告含义 | 历史报告读取 |
| --- | --- | --- |
| `suggestion` | 非空中文建议；默认 HTML 显示它 | 保留原文，包括历史英文 |
| `suggestion_en` | 非空英文建议，与中文表达同一确定程度 | 可省略，不自动补造翻译或 null |

这两个字段不随 `--locale` 交换。title、reason、证据节点说明、状态码、诊断与日志不在汉化范围。HTML 不增加英文列或语言开关；消费者需要英文时自行读取 `suggestion_en`，历史缺失时按历史原文或缺省 UI 处理。

兼容性有方向：新版 reader 接受旧报告，但旧封闭模型/Schema 会拒绝新增字段。严格消费者应先升级 [Schema](../schemas/scan-result-v2.schema.json) 和 Conclusion 模型，再接入新 producer；

- 通用 reader 只允许省略英文字段；显式 null、空字符串、纯空白、非字符串均不合法。
- 历史往返使用现有 `render_json()` 或 `model_dump(mode="json", exclude_none=True)`，保持省略语义。
- 当前 producer 在发布三个 artifact 前额外校验两字段非空；不能用 reader 的历史宽容规则绕过生产必填要求。失败沿现有 projection failure 处理，不发布半套结果。
- 不用汉字正则拒绝历史报告，也不由 reader 推断两段自然语言是否等价。新生产语言与确定程度由成对模板和人工预期测试保证。

建议跟随已有结论：未知/部分/歧义先补证据；inactive 保留排除条件；hint 先核实线索；非阻断项核查目标适用性；阻断项处理已选中的 x86 依赖；构建选择和测试覆盖缺口分别提示对应工作。所有措辞均保持静态分析边界，不宣称真实编译或测试已执行。

人工冻结文案见 [双语预期](../tests/fixtures/bilingual-suggestions/expected-pairs.json)，差异只允许两个建议字段，见 [差异账本](../tests/fixtures/bilingual-suggestions/report-differential.json)。旧报告及旧账本没有回写，V1、事实、分类/评估、ID、源码链、上下文、summary、diagnostics 和日志均不因本次建议改动变化。
