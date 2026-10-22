## Context

当前生产默认 Schema V2，显式 V1 仍可用。`projection/v2/mapper.py` 直接在 `Conclusion` 中选择两个英文 suggestion 模板；`projector.py` 没有向该选择过程传入 locale。V1 的 `projection/policy.py` 已分别提供中文 suggestion 与英文 suggestion_en，不能为复用文案让 V2 回退读取 V1。

V2 `Conclusion` 和 JSON Schema 为封闭对象，目前不接受 suggestion_en。HTML renderer 直接展示 conclusion.suggestion；分类 reason 是上游机器理由，参与分析身份与审计，不能借翻译建议去改分类器。前一个源码链 change 已建立 128 个自有源码文件的整体单元覆盖统计，最新验证为 97.82% 行/93.36% 分支；实施时仍须重新运行，不能把历史数字当本 change 验收。

## Goals / Non-Goals

**Goals:**

- 当前 producer 每个 V2 Finding 同时输出中文 suggestion 与英文 suggestion_en，并保持语义一致。
- 建议与已有结论相符：无法判断先补证据，已排除路径保留保护，已确认依赖或缺口才建议相应迁移工作。
- 保持新 reader 能读取历史 V2，HTML 默认中文，提供完整机器合同、差异回归与单元覆盖门禁。

**Non-Goals:**

- 不翻译 title、reason、evidenceChain step 文案、机器状态/原因码、诊断或日志；不是完整报告国际化。
- 不改变 Classifier/Assessor、schemaVersion、Finding 身份、证据链、±20 行上下文或现有 V1 输出。
- 不调整后端/前端、数据库、Compose 或生产容器；不使用在线翻译、大模型运行时翻译或新增本机依赖。
- 不执行项目 Make、compiler 或 tests，不涉及 OS 迁移；uname 正确选择目标架构的分析假设不变。

## Decisions

### 1. 成对模板位于 V2 展示层，不修改分析输入

新增纯展示模块 `kb_scanner/projection/v2/suggestions.py`，以同一个建议键返回不可变的中文/英文文案对。mapper 使用已计算的 conclusion status、classification impact、findingType 及必要的既有结构化上下文选键，不重新求值构建、宏或可达性，也不通过英文字符串全文匹配选择模板。每个 Finding 的选择为有界常数级操作，无额外图查询、文件读取或网络调用。

不分别维护两套 if/else，避免语言分支漂移；不复制 V1 Presentation 进入 V2，保留现有管线隔离；不引入 gettext 或通用 i18n 框架，因为本次是两个固定输出字段，而非全站语言协商。语言字段不由 `--locale` 重命名或交换：无论现有 locale 传何值，新 producer 都输出 suggestion=中文、suggestion_en=英文；不改变该参数的其他行为。

### 2. 用已有结论决定措辞，保守优先

首先处理 conclusion.status 为 unknown/partial/ambiguous 或 impact 为 unknown，再处理 inactive/guarded_inactive、hint、确定阻断与非阻断分类。规则消费的是已经输出的结论，不根据局部 chain.status 单独重新归类：例如已确认局部 x86 事实但上游构建未知，应说明“核查是否被目标选择”，不能断言必然阻断，也不能抹去已确认的局部事实。

| 已有结果/建议类别 | 中文建议表达重点 | 英文建议表达重点 |
| --- | --- | --- |
| unknown / partial / ambiguous | 当前证据不足；保留事实，补齐选择、定义或上下游证据后判断，不直接要求替换 | Evidence is insufficient; preserve the fact and resolve missing or ambiguous evidence before deciding on replacement |
| inactive / guarded_inactive | 当前静态证据表明路径已排除；保留条件保护，配置变化时复核，不宣称项目已就绪 | The path is statically excluded; preserve its guards and reassess after configuration changes |
| hint / comment | 仅作线索，结合实际源码与选择路径核实 | Treat this as a hint and check actual source and selection evidence |
| blocking_issue 且 complete | 根据证据链处理已选中的 x86 依赖，补充 RISC-V 或通用实现，核查静态选择路径 | Address the selected x86 dependency with a RISC-V or portable implementation and review static selection |
| 已确认局部/其他 actionable_non_blocking | 核查该依赖的目标适用性，按需补充目标或通用路径，不写成确定阻断 | Check target applicability and add a suitable implementation or path where required |
| 已有 missing_riscv_selection_path / riscv_test_coverage_gap | 分别核查目标选择分支或测试资产/选择路径，不用“替换 intrinsic”套用所有缺口 | Review the missing target-selection or test-coverage path, without claiming tests have executed |

候选数据格式名称只能作为已有事实描述，不能仅凭候选类型就把任意 unknown 都称作 codec 数据。两种语言必须表达相同的已知程度与操作建议；可保留 RISC-V、宏名等技术标识。缺失 observation 或新增未映射 findingType 使用保守双语兜底，不能抛弃 Finding、退回仅英文或产生新分析结论。模板最终逐字内容在实施单测的人工预期中冻结，上表冻结语义和选择优先级。

### 3. 同一核心对象可选读取、生产必填

V2 Conclusion 新增同级 suggestion_en，不放进 extension，不增加顶层结果文件。Schema 的 properties 声明该字段为非空字符串，但不加入通用 reader 的 required；历史省略字段仍可读取。新 producer 显式传入两段非空文案；通过专用 producer 检查或生成边界校验禁止遗漏英文，不能仅靠“reader 校验通过”验收。

