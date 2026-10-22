## ADDED Requirements

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
