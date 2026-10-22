## ADDED Requirements

### Requirement: V2 新生成结果必须包含成对的中文和英文建议
V2 Projector SHALL 在每个新生成 Finding 的 conclusion 中输出非空中文 `suggestion` 和同级非空英文 `suggestion_en`，两者 SHALL 表达同一建议及相同的证据确定程度。语言字段含义 MUST NOT 随 locale 交换或只输出其中一种语言；建议 SHALL 在展示层由确定性成对模板生成，不调用网络翻译、V1 mapper 或重新执行分析。

#### Scenario: 默认与非默认 locale 均输出固定语言字段
- **WHEN** 同一 snapshots 分别通过默认 locale、en-US 或其他现有可接受 locale 生成 V2 报告
- **THEN** 每个 conclusion SHALL 同时包含中文 suggestion 与英文 suggestion_en，两字段的文案选择 SHALL 一致
- **AND** status、findingType、ID、reason、源码符号和其他机器字段 MUST NOT 因建议语言发生变化

#### Scenario: 新生产结果遗漏英文建议
- **WHEN** 生产映射遗漏 suggestion_en，或任一新建议为空白
- **THEN** 生产边界 SHALL 拒绝发布该无效报告并沿既有错误处理返回失败
- **AND** reader 允许历史省略字段的规则 MUST NOT 被用来接受该新生产缺陷

### Requirement: 双语建议必须服从已有结论并保持静态边界
建议策略 SHALL 使用已有 classification impact、conclusion status 和 findingType 选择措辞，unknown/partial/ambiguous SHALL 优先给出补证据建议，inactive SHALL 保留排除条件，hint SHALL 提醒核实事实，已确认依赖或缺口 SHALL 给出相应迁移建议。策略 MUST NOT 改变分析结论、把候选升级为确定依赖、把非阻断项称为确定阻断，或声明真实编译/测试已执行。

#### Scenario: 证据不足或者存在歧义
- **WHEN** 结论为 unknown、partial 或 ambiguous，包括非 candidate 状态但证据仍不足的项目
- **THEN** 两种建议 SHALL 要求保留事实并补齐证据后再判断，不直接断言必须替换实现
- **AND** 文案 MUST NOT 把所有未知项默认称为 codec 或数据格式名称

#### Scenario: 路径已被排除
- **WHEN** 已有结论为 inactive 或 guarded_inactive
- **THEN** 双语建议 SHALL 说明当前路径由静态证据排除、保留相关条件并在配置变化时复核
- **AND** 建议 MUST NOT 要求无条件替换该路径，也 MUST NOT 声称项目整体已就绪

#### Scenario: 提示和非阻断局部依赖
- **WHEN** Finding 为 hint 或已确认局部但未证明目标必选的 actionable_non_blocking
- **THEN** 建议 SHALL 分别要求结合源码核实线索或核查目标适用性，按需处理依赖
- **AND** 两种语言 SHALL 均不声称已确定阻断或已完成目标编译

#### Scenario: 已确认依赖和迁移缺口
- **WHEN** 完整结论为 blocking_issue，或已有 findingType 表示目标选择/测试覆盖缺口
- **THEN** 建议 SHALL 分别指向处理已选中的 x86 依赖、核查目标选择分支或测试资产/选择路径
- **AND** 测试覆盖建议 MUST NOT 声称测试已经运行或通过

#### Scenario: 缺失 observation 或未知 findingType
- **WHEN** 可投影 Finding 缺少 observation 或其 findingType 不在已知模板特例中
- **THEN** 策略 SHALL 根据已有结论采用保守、非空的双语兜底
- **AND** 它 MUST NOT 丢弃 Finding、伪造新分析结论或回退到仅英文模板

### Requirement: 双语建议合同必须区分历史读取与当前生产
V2 SHALL 保持 schemaVersion 2.0，并在 Conclusion 模型和 JSON Schema properties 声明 suggestion_en 为可省略的非空英文建议字段；通用 reader SHALL 接受历史缺失，但显式 null、空白或非字符串 SHALL 被拒绝。新 producer SHALL 始终填充双语字段。迁移文档 SHALL 明确旧封闭 Schema 对新增字段的不兼容，不得声称旧严格消费者无需升级。

#### Scenario: 历史报告只有 suggestion
- **WHEN** 更新后的 reader 读取合法旧 V2 报告，suggestion 仍为英文且缺少 suggestion_en
- **THEN** 读取 SHALL 成功，原文和字段缺失语义 SHALL 保持，往返序列化不添加伪造英文或 null
- **AND** 新 producer 的中文要求 MUST NOT 被用于拒绝合法历史英文建议

