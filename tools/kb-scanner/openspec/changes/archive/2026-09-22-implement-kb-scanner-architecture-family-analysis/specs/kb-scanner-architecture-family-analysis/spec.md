## ADDED Requirements

### Requirement: 家族发现必须仅消费授权的 C/C++ 路径清单

Scanner SHALL 从同一次 WorkspaceSnapshot 派生路径观察，保留原 source file 稳定身份、收集范围和解析状态；MUST NOT 重新递归发现文件、读取根外路径或执行项目命令。空文件和解析失败文件的路径观察 MUST NOT 被当作源码解析成功。

#### Scenario: 无构建输入的空实现文件

- **WHEN** 授权清单包含空的 `src/foo_x86.cpp` 和 `src/foo_generic.cpp`，没有编译数据库
- **THEN** scanner SHALL 能记录同一家族的两个路径候选
- **AND** MUST NOT 编造函数、intrinsic、代码命中行或选择证明

#### Scenario: 排除、缺失及根外路径

- **WHEN** 对应 generic 文件被用户排除、未提供或因越界软链接未进入授权清单
- **THEN** 家族分析 SHALL 不读取该文件，并将发现范围限定到实际输入
- **AND** MUST NOT 因没有观察到该成员推导不存在通用实现

### Requirement: 路径家族必须采用有界局部模板和可追溯角色提示

Scanner SHALL 支持同目录角色前后缀变体及单角色槽位的镜像架构目录，保留完整非架构路径作为分组边界。角色匹配 SHALL 有词边界、规则 ID 与版本，MUST NOT 使用任意子串或全项目 basename 模糊聚类。首版 SHALL 保持扩展名边界，多角色冲突为 ambiguous。

#### Scenario: 同目录变体与无标记候选

- **WHEN** 输入包含 `src/foo_x86.cpp`、`src/foo_generic.cpp` 和 `src/foo.cpp`
- **THEN** SHALL 按同目录相同剩余 basename 形成候选家族，并把无标记文件记录为 unlabelled
- **AND** generic 名称和 unlabelled 成员均 MUST NOT 被标记为已经证明可移植

#### Scenario: 镜像架构目录

- **WHEN** 输入包含 `src/arch/x86/math/foo.cpp`、`src/arch/riscv/math/foo.cpp` 和 `src/arch/arm/math/foo.cpp`
- **THEN** SHALL 保留一个局部家族及 x86、riscv、foreign 角色提示
- **AND** foreign 成员 MUST NOT 产生 ARM 迁移问题

#### Scenario: 不同模块和扩展名

- **WHEN** 输入包含 `vendor/a/foo_x86.cpp`、`vendor/b/foo_generic.cpp`、`vendor/a/foo_generic.h` 或普通文件 `myx86helper.cpp`
- **THEN** SHALL 不将这些路径仅凭共享子串或 basename 自动合并为同一替代家族

#### Scenario: 多角色或大小写歧义

- **WHEN** 路径含多个冲突角色槽位或存在仅大小写不同的候选路径
- **THEN** SHALL 保留独立身份及歧义原因，不任意选取角色、不把多个弱候选传递合并

### Requirement: 家族发现、架构提示和配置证明必须独立表达

每个家族 SHALL 区分发现范围完整性、成员候选角色和按 configuration 的选择/替代绑定；候选枚举完成 MUST NOT 表示替代实现分析完整。仅有 x86 成员 SHALL 允许记录范围内未观察到其他候选，但 MUST NOT 断言缺少 RISC-V/generic 实现。

#### Scenario: generic 文件实际包含 AVX

- **WHEN** generic 命名成员存在真实 AVX fact
- **THEN** SHALL 同时保留路径提示和原始 x86 事实，分别表达其来源
- **AND** MUST NOT 用路径角色覆盖执行依赖或据此消除 blocker

#### Scenario: 多配置状态不同

- **WHEN** 同一成员在两个 configuration 的既有选择 proof 分别为 selected 和 inactive
- **THEN** SHALL 分别保留绑定及 proof 来源，不生成全局 selected/inactive 状态

### Requirement: 家族处理必须确定性且受显式预算约束

Scanner SHALL 使用模板索引分桶与稳定排序，MUST NOT 做全量成员两两比较。路径、家族、成员、图绑定及输出均 SHALL 有具名预算；截断 SHALL 记录范围、计数与稳定 reason，发现截断和投影裁剪 MUST 分开。ID MUST NOT 包含机器绝对路径或遍历时序。

#### Scenario: 相同输入乱序及更换根目录

- **WHEN** 相同相对文件清单被乱序提供或移动到另一绝对根目录
- **THEN** 家族、成员和绑定 ID 及其排序 SHALL 一致

#### Scenario: 超大同模板家族

- **WHEN** 输入超过家族或成员预算
- **THEN** SHALL 有界终止并稳定保留允许范围内成员、截断状态及计数
- **AND** MUST NOT 把遗漏成员解释为不存在或将已有 facts 删除

### Requirement: 家族能力必须通过独立容器的隔离单元与人工回归验收

新增及实质修改业务模块 SHALL 登记 unit inventory，覆盖正常、边界及异常路径。全部自有可执行代码（含未被加载模块）及每个受影响模块 SHALL 达到至少 90% 行和 90% 分支覆盖率；运行 MUST 在独立 scanner 测试容器内，不在宿主安装依赖。组件回归和性能数据 MUST NOT 替代单元门禁。

#### Scenario: 发布前验收

- **WHEN** 实现申请验收
- **THEN** SHALL 提交实际命令、隔离单元/覆盖率报告、范围与排除理由、人工字段级 oracle、完整回归及性能对照
- **AND** 覆盖不足、失败或缺失模块映射 SHALL 阻止验收，不允许收窄统计范围通过
