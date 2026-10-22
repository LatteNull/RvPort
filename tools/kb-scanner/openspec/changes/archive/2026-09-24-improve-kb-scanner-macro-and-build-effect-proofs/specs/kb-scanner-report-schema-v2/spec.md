## ADDED Requirements

### Requirement: 宏构建作用链必须展示真实多来源且隔离不同 TU
V2 SHALL 在单个 Finding 的既有 evidenceChain/occurrences 中展示实际构建参数来源、引用/使用点、include、条件、调用/定义、实参与 replacement token，并保留 TU/configuration 区别。每条边 SHALL 有连续可验证的分析来源；primaryPath SHALL 只选择实际连通局部路径，不把多个实参或不同 TU 的路径串成一条执行链。

#### Scenario: 分散参数来源和多层包装
- **WHEN** 一个参数来自两个变量赋值，实际使用后启用经参数传递包装的 intrinsic
- **THEN** Finding SHALL 展示各来源各自的文件/span/context 和真实连接，不伪造拼接 token 的原始行列
- **AND** 所有码型来源 SHALL 默认带上下各 20 行及命中高亮，继续遵守既有行数/字符预算

#### Scenario: 多配置结果相反
- **WHEN** 同一头文件锚点在一个编译使用实例中 selected，在另一个实例中 inactive 或 unknown
- **THEN** V2 SHALL 保留相应分支、来源与状态，不用一个完整 occurrence 掩盖另一个断点
- **AND** 查询预算不足时 SHALL 显式记录裁剪，不能把未展示路径解释为不存在

### Requirement: 宏作用扩展必须保持 V2 核心合同和中英文说明
本轮 SHALL 复用现有源码/build step 与 edge 类型、断点和可选 namespace extensions，不新增核心 required 字段、kind 或 schemaVersion；扩展 provenance SHALL 自包含且有界。新增用户可读说明 SHALL 同时提供中文及英文字段，suggestion/suggestion_en 合同 SHALL 保持。classification/assessment MUST NOT 出现在源码证据链，knowledge SHALL 仍为实际命中的旁支。

#### Scenario: 老消费者与显式 V1
- **WHEN** 默认 V2 或显式 V1 生成 JSON/HTML/log
- **THEN** V2 基本源码链 SHALL 无需后端新接入即可读取，V1 SHALL 不增加 V2 图必填字段，三个 artifact 与原子发布 SHALL 保持
- **AND** 因新证据改变风险/状态的项目 SHALL 有逐项审校记录，不能用兼容名义冻结错误结论或自动改写历史报告

#### Scenario: 原有功能回归
- **WHEN** 运行既有候选用途、函数多版本、架构家族及源码链样例
- **THEN** 不受新证明影响的结论和其他扩展 SHALL 保持；变化 SHALL 区分事实、关系、分类与纯展示并记录依据
- **AND** 不得为减少体积而删除原始事实、缩短正常 20/20 上下文或省略 unknown 原因