#### Scenario: 新字段类型或内容不合法
- **WHEN** suggestion_en 被显式设置为 null、空字符串、纯空白或非字符串
- **THEN** 更新后的模型和 Schema 合同 SHALL 一致拒绝该输入
- **AND** 合法历史省略字段与显式非法值 SHALL 被区分

#### Scenario: 旧严格消费者接收新结果
- **WHEN** 消费者仍使用不含 suggestion_en 且 additionalProperties=false 的旧 V2 conclusion Schema
- **THEN** 迁移记录 SHALL 明确要求先升级 Schema/模型
- **AND** 本 change MUST NOT 自动修改后端、前端或持久化结果以绕过该边界

### Requirement: 建议汉化必须保持现有报告其余内容与默认中文展示
同一 snapshots 的新旧 V2 JSON SHALL 仅允许 conclusion.suggestion 文案变化和新增 conclusion.suggestion_en，其他结论字段、ID、facts、occurrences、evidenceChain、summary 和 diagnostics MUST 保持不变。HTML SHALL 默认展示 suggestion 的中文内容并继续安全转义；显式 V1、scan.log、三个 artifact 名称及 GCC/Clang 事实数据 MUST 保持现有合同。

#### Scenario: JSON 与 HTML 建议一致
- **WHEN** 新 V2 结果输出 JSON 和 HTML，建议中含中文、技术标识或 HTML 特殊字符
- **THEN** JSON SHALL 保留语义一致的双语字段，HTML SHALL 正确显示中文 suggestion 并安全转义
- **AND** HTML MUST NOT 用 suggestion_en 替换默认建议，也不要求新增英文列或语言切换 UI

#### Scenario: 对比双语修订前后报告
- **WHEN** 固定 snapshots 或固定输入完成双语修订前后对照
- **THEN** 仅移除允许变化的两个建议字段后，V2 报告 SHALL 全字段相等，V1 与知识哈希 SHALL 不变
- **AND** 回归账本 SHALL 记录允许的文案/字段变化，不能自动重写无法解释的 golden 或修改原始源码

### Requirement: 双语建议必须通过独立单元覆盖与兼容合同验收
每个新增/实质修改的建议策略、mapper、model、producer validator/projector 或 renderer 业务模块 SHALL 登记隔离 unit suite，覆盖正常、边界和异常路径，并在独立 kb-scanner-test 容器达到项目整体及每个受影响模块至少 90% 行/90% 分支覆盖率。统计 SHALL 包含未加载的 kb_scanner/scripts/tools 自有可执行源码，排除项必须有明确理由，合同/组件测试 MUST NOT 替代隔离单元覆盖。

#### Scenario: 执行建议模块门禁
- **WHEN** 容器运行默认自动化与本 change 的受影响模块单元门禁
- **THEN** 全部语言对、优先级、兜底、新 producer 必填和历史 reader 缺省反例 SHALL 有有效断言且满足覆盖门槛
- **AND** 未加载源码 SHALL 纳入分母，真实 parser/pipeline 组件结果 MUST NOT 被计为隔离单元数字

#### Scenario: 验收合同与差异回归
- **WHEN** 执行新旧 V2、中文 HTML、V1、AVX/enum/RPM/候选及既有完整回归
- **THEN** 结果 SHALL 有可复跑命令、测试记录、整体/逐模块覆盖、统计范围和持久报告路径
- **AND** 验证失败或覆盖不足 SHALL 保持任务未完成；所有测试 MUST NOT 安装本机依赖、执行被扫描项目命令或更新生产容器

## MODIFIED Requirements

### Requirement: Unknown candidate 必须在结论和链路中一致表达
V2 SHALL 对所有未决 candidate（包括 identifier 与 enum）一致表达 unknown completeness/conclusion/chain，并以语义一致的中文 suggestion 与英文 suggestion_en 提示当前无法确定执行架构依赖，可由后续分析补齐。schemaVersion 与 V1 合同 SHALL 保持不变；suggestion_en SHALL 依本 capability 的双语合同作为历史读取可省略、当前生产必填的字段。

#### Scenario: codec 名称只有候选证据
- **WHEN** Classifier 对 identifier candidate 返回 unknown
- **THEN** V2 conclusion 与 chain SHALL 保持 unknown，且 suggestion 与 suggestion_en MUST NOT 宣称已确认需要替换实现
- **AND** fact、occurrence、上下文和知识来源 SHALL 保留