模型允许内部缺省值表示历史缺失，历史序列化按既有 exclude_none 行为省略该字段，不把缺失补成空字符串、null 或机器翻译。对于显式提供的 suggestion_en，null、空字符串、纯空白或非字符串均判为无效；Schema 和模型必须对显式输入保持一致。现有 suggestion 的历史合法内容（包括英文旧报告）继续接受，中文要求只施加于新 producer，不能以汉字正则拒绝历史报告。两语言语义由有限模板与定向单测验证，通用 reader 不尝试推断自然语言等价性。

若采用独立 producer 验证入口，须与通用 reader 校验分开，并在正常 artifact 发布之前执行；错误沿现有 projection failure 处理，不发布半套结果。三份 artifact 名称、JSON 确定性序列化、HTML UTF-8 与转义均不变；新 HTML 只显示中文建议，不新增英文列或切换按钮，历史 HTML 仍可显示历史 suggestion 原文。

### 4. 兼容边界与变更账本

新版 reader 可读取旧报告，但旧封闭 Schema 会拒绝新字段，因此迁移文档必须要求严格消费者先升级模型/Schema。保留 schemaVersion 2.0 是本次用户明确选择的增量合同，不声称所有旧消费者无须升级。

同一 snapshots 新旧投影逐字段对照：V2 JSON 唯一允许变化为 conclusion.suggestion 和新增 conclusion.suggestion_en；Finding/occurrence/step/edge ID、fact、conclusion 其余字段、链/预算、summary/diagnostics 均应相等。HTML 仅建议文案相应变化，scan.log 不变；V1 全字段/规范化哈希不变。旧报告样例原样保留做兼容测试，另建或明确标注新双语样例；完整报告哈希变化须有剔除上述字段后的相等证明，不盲目更新既有 golden。

GCC/Clang JSON 不提供展示翻译源、不参与重写，其字节、哈希、分类、知识 entry/source ID 与 provenance 全部不变。

### 5. 模块与独立测试映射

| 模块 | 隔离测试与边界 |
| --- | --- |
| 新 suggestions.py | 新 test_suggestions.py：全部模板、状态优先级、未知类型/缺 observation、成对语言非空且人工语义预期；不调用解析器或 pipeline |
| mapper.py | 扩展 test_finding_mapper.py：fake index、chain builder、source projector，核验双字段和其他 conclusion 字段不变 |
| models.py | 扩展 test_models.py：新字段、历史缺失、显式 null/空白/错误类型、额外字段拒绝与往返序列化 |
| projector.py / validation.py（若接入 producer 检查） | 对应 projector/reference-validator 独立套件：fake mapper、publisher 与上下文边界，验证生产遗漏拒绝但历史 reader 接受 |
| renderers.py（直接复用也需验证） | test_renderers.py：直接构造新/旧报告，检查 UTF-8 中文、默认字段选择、HTML 转义及 JSON 双语/历史缺省；仅在必要时修改业务代码 |

实际新增或实质修改的其他业务模块同样必须登记；不能仅在组件测试中间接调用就计为单元覆盖。复用现有容器及整体覆盖入口 `tests/run_source_chain_unit_tests.py --output /out`，扩充机器可读受影响模块 inventory，保留既有统计范围 `kb_scanner/`、`scripts/`、`tools/` 并纳入未加载源码。整体及本次每个受影响模块必须达到 90% 行/90% 分支；无分支指标明确记为不可用。排除仅限测试/fixture/测试辅助代码、非运行归档快照、非可执行知识数据和容器第三方依赖，不排除仍在包中的 Legacy 业务逻辑。

Schema validator 等真实第三方验证作为合同/组件层补充，不能抵充单测覆盖；单元层 fake 原生解析、文件/发布、外部进程和跨阶段边界。新增/修改业务模块的覆盖门槛须进入默认容器测试自动化，不只人工读取报告。报告记录命令、测试数量、整体/逐模块覆盖、统计分母和持久路径；不足时保持任务未完成，若需扩大到无关历史模块则请求授权。

## Risks / Trade-offs

- [旧严格消费者拒绝新字段] → 文档声明升级顺序，新旧 reader/producer 合同分开测试，不在本 change 修改后端。
- [中文翻译改变风险程度] → 同键双语成对人工预期，冻结未知、inactive、hint 和软依赖等非阻断语义，不修改 classification。
- [任意未知候选被称为 codec] → 默认用通用不足证据文案，只有明确已有语义才能使用更具体措辞。
- [历史样例被中文校验拒绝] → reader 不强制建议语言；生产完整性检查与 reader 分离，禁止自动回写旧样例。
- [新字段带来报告哈希变化] → 差异仅允许两个建议字段；独立验证其余全部报告字段、V1 与知识哈希不变。
- [测试门槛被既有 80% 分支门禁稀释] → 本次复用整体 90/90 gate 并登记全部 affected modules；历史门禁只能补充，不能代替本次标准。

## Migration Plan

1. 在独立测试容器冻结固定输入的新旧 V2、V1、知识哈希及单元覆盖基线；保留历史样例，不安装本机依赖。
2. 原子交付成对模板、mapper、模型/Schema 与 producer 检查，补齐各模块隔离单测及新旧 reader 合同。
3. 验证中文 HTML、JSON 双语、状态语义与差异账本；运行整体/逐模块覆盖和完整回归，更新消费者迁移记录。
4. 向用户交付 apply 结果，后续 sync/archive、commit/push 与部署由用户单独授权。消费者接入需先更新严格 Schema/模型，但不在本次执行。
5. 如需回退，按另行批准的 Git 回退流程整体回退该展示与合同变更；不自动 reset、不回写历史 artifact、不恢复 Legacy 路径。

## Open Questions

无待用户决定的语言或范围选项。固定双语字段、建议级汉化、历史缺省兼容均已确认；producer 检查具体放置位置在实施时按最小模块改动确定，但不得省略运行时生成约束与对应隔离测试。
