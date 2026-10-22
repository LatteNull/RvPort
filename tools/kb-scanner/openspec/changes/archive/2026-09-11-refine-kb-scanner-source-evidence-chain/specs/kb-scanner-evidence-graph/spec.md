## ADDED Requirements

### Requirement: 命中上游闭包必须按 occurrence 和配置有界查询
Evidence Graph SHALL 向下游提供以当前 matched Evidence、occurrence 和 configuration 为锚点的相关子图，保留宏调用/展开、条件保护、include 可见性及已有构建作用证明。查询 SHALL 复用事实需求计划和统一入/出边索引，按关系语义进行上游查询与必要的终端展开，MUST NOT 恢复全 root×terminal 搜索或按每条 Finding 重扫全图。

#### Scenario: 命中宏替换中的 intrinsic
- **WHEN** 终端 intrinsic 的 Evidence 位于本地宏 replacement 中且存在可验证调用与外层 guard
- **THEN** 子图 SHALL 包含实际 definition、replacement、invocation、guard 的完整来源与精确端点
- **AND** 多级同 kind 节点 SHALL 分别保留，未出现调用的定义 MUST NOT 被伪造为已调用

#### Scenario: 不同配置共享头文件
- **WHEN** 同一头文件的宏被不同目标或配置引用
- **THEN** 查询 SHALL 保留各自调用、条件和构建来源，不用一个配置的 selected 状态覆盖另一个
- **AND** 未确认 target membership 的路径 SHALL 保持 unknown，不得按宏同名跨目标连线

#### Scenario: 查询遇到循环或预算
- **WHEN** 上游或终端展开遇到循环、缺失引用或 depth/visited/path 上限
- **THEN** 子图 SHALL 保留已验证局部节点和关系，记录稳定原因和实际预算计数
- **AND** 局部截断 MUST NOT 删除原始 Fact、放宽原图预算或被解释为安全

### Requirement: 源码上游关系必须可精确映射展示端点
Graph Analyzer SHALL 为供源码链消费的 macro/condition/build/source 关系提供明确 Entity 到 Evidence 的端点映射与必要配置来源，不要求每个抽象 Entity 都有伪造位置。折叠结构节点的投影 SHALL 能追溯连续 Relation sequence；未知或非唯一映射 SHALL 显式保持 partial/ambiguous。

#### Scenario: 两个普通同类节点没有直接关系
- **WHEN** 两个 source Evidence 仅因 kind 相同被查询到
- **THEN** Graph SHALL 不新增 contains/calls/alternative_to 等无依据关系
- **AND** 下游可以保留各节点，但不得将它们当作一条完整路径

#### Scenario: 无位置的配置实体连接代码
- **WHEN** 合法关系经过没有源码 span 的配置/结构 Entity
- **THEN** Graph SHALL 提供真实关系序列供下游折叠或解释断点
- **AND** 下游 MUST NOT 复制另一 Evidence 的位置给该抽象实体

#### Scenario: 需求子图规模增长
- **WHEN** 在相同命中和相关子图之外增加大量无关图节点
- **THEN** 索引构建 SHALL 一次完成，查询 SHALL 按需访问相关关系，且相关查询结果及预算语义保持一致
- **AND** 性能回归 SHALL 记录访问计数、时间和内存，不以最终 Finding 条数代替查询正确性
