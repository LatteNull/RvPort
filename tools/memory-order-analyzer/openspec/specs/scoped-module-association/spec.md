# scoped-module-association

## Purpose

规范显式目标范围内的直接符号关联、兼容性与 lineage 校验，保留未解析引用和输入模块来源，不自动推断完整程序或并发语义。

## Requirements

### Requirement: Associate modules only within an explicit scope

系统 SHALL 接受带版本、目标 ID、成员 ArtifactKey、成员来源、封闭性声明和外部边界的 scope manifest；SHALL 不从编译数据库、共用头文件或目录自动推导完整程序范围。缺少范围时 SHALL 保留分模块事实及 scope unknown，不宣称跨 TU 解析完整。

#### Scenario: Only compilation commands are supplied

- **WHEN** 输入只有源码、编译数据库及生成 BC，没有目标 scope
- **THEN** 可以完成逐 TU 事实采集，但 scope_status 为 unknown，不把全部 BC 默认归为一个可执行程序

#### Scenario: Two executable targets contain the same symbol

- **WHEN** 两个不同显式 scope 分别包含同名函数/全局
- **THEN** 在各自 scope 内解析，不形成跨目标调用或共享对象关系

### Requirement: Resolve direct references without inventing aliases

系统 SHALL 在范围内解析无覆盖歧义的唯一强函数/全局定义和直接引用，使用实际链接符号区分 C++ 重载，内部符号包含模块身份；extern 声明 SHALL 关联已有定义而非创建额外存储。间接调用、未知指针、weak/COMDAT/ifunc/动态绑定和未支持的归档规则 SHALL 保留候选/未知与原因，不猜唯一目标或空影响。

#### Scenario: Resolve a direct call across physical source files

- **WHEN** 两个物理 TU 在同一已声明 scope 内，调用点引用另一 TU 的唯一强定义
- **THEN** 索引输出带调用位置、定义模块和范围证据的绑定边，而不要求先 llvm-link

#### Scenario: Internal symbols share a name

- **WHEN** 两个 TU 各有同名 static 函数或全局
- **THEN** 保留不同内部身份，不跨模块合并

#### Scenario: An indirect call has no implemented resolver

- **WHEN** 调用目标来自函数指针或虚调用且当前后端未解析
- **THEN** 输出 indirect/unknown 及影响完整性的原因，不将它当作无调用或任意选定函数

### Requirement: Link only compatible selected modules and retain lineage

显式 link 操作 SHALL 检查目标范围、triple/layout、关键配置兼容性、重复强定义和成员 lineage，再调用锁定的 llvm-link 并验证输出；SHALL 不把原生库选择当作已完成，也不把链接成功等同于完整程序。相同来源的 object 与 linked 产物 MUST 不在同一语义范围重复计数。

#### Scenario: Scope contains incompatible target modules

- **WHEN** 请求链接的成员混入不同 triple/layout 或同源码互斥构建变体
- **THEN** 拒绝链接并列出冲突，不修改模块 triple 绕过检查

#### Scenario: Linked and original modules overlap

- **WHEN** 一个 scope 同时包含 linked BC 及其 lineage 中的 object BC
- **THEN** 显式拒绝重复成员或要求选择表示，不重复导出同一来源的访问

### Requirement: Expose the limited association stage

索引 SHALL 声明本阶段只提供符号/直接引用关联，尚未执行 points-to、函数效果传播、线程或内存模型分析；缓存 scope 索引 SHALL 依赖成员内容、范围声明和索引版本。

#### Scenario: Target membership changes without BC changes

- **WHEN** BC 内容不变但 scope 成员或边界声明改变
- **THEN** 重建 scope 身份及索引，不必无条件重编译 TU，也不复用旧范围绑定

#### Scenario: A resolved callee writes a global

- **WHEN** 已解析的被调用函数含全局写事件
- **THEN** 输出调用绑定和函数内事实，但不宣称调用者必然执行该写，更不自动生成数据竞争结论

### Requirement: Revalidate direct-call eligibility in a separate derived layer

P2 SHALL 在不改变 ScopeIndex v1 原始绑定/unknown/capabilities 语义的独立派生层，复用显式 scope 校验并复核直接调用的函数/参数/返回类型、calling convention、ABI 支持、精确 linkage、可替换性和边界证据。SHALL 拒绝配置/target/layout/lineage 冲突及跨 profile 混合；符号名唯一或 opaque pointer 类型相同不得替代接口证明。

