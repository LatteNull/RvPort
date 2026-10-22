## ADDED Requirements

### Requirement: Describe memory access sizes from module layout

系统 SHALL 使用 BC 内的 DataLayout 和 LLVM 类型 API 给出可确定的访问存储字节数、地址空间与对齐；SHALL 用明确的 known/unknown/not_applicable 状态区分确定值、动态/不支持信息及无普通范围的事件。未知值不得填零，不能从 triple 猜测缺失布局，不能把类型位宽简单除 8 作为全部内存大小。

#### Scenario: Padded structure fields are accessed

- **WHEN** 模块使用带 padding 的结构体布局及不同字段的 load/store
- **THEN** 字段偏移与访问字节数依照该 DataLayout，访问类型大小与结构分配布局不混淆，保留对齐和地址空间

#### Scenario: Layout or access size is not statically available

- **WHEN** 模块缺少可靠布局或访问涉及 scalable 类型/动态大小
- **THEN** 对不能确定的范围记录 unknown 及具体原因，保留事件和类型，不输出虚构固定大小；fence 的普通范围为 not_applicable

### Requirement: Preserve exact constant offsets and address-space boundaries

系统 SHALL 为可解释的常量 GEP 保存原始基址/索引/源元素类型/flags 和依据地址空间 index 位宽计算的精确字节偏移；动态偏移、不能安全解释的指针转换 SHALL 保留 unknown 和原始关系。数值偏移 SHALL 不被当作对象边界、生命周期、in-bounds 或 alias 证明，地址空间转换不得被静默剥离。

#### Scenario: Negative or wide pointer offsets occur

- **WHEN** 合法 IR 的 GEP 含负索引或超出宿主 int64 表示范围的可计算偏移
- **THEN** 保存 index 位宽和精确偏移表示，负值不会变成正值或截断，输出不宣称相应内存访问合法

#### Scenario: Dynamic index or address-space cast occurs

- **WHEN** 地址来自动态 GEP、addrspacecast 或当前不能安全解释的 inttoptr
- **THEN** 保留操作数和地址空间边界，不能计算的对象/偏移带原因标 unknown，不因 strip casts 产生确定同对象结论

### Requirement: Export memory operation values and initialization facts

系统 SHALL 保存 load 结果、store 值、RMW 输入/旧值结果、CAS compare/new/result，并保留 CAS success/failure ordering、weak 与结果使用链。内存 intrinsic SHALL 保存长度引用、读/写地址及各自对齐/地址空间，memset SHALL 保存填充值。全局 SHALL 区分外部声明无初值与静态 initializer，支持整数、零初始化、指针常量和有界聚合，其他形式显式未知；静态 initializer 不得当作动态初始化已执行的证明。

#### Scenario: CAS result is decomposed

- **WHEN** cmpxchg 的结果通过 extractvalue 分别取旧值和成功位并控制分支
- **THEN** compare/new/result/两个提取索引及分支条件引用均可追溯，成功和失败 order 不被合并

#### Scenario: Bulk operations have zero or unknown lengths

- **WHEN** memcpy/memmove/memset 分别具有常量零长度或运行时长度
- **THEN** 零长度保留为精确已知零，运行时长度保留引用和 unknown 大小；传输源与目的、填充值及各自地址属性不丢失

#### Scenario: Declaration and initialized definition coexist

- **WHEN** 模块包含 extern 声明、整数/指针初值、零聚合和未支持的初始化表达式
- **THEN** 声明不产生虚构零初值，支持项有合法值引用，未支持项带原因，不能声称 C++ 动态构造或线程时序已经被分析
