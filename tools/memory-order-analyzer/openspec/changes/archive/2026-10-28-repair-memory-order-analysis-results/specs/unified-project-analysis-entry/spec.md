## ADDED Requirements

### Requirement: 按被调用协议规范化适配器输入
统一入口 SHALL 在调用每个阶段前按该阶段正式合同规范化身份、排序和引用：AST source requests 按 TU/profile 合同，LLVM binding requests 按 artifact key，R3 members 按 physical TU。系统 MUST 保留 record/TU/artifact 映射与计划分母，不得通过放宽下游校验或丢弃失败成员产生完整结果。

#### Scenario: TU 与 artifact 排序方向不同
- **WHEN** 多个合法成员的 physical TU 排序与 artifact key 排序不同
- **THEN** source、binding、R3 请求分别符合其协议并通过实际 validator，规范化结果不依赖输入枚举顺序

#### Scenario: 身份重复但内容冲突
- **WHEN** 同一阶段身份出现不同 digest、profile 或证据内容
- **THEN** 系统拒绝冲突并报告明确诊断；相同身份及相同内容的幂等重复才能归并，计划记录仍可追溯

### Requirement: 显式选择发布分析依赖
发布分析 SHALL 消费编排器选定并验证的 P3 请求引用；MUST NOT 依赖文件名前缀扫描、最后修改时间或将任意后缀转换为整数来识别语义产物。

#### Scenario: P3 请求与线程入口请求共存
- **WHEN** 同一输出目录存在 `thread-0.json`、`thread-entry.json` 及其他非 P3 文件
- **THEN** 发布分析仅消费当前计划引用的合法 P3 请求，不因 entry 文件产生解析异常

#### Scenario: P3 请求未生成
- **WHEN** 上游线程阶段未产生有效 P3 请求
- **THEN** 发布阶段记录依赖缺失及根因引用，不运行不合法请求，不生成 complete empty

### Requirement: 在阶段执行前区分适用性与依赖完整性
协调器 SHALL 区分证据充分的不适用、依赖受阻、模型不支持和实际执行异常，并保留已完成产物。缺失 members、EffectSummary、source/LLVM 请求或 profile 时 MUST 返回具体原因，不能让无效请求进入下游后再以泛化异常代替根因。

#### Scenario: 下游缺少效果摘要或有效成员
- **WHEN** R3/R2 或对象分析所需证据未生成，或所有输入成员均不具备该阶段要求
- **THEN** 相关阶段为 partial/unknown 并引用上游根因，计划成员保留，不提交空 members 或双空 source/LLVM 成员

#### Scenario: profile 无匹配或多匹配
- **WHEN** C++ thread/RAII profile 根据 standard、vendor、target、DataLayout 和 ABI 得到零个或多个已验证匹配
- **THEN** 两种情况分别记录原因与匹配差异，受影响分析降级，不通过忽略配置维度挑选任意 profile

#### Scenario: 构造不存在与构造不可知
- **WHEN** 可信证据证明没有阶段关注构造，或缺失 AST/IR 导致无法判断构造是否存在
- **THEN** 前者记录带依据的 skipped-not-applicable，后者保留 unknown/frontier，二者均不冒充已执行的完整证明

### Requirement: 保持语言标准与原子策略合同一致
原子阶段 SHALL 对协议接受的 compiler-default、legacy 和 ISO 原子语言标准提供一致的生产、schema 与消费行为。无法确定有效标准时 MUST 保留未知边界，不得默认提升为 C++17。不同标准组的模块与源码事实 SHALL 分组绑定，某组失败不能抹去其他组的有效产物。

#### Scenario: legacy 策略输出
- **WHEN** 合法 legacy 输入产生 `legacy-no-iso-atomics-v1` 策略记录
- **THEN** 输出通过对应版本 schema 并明确缺少 ISO 原子模型，不因枚举不一致异常，也不输出不受支持的正式原子证明

#### Scenario: compiler-default 无可信解析依据
- **WHEN** 输入为 compiler-default 且不存在可验证的有效语言标准
- **THEN** 系统输出可理解的标准未知诊断；只有证据充分证明不适用时才能跳过原子阶段

#### Scenario: 多标准组部分完成
- **WHEN** 一个 Scope 内合法分组中的 C++17 产物有效，而另一 legacy 或 unknown 组无法完成
- **THEN** 有效分组的独立证据保留，项目完整性反映失败组，组间不借用事件或证明

### Requirement: 完整传播并去重分析诊断与边界
统一报告 SHALL 汇总 ingestion、source、适配器和下游的诊断与相关 frontier，保留 code、stage、Scope/TU/record、双语说明建议、根因及审计引用。诊断与 frontier SHALL 保留各自含义；去重不得合并不同配置或不同 TU 的独立问题。任何已知事实提取不完整、优化证据丢失或相关阶段异常 MUST 影响相应完整性。

#### Scenario: 顶层原始 diagnostics 为空
- **WHEN** 内部阶段存在 frontier 或 ingestion diagnostics，而协调器自身没有异常诊断
- **THEN** 最终聚合仍可查看真实问题及影响范围，不能输出“无诊断”掩盖缺口

#### Scenario: 同根因传播到多个阶段
- **WHEN** 一个 Scope/TU 的输入失败被多个阶段引用，同时另一个 Scope 有同 code 的独立失败
- **THEN** 同一根因归并并保留受阻阶段，另一 Scope 的失败保留独立身份，数量和明细一致

#### Scenario: 事实可读但不完整
- **WHEN** BC 已发布且 ModuleFacts 为 partial 或含相关优化证据丢失
- **THEN** ingestion/Scope/项目的相应完整性仍非完整，不能仅凭 artifact 存在将阶段计为完整证据

### Requirement: 修复后的结果策略隔离旧缓存
统一入口 SHALL 将候选准入、诊断传播及投影版本纳入版本化结果策略与缓存身份；MUST NOT 将旧策略的 complete 或 partial 输出作为新策略的有效完成缓存。

#### Scenario: 升级后命中旧结果目录
- **WHEN** 输入 digest 相同但结果策略或投影版本已改变
- **THEN** 系统重建受影响结果并保留旧制品，不把旧错误输出当作新分析的验收结果

#### Scenario: 相同新策略冷暖运行
- **WHEN** 固定输入、版本和预算执行冷缓存与暖缓存分析
- **THEN** 可复用的完整产物语义一致，partial/transient 依旧遵守既有缓存限制