#### Scenario: A raw unique binding has an incompatible interface

- **WHEN** P1 根据符号唯一建立绑定，但调用点和定义的 calling convention、参数/返回或 ABI 规则不匹配
- **THEN** 保留原始 index，在 P2 记录不合格采用边及 unknown 效果，不执行确定实参替换

#### Scenario: The scope mixes profiles or repeated lineage

- **WHEN** 请求混入互斥 source-preserving/build-faithful 配置，或 linked 产物及其 object 祖先
- **THEN** 拒绝联合效果分析并列明冲突，不混合路径或重复计数；不通过改 triple/layout 绕过检查

### Requirement: Adopt restricted ODR bodies without claiming linker resolution

P2 SHALL 只在版本化规则允许时生成 odr-body-under-contract 边：调用直接指向本 TU 可见 linkonce_odr 定义，非 interposable 且有 dso_local 依据，scope 已声明封闭，COMDAT selection 属于已支持的 any 子集，接口/局部语义可解释，无冲突强定义且可见同名副本经保守规范化结构/接口指纹检查兼容。SHALL 记录采用体、LLVM 查询、检查结果及 ODR 契约假设；该边不得声明最终链接选择已知或修改原始 COMDAT unknown。一般 linkonce、weak/weak_odr、ifunc、动态边界及不可证明兼容的副本 SHALL 保持 unknown。

#### Scenario: A standard-library helper meets restricted ODR rules

- **WHEN** 固定 atomic 样例的直接辅助调用满足全部 ODR 采用条件
- **THEN** 允许使用该本地函数体推导效果/返回关系，证据标明 ODR 语义代表及假设，而原始索引仍保留其保守 COMDAT 状态

#### Scenario: A possible ODR body conflicts or can be replaced

- **WHEN** 可见副本不兼容、存在冲突强定义、interposable、非封闭边界或未支持 selection
- **THEN** 不任选一个定义，输出候选/unknown 和原因；即使各候选同名也不宣称函数体已确定

#### Scenario: A plain linkonce body resembles an ODR helper

- **WHEN** 精确 linkage 是 linkonce 而不是 linkonce_odr，其他外观信息相似
- **THEN** 不套用 ODR 采用通道，证明补充事实不能继续沿用 P1 折叠后的 linkage 值作判断

#### Scenario: Similar ODR bodies reference distinct private globals

- **WHEN** 两份看似相同的函数体引用不同 TU 的同名私有全局
- **THEN** 指纹保留被引用存储身份差异，不因剥离模块前缀或文本同名而认定副本兼容

### Requirement: Associate canonical source entities without inventing target scope

显式 AST-assisted scope SHALL 可选引用 `ProgramEntityIndex` 与 `CanonicalObjectOverlay`，将多个 artifact-local function/object key 关联到已解析 program entity/object；该关联 MUST 保留原 scope 成员和每个 dependency digest。`compile_commands.json` 仍只表示逐 TU 编译记录，不得因实体可解析而自动推导 target/link 图或加入 scope 外 TU。

#### Scenario: Two scoped artifacts bind one external object

- **WHEN** 两个 scope 成员通过唯一 source definition 和兼容 IR binding 指向同一 external object
- **THEN** association 输出一个 canonical object relation，并保留两个原始 artifact-local key

#### Scenario: Repeated evidence names the same artifact-local object

- **WHEN** 多个 source declaration/binding 证据指向完全相同的 `(artifact_key, LLVM object id, kind)`
- **THEN** overlay 在判定定义基数前对 target 去重，但保留所有 binding id/source node；不将重复证据误判为多定义

#### Scenario: The only definition is outside scope

- **WHEN** scoped declaration 的定义只存在于 compilation database 的 scope 外记录
- **THEN** association 保持 unresolved/out-of-scope，不自动扩大 scope

### Requirement: Propagate ambiguous source association conservatively

source entity、definition 或 IR binding 为 ambiguous/conflict 时，scope association SHALL 保存所有候选和 frontier，不得按名称、输入顺序或缓存顺序选择。旧 IR-only association 在未显式请求 AST overlay 时 MUST 保持不变。

#### Scenario: Same-named internal objects appear in multiple modules

- **WHEN** 多个 TU 存在同名 internal-linkage 对象
- **THEN** association 保持各自 TU-local identity，不创建跨模块对象关系
