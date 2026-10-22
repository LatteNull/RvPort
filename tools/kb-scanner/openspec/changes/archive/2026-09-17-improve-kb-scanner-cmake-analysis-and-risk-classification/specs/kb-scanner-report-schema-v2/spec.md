## ADDED Requirements

### Requirement: 风险投影必须保留不确定性而不修改结果结构
V2 SHALL 使用统一内部决策投影 severity、status、actionable、blocking 与 archReachability，不再仅按 impact 将 actionable_non_blocking 固定映射 medium 或把 unknown 兜底为 low/complete。高风险且上游部分缺失 SHALL 可以 actionable=true、blocking=false、status=partial/unknown。SchemaVersion 2.0、既有核心字段/枚举、默认 V2/显式 V1 和三个 artifact SHALL 保持；V1 SHALL 从同一内部风险策略适配既有字段，V2 MUST NOT 依赖 V1 payload。

#### Scenario: 局部依赖高风险但目标未知
- **WHEN** Classification 确认局部 x86 依赖但目标适用性未闭合
- **THEN** V2 SHALL 输出 high、partial/unknown、actionable=true、blocking=false，并用已有 reason/chain break 表达缺口
- **AND** 双语建议 SHALL 区分依赖已确认和目标适用性待核查，不声称已验证阻断

#### Scenario: 未决候选和未知枚举值兜底
- **WHEN** 候选分类未决或生产映射无法识别内部风险决策
- **THEN** 未决候选 SHALL 输出 medium 待核查与未知状态；无效内部决策 SHALL 产生明确诊断或按既有发布边界拒绝
- **AND** MUST NOT 静默以 low/complete 发布无依据的结论

### Requirement: CMake 证据链必须显示真实上游且保持兼容
V2 SHALL 使用现有 source/build step、edge、上下文和命名空间 extensions 表达 CMake 条件、变量、目标、源码和参数作用，不新增核心必填字段或 kind；代码节点 SHALL 有自己的 span、高亮和默认上下各 20 行。配置拒绝 SHALL 展示条件到实际 fatal 的链；后续声明不得拼造为该次配置 selected。classification/assessment MUST NOT 回到 evidenceChain。

#### Scenario: 展开 CMake 参数驱动的命中
- **WHEN** 参数到 target/source、条件宏和 intrinsic 关系完整
- **THEN** 单个 Finding SHALL 自包含展示真实连通链与知识旁支
- **AND** 关系不完整时 SHALL 保留可验证局部链及明确断点，不按节点种类拼接

#### Scenario: 固定首次扫描审校
- **WHEN** 对 demo-test1 首次源码版本执行新旧审校及 V1/V2/HTML/log 合同测试
- **THEN** SHALL 逐项记录原 19 项及新增 CMake 事实的风险/状态/依据变化，而非要求全部为 high/blocking
- **AND** 两份 compiler JSON 哈希、既有字段合同、静态范围及中文/英文建议合同 SHALL 保持，历史数据不得自动改写
