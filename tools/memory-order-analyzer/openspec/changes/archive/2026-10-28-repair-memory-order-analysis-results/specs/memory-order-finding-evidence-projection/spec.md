## ADDED Requirements

### Requirement: 版本化表达证据等级与未评估置信度
系统 SHALL 提供 `MemoryOrderFindingProjection 3.0`，在 conclusion 中明确 `evidenceLevel` 为 source-only、incomplete 或 bounded-model，并允许未评估 confidence 为 null。源码候选 MUST 使用提示级严重性、非阻断状态和未知/部分结论；不得使用固定 0.5 或其他数值充当未评估概率。正式风险严重性 SHALL 来源于实际评估。

#### Scenario: 源码候选投影
- **WHEN** 一个已准入候选仅具备源码证据
- **THEN** 新投影为 source-only、severity=info、confidence=null、blocking=false、unknown/partial，verdict 不得为 risk/discharged

#### Scenario: 完整受限模型结果
- **WHEN** 原分析产物支持正式风险或受限消解
- **THEN** 保留实际结论及模型边界，只有存在可解释评估依据时才填数值 confidence，不能以 1.0 表达全程序安全

### Requirement: 生成具体双语说明而非枚举占位
每个对外候选 SHALL 包含可理解的中英文标题、原因、详情和建议，解释已观察形状、相关性依据及不能得出正式结论的原因。MUST NOT 仅用 `source-candidate`、内部 ID 或泛化模板替代业务解释，也不得推断未观察的线程或同步事实。

#### Scenario: 观察到原子与控制关系但无 IR
- **WHEN** 候选有可回溯原子/控制源码形状而 IR 或线程证明缺失
- **THEN** 文案指出所观察操作和适用证据缺口，建议补证/复核；不能直接建议修改确定的错误内存序

#### Scenario: 缺少符号或完整位置
- **WHEN** 可信证据没有符号名或完整源码范围
- **THEN** 文案明确未知且引用可用事实，不伪造名称和代码位置

### Requirement: 新旧投影与结果策略显式兼容
本工具生产者 SHALL 在统一报告中声明实际 finding schema 版本，本工具 validator SHALL 明确区分 2.0、3.0 和不支持版本。3.0 的语义与缓存身份 MUST 不复用 2.0 的固定等级/置信度假设；历史原始制品 MUST 保持不可变。外部消费者的展示适配不属于本规格的实施范围。

#### Scenario: 读取旧版 medium 和 0.5 源码候选
- **WHEN** 合法 2.0 候选包含 medium/0.5，fact.kind 或 conclusion.verdict 表明它是源码候选
- **THEN** 本工具校验器仍接受该历史格式并保留原字段，不写回旧制品；新生成的 3.0 候选仍使用 info/null，不能继承旧固定数值

#### Scenario: 未知投影版本
- **WHEN** 输入声明未支持的投影版本或版本与字段合同不一致
- **THEN** 本工具校验器显式报告不兼容，不能按 2.0/3.0 静默猜测完整结论

### Requirement: 主路径与断点在无序存储下保持独立含义
本工具投影 SHALL 维持 steps 的稳定存储排序与 primaryPath 的逻辑排序，提供关系闭合的 edges、breaks 和截断状态，使 ID 引用能够表达真实主路径及相关分支。本工具 MUST NOT 把 steps 数组顺序当推理顺序；页面渲染由外部项目负责。

#### Scenario: 结论 ID 排在事实 ID 之前
- **WHEN** steps 的稳定排序先存放 conclusion，而 primaryPath 先引用 source-fact
- **THEN** 投影校验确认 primaryPath 为事实到结论，引用与步骤身份一致，不因 steps 数组位置改写主路径

#### Scenario: 缺口没有直接源码
- **WHEN** break 指向推理阶段或全局证据缺失且没有源码位置
- **THEN** break 保留原因、期望证据及建议，不复制其他 occurrence 的位置或删除该缺口
