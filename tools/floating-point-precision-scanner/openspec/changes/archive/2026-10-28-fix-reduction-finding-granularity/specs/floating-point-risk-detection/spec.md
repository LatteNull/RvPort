## MODIFIED Requirements

### Requirement: reduction reassociation 必须结合递推形态和实际 lowering
`reduction-reassociation` SHALL 从 AST facts 识别浮点 sum、product、dot-product、并行/向量归约与受支持补偿算法，并在可用时通过 source-preserving/build-faithful IR 验证 phi recurrence、vector reduction、reassociation flags 和实际顺序。仅有归约形态但缺少敏感度或 lowering 差异时最多产生 heuristic finding；IR/profile/option 证明一端重结合或向量化且另一端语义不同 MAY 提升证据强度。单元素、固定无重排小表达式或已验证补偿算法 MUST NOT 被当作普通未补偿归约命中。

规则 SHALL 按独立循环中的独立归约候选分别评估，使用当前候选直接事实及有可靠关联的 IR、binding、profile/build context。不同循环、不同函数或同一循环的独立累加器 MUST NOT 因属于同一 TU、使用相同变量名称或命中相同规则而合并。每个候选的 unknown、failed、补偿判断和置信度 MUST 与其他候选隔离。归约规则版本 SHALL 提升至 1.1，并保留稳定 rule code。

#### Scenario: build-faithful IR 发生向量归约
- **WHEN** AST 证明浮点累加，verified evidence 将当前候选绑定到带重结合语义的向量归约，且 source/target policy 不同
- **THEN** 扫描器发布仅引用该候选 AST recurrence、关联 IR group、flags 和必要 profiles 的 finding，并建议病态输入和跨平台顺序测试

#### Scenario: 只有 AST 求和循环
- **WHEN** 可识别长浮点求和但没有可靠 build-faithful IR 或输入敏感度证明
- **THEN** 规则仅发布需要人工确认的 heuristic finding，或按配置保留候选 assessment，不宣称已发生重排

#### Scenario: Kahan 补偿求和
- **WHEN** AST/IR facts 完整证明受支持的 Kahan 更新关系且没有证据显示优化破坏补偿步骤
- **THEN** 普通归约风险为 `not_matched`；若 fast-math 可能破坏关系，由相应优化证据单独评估
- **AND** 其他候选的 IR 或 flags 不得被用于认定该补偿失效

#### Scenario: 循环递推歧义
- **WHEN** 多个 phi/update 候选无法由 evidence 唯一绑定到 accumulator
- **THEN** 受影响候选的 assessment 为 `unknown`，不任选递推链发布 finding，其他可确定候选继续独立评估

#### Scenario: 同一函数的相邻循环复用累加器
- **WHEN** 向量通道累加循环与尾部元素累加循环分别存在归约风险，且更新同一个 `result`
- **THEN** 扫描器发布两个不同 scope、assessment 和 Finding，各自位置与证据只对应所属候选

#### Scenario: 跨函数与同循环多累加器
- **WHEN** 同一 TU 不同函数存在归约，或同一循环存在两个独立累加器
- **THEN** 每个独立候选分别判断并生成适用结果，不按 TU、函数或循环整体强制合并

#### Scenario: 无关 IR 不提高置信度
- **WHEN** 一个候选具有经验证的重结合 IR 和必要语义差异，另一个候选只有 AST 顺序敏感形态
- **THEN** 前者独立评估其证据强度，后者保持 heuristic 和人工确认，不引用前者的 IR 或 binding

## ADDED Requirements

### Requirement: 归约候选必须具有可追溯的独立身份
扫描器 SHALL 从规范化 TU/编译上下文、函数身份、最近所属循环、更新表达式及可证明的递推关系建立稳定候选身份。MUST NOT 以相同行号、变量名或循环种类推断候选等价。完全相同的事实 SHALL 去重；同一递推的多份证据 SHALL 归于同一候选，不能作为多个独立风险重复发布。身份归属无法安全证明时 SHALL 保留局部 unknown，不伪造循环、范围或变量关系。

#### Scenario: 嵌套循环和同一行更新
- **WHEN** 嵌套循环中存在独立归约，或不同更新位于同一行但不同列/宏展开范围
- **THEN** 候选使用直接所属循环及表达式/声明身份区分，不能合并到外层循环或同一行

#### Scenario: 同一候选多证据
- **WHEN** 一个已证明的归约候选有重复 AST 事实、多个关联 IR 事实或来源位置
- **THEN** 重复事实去重，仅生成一个候选 assessment 和适用 Finding，同时保留有界且可追溯的必要证据

#### Scenario: 定位未知但语义明确
- **WHEN** 候选递推身份和风险可证明，但部分展示位置不可恢复
- **THEN** 保留该候选独立判断并沿用未知位置协议，不填造坐标，不因该位置未知影响其他候选

#### Scenario: 身份归属不可证明
- **WHEN** 当前事实无法安全确定候选所属递推或循环
- **THEN** 使用稳定直接事实身份记录该范围的 unknown 及双语原因，不合并其他候选以消除歧义
