## ADDED Requirements

### Requirement: 测试结论必须区分编译选择与内容证明

测试检测与分类 SHALL 分开使用编译成员、注册/运行选择和内容关系。完整的测试构建链与 knowledge-backed x86 依赖可以证明编译阻断；“测试入口使用/断言验证某 fact”的说明 SHALL 另外要求具体 occurrence 的受支持内容关系，不能由同文件共现推出。命名角色或未知 runtime 条件 MUST NOT 作为完整选择证明。

#### Scenario: 未调用辅助函数含 intrinsic

- **WHEN** 测试 source 的未调用函数含 intrinsic
- **THEN** SHALL 保留普通源码事实及其独立编译风险，不声称测试入口已经调用或验证它
- **AND** 若有完整测试编译阻断 proof，建议 SHALL 明确是编译问题而非运行失败

#### Scenario: 完整目标选择但局部条件未知

- **WHEN** 测试 target 已选中，但相关内容条件、调用或 assert 生效状态未知
- **THEN** 内容关系 SHALL 保持 unknown，不借 target selected 补齐局部执行证明
- **AND** 未知 MUST NOT 被静默降为 low、guarded 或 ready

#### Scenario: 真实互斥测试路径

- **WHEN** 同一配置下完整 proof 排除了对应 x86 注册/内容路径，且编译成员状态独立可判
- **THEN** SHALL 仅对被证明隔离的路径表达 guarded
- **AND** 其他配置、未排除编译依赖或未知路径 SHALL 继续独立保留

### Requirement: 测试内容证明必须非破坏性且不夸大覆盖

新增测试用途 SHALL 不删除 Fact/Observation，不将断言形态自动提升为执行依赖，不修改已有纯数据排除的证据门槛。相同根因/occurrence/configuration 的源码与测试语境 SHALL 合并 provenance，避免重复 Finding 与风险计数。内容清单 SHALL 不自动设置测试枚举完整或证明 RISC-V/generic 测试等价、通过、覆盖完整。

#### Scenario: 同一 intrinsic 具有源码与测试来源

- **WHEN** 源码检测与测试内容检测描述同一 occurrence/configuration 的 x86 依赖
- **THEN** SHALL 合并对应语境与来源而非重复计数
- **AND** 不同配置的未知与确定状态 MUST NOT 相互覆盖

#### Scenario: 只有通用测试或数据断言

- **WHEN** 找到 scalar 测试名称，或者含 X86 数据枚举的断言
- **THEN** SHALL 根据显式关联与既有用途 proof 表达候选/数据用途/unknown
- **AND** MUST NOT 由此宣布覆盖 x86 实现、缺少 RISC-V 等价测试、执行阻断或整体 ready

#### Scenario: 存在不完整或冲突 proof

- **WHEN** 同配置相关关系出现截断、缺失引用或冲突，即使另有一条 complete proof
- **THEN** SHALL 保留对应 unknown 原因和真实事实，不用局部 complete 标签隐藏必要断点
- **AND** 未解析的测试输入 MUST NOT 支持 riscv_test_coverage_gap 的完整枚举前提
