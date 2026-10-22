## ADDED Requirements

### Requirement: Makefile 宏参数必须证明实际作用域再关联源码条件
Build Frontend/Normalizer/Analyzer SHALL 静态恢复受支持 CPPFLAGS/CFLAGS/CXXFLAGS 的已知赋值、追加及引用来源，识别 -DNAME、-DNAME=value、分离 token 的 -D NAME[=value] 与 -UNAME，保留原始位置、顺序、target/source 和 configuration。参数到源码条件宏的确定关系 SHALL 同时具有参数被编译 recipe 静态引用、源码目标归属和宏可见性证据；单独赋值或同名字符串 MUST NOT 构成启用证明。所有过程 MUST NOT 执行 Make、编译器或项目命令。

#### Scenario: 已证明 Make 参数启用当前源码
- **WHEN** 受支持 Makefile 的 CPPFLAGS 定义 -DUSE_AVX2，编译目标明确引用该变量且关联当前源码，源码在 #if defined(USE_AVX2) 下调用包装 intrinsic 的宏
- **THEN** Analyzer SHALL 提供参数来源、recipe 使用、目标源码、条件、宏调用/定义/replacement 到 intrinsic 的可验证关联
- **AND** 每条关系 SHALL 保留实际 Evidence、配置和选择状态，可在同一 Finding 自包含展示

#### Scenario: 参数赋值未被使用
- **WHEN** Makefile 声明 -DUSE_AVX2 但缺少其进入当前编译目标的静态引用证据
- **THEN** 参数 Fact SHALL 保留，作用于当前条件宏的结论 SHALL 为 unknown
- **AND** scanner MUST NOT 仅凭变量名为 CFLAGS 或宏同名断言已启用

#### Scenario: 参数属于其他目标
- **WHEN** -DUSE_AVX2 只在另一目标、配置、注释或无关文件出现
- **THEN** scanner SHALL 不将它作为当前命中的确定上游
- **AND** 原事实不得被删除，缺少当前目标输入时 SHALL 保持相应 unknown

#### Scenario: 动态构造不执行
- **WHEN** 参数或目标作用域依赖 shell、eval、无法解析的 recipe、response file 或外部未知值
- **THEN** 分析 SHALL 有界保留事实与 unknown reason
- **AND** scanner MUST NOT 执行构建来补齐证据

### Requirement: 构建宏绑定必须区分定义存在性与值并保留覆盖
参数宏绑定 SHALL 区分定义/取消、已定义性和值，遵循已证明的参数顺序、translation unit/include 可见性和局部 #define/#undef 作用。受支持条件至少 SHALL 包含 #ifdef/#ifndef、defined(NAME)、已知整数宏的 #if NAME 与受限等值比较；未知/不支持表达式和非等价配置 SHALL 保持 unknown，不推断编译器预定义宏与任意用户宏等价。

#### Scenario: 定义为零的宏
- **WHEN** 已证明当前配置使用 -DUSE_AVX2=0 且无后续覆盖
- **THEN** #ifdef USE_AVX2 SHALL 按已定义处理，而 #if USE_AVX2 SHALL 按假处理
- **AND** 链 SHALL 保存参数值与条件 Evidence，不把两者混成同一真假语义

#### Scenario: 取消或源内覆盖
- **WHEN** -U 或可见的源码 #undef/#define 改变先前 -D 的有效状态
- **THEN** 绑定 SHALL 保留原来源与覆盖依据，仅在顺序和作用域完整时给出确定结果
- **AND** 无法消解时 SHALL unknown，不得无条件使用最早或最后出现的同名文本

#### Scenario: 多级条件及宏包装
- **WHEN** intrinsic 经多级宏包装并处于多层已恢复条件内
- **THEN** Analyzer SHALL 保留每层宏/条件的实际关系，参数只关联到其确实控制的条件
- **AND** 宏调用展开关系 MUST NOT 被替代为条件宏启用关系

#### Scenario: 机器参数没有宏映射依据
- **WHEN** 只有 -mavx2 等机器选项，而没有适用的预定义宏语义证据
- **THEN** 参数 Fact SHALL 仍可检测，但参数到任意用户条件宏的绑定 SHALL 不成立
- **AND** scanner MUST NOT 猜测 -mavx2 等价于 -DUSE_AVX2

### Requirement: 构建宏桥接必须通过隔离单元与端到端人工链验收
每个新增或实质修改的 Make frontend、参数 normalizer、macro binding resolver、build/source graph 接线模块 SHALL 映射到隔离 unit suite，在独立 kb-scanner-test 容器中使项目整体及每个受影响模块达到 90% line / 90% branch，覆盖统计 SHALL 包含未被单测加载的项目自有可执行源码；大规模历史缺口 SHALL 报告并请求扩大范围，未达标不得完成验收。人工 fixture SHALL 逐字段验证参数、条件、宏定义/调用、intrinsic 的端点、位置、状态和闭包，而非仅验证 Finding 总数。

#### Scenario: 正反例验收
- **WHEN** 容器测试覆盖完整链、未使用变量、其他 target、-D0、-U、覆盖、未知输入和同名歧义
- **THEN** 正例 SHALL 给出可验证完整链，反例 SHALL 无伪启用边，未知项 SHALL 保留稳定断点
- **AND** fake 原生解析/文件/进程边界的隔离覆盖 SHALL 与真实语法组件测试分开计算

#### Scenario: 既有构建结果回归
- **WHEN** 运行既有 AVX/RPM/enum/候选及可用真实项目基线
- **THEN** 所有结论变化 SHALL 有新增证据和审校记录，纯投影变化不得改变风险判断
- **AND** GCC/Clang 事实哈希、静态边界、原局部图预算和 V1 字段合同 SHALL 保持不变
