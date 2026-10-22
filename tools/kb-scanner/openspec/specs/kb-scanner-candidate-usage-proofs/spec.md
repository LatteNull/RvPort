# KB Scanner 候选用途自动证明规范

## Purpose

定义候选事实驱动的局部用途采集、配置隔离、有界使用闭包、自动纯数据证明与保守准入，以及兼容报告和容器质量/资源验收边界。

## Requirements

### Requirement: 用途需求必须复用候选事实与配置身份

Scanner SHALL 从已有 NormalizedFact 与同一知识匹配规则建立候选用途需求，使用与 Detector 一致的 factId、subjectId、configuration 和原始 matchedEvidenceIds。用途分析 MUST NOT 依赖最终 Finding、重复运行管线或另建名称白名单。

#### Scenario: 枚举和宏候选共享语义匹配入口

- **WHEN** identifier 或 enum fact 经既有匹配被识别为候选
- **THEN** 用途需求 SHALL 绑定相同事实根和配置，并保留原 Evidence、Fact 与知识来源
- **AND** 普通不匹配事实不得被当作另一个架构候选，相关使用记录可作为支持证据追加

#### Scenario: 无候选或配置无法唯一确定

- **WHEN** 当前输入无候选，或某候选跨多个未消解配置
- **THEN** 前者 SHALL 跳过无需求查询，后者 SHALL 按配置分开或保持 unknown
- **AND** MUST NOT 借用其他配置的完整用途证明

### Requirement: 自动排除必须来自完整局部纯数据闭包

用途 Analyzer SHALL 建立有界声明绑定、def-use、control 和 escape 闭包。仅当受支持语法、所有相关使用及控制后果均完整，无执行冲突、逃逸、未知操作或截断时，SHALL 生成 `non_execution_data` 的完整证明；无已知 x86 命中 MUST NOT 单独构成证明。

#### Scenario: 局部数据操作完全闭合

- **WHEN** 局部候选常量只经可唯一绑定的标量比较和字面数据写入无逃逸本地固定数组，全部相关使用均已解析
- **THEN** 默认管线 SHALL 自动生成带真实源码来源和闭包统计的完整纯数据用途证明
- **AND** 分类 SHALL 只省略对应候选迁移 Classification，不删除原始 fact 或 Observation

#### Scenario: 局部数据流逃逸

- **WHEN** 候选影响的值或对象经 return、未知调用参数、取址、指针/字段或全局写入逃逸，或涉及重载、volatile/atomic、循环或不支持控制语义
- **THEN** 闭包 SHALL 标记 unknown/partial 并保留具体断点
- **AND** MUST NOT 只凭前一条赋值或比较为完整而生成排除

#### Scenario: 定义与使用的范围不同

- **WHEN** 待判定 fact 是宏定义或枚举声明，而全部可见使用没有闭合，或同 fact 还有其他未证明 occurrence
- **THEN** 定义/聚合 fact SHALL 保持 unknown，即使一个局部使用已证明纯数据
- **AND** 单个使用的证明不得扩展到头文件、跨 TU 或全项目

### Requirement: 数据用途不得覆盖执行依赖和实现未知

Scanner SHALL 分别表达数据用途、执行依赖和目标替代实现。控制闭包中已有 confirmed x86 事实 SHALL 保持原风险；未解析调用 SHALL 保持 unknown，不因 selector 名称或数据来源自动降级，也不由新用途关系独自升级为 blocker。

#### Scenario: Codec 标识选择架构实现

- **WHEN** 数据 ID 的分支包含已确认 intrinsic/asm，或通过普通调用选择未知实现
- **THEN** 前者 SHALL 保留原 confirmed/high/blocker，后者 SHALL 保留待补证据状态
- **AND** 两者均不得仅凭数据 ID、generic 标签或不存在 RISC-V codec 名称作出可移植性结论

#### Scenario: 候选排除后仍缺构建或目标证据

- **WHEN** 候选分类因完整纯数据证明被省略，但目标选择或输入完整性未证明
- **THEN** 项目评估 SHALL 继续保留相应未知维度
- **AND** 排除关系 MUST NOT 被当作目标已选中、替代实现已具备或 ready 的证明

### Requirement: 用途查询必须确定性且受双层资源门禁约束

Scanner SHALL 一次建立索引并按 fact/configuration/scope 缓存有界查询，记录局部和扫描级预算、计数及未完成原因；MUST NOT 对每个 Finding 重扫源码或执行全 root×terminal 搜索。任何裁剪或预算耗尽 SHALL 关闭相应排除资格而保留既有事实。

#### Scenario: 乱序与无关源码增长

- **WHEN** 相同输入改变遍历顺序或增加无关代码
- **THEN** 相关证明 SHALL 保持稳定身份及相同结论，索引构建和查询计数 SHALL 可分别审计
- **AND** 机器绝对路径、对象地址和时间不得进入稳定身份

#### Scenario: 使用链超过预算

- **WHEN** 单根深度/访问或扫描级记录/访问超过设计硬预算
- **THEN** SHALL 输出 partial/unknown、已验证局部来源和截断计数，不设置 scopeComplete
- **AND** 不得以删除困难事实或提高原图预算绕过性能验收

### Requirement: 自动 producer 必须通过独立单元和真实输入验收

所有新增/实质修改自有模块 SHALL 映射隔离单测，在独立容器达到整体与每个受影响模块至少 90% 行/90% 分支覆盖率；统计 SHALL 包含未被加载的 kb_scanner/scripts/tools 源码。真实 parser、CLI、项目扫描和性能测量 MUST NOT 替代单元覆盖。

#### Scenario: 端到端生成与负例

- **WHEN** 默认 scanner 分析纯数据正例、同名遮蔽、未知调用、跨配置、复杂宏和执行混用反例
- **THEN** 正例 SHALL 不经手工注入即生成被消费者接受的证明，反例 SHALL 保留 unknown 或已有执行结论
- **AND** SHALL 记录可复跑命令、单元结果、整体/逐模块覆盖、排除范围及报告路径

#### Scenario: 固定项目与规模验收

- **WHEN** 对固定 libarchive 两轮及 10000/20000 引用稀疏/密集输入执行新旧对照
- **THEN** SHALL 逐项审校候选用途与实际排除，在 2 CPU/2 GiB/无额外 swap 下每个扫描正常完成且少于 300 秒，记录性能、内存、分阶段时间及预算
- **AND** 开关 producer 的相对时间 SHALL 作为新增功能成本诊断而非单独否决条件，旧门槛结果和历史失败 SHALL 保留；通过的开启版本 SHALL 保存为后续同功能回归基线
- **AND** 全部规模组 SHALL 实际执行，缺失工件、候选数错误、未触发用途分析、超预算访问或重复按 Finding 重建索引 MUST NOT 因时间放宽而通过
- **AND** 未消除全部 26 项不代表失败，但无任何真实自动证明正例、错误排除、测试失败或覆盖不足 SHALL 阻止验收完成
