# KB Scanner Autoconf Target Support Specification

## Purpose

定义 KB Scanner 对 Autoconf 配置入口、目标识别与名称规范化的有界静态分析，保留源码证据、目标与观察环境隔离，以及现有 V1/V2 输出合同。

## Requirements

### Requirement: Autoconf 分析必须建立有作用域的配置链
Scanner SHALL 以配置单元组织 configure.ac/configure 与 config.guess/config.sub，识别常见无括号 canonical 宏、受限多行字面参数、AC_CONFIG_AUX_DIR 和字面子项目关系。它 SHALL 使用当前输入内可证明的源码调用/声明关系，MUST NOT 将声明视为已观测的实际执行；未知宏/目录、来源冲突或同名脚本歧义 SHALL 保持 unknown，不以任意第一份脚本代表项目。

#### Scenario: 显式辅助目录与旧 vendor 脚本共存
- **WHEN** 主配置使用 build-aux 的辅助脚本而 vendor 子项目有旧版脚本
- **THEN** scanner SHALL 分开建模两个配置单元与脚本版本
- **AND** MUST NOT 将 vendor 的拒绝结论直接应用到主配置

#### Scenario: canonical 宏没有括号
- **WHEN** configure.ac 含无括号 AC_CANONICAL_HOST 与字面 AC_CONFIG_AUX_DIR
- **THEN** scanner SHALL 保留 canonical 需求和辅助目录声明的位置关系
- **AND** MUST NOT 将宏声明本身当作脚本实际执行证据

#### Scenario: 辅助文件尚未由 bootstrap 提供
- **WHEN** 配置声明需要辅助文件但输入中没有对应脚本
- **THEN** scanner SHALL 记录 unavailable/unknown 及缺少的关系
- **AND** MUST NOT 推定脚本不支持 RISC-V，也不得运行 bootstrap 下载或生成它

### Requirement: 目标平台信息必须与 x86 观察环境分离
Scanner SHALL 以 target_arch 作为已知目标 CPU，本 change MUST NOT 新增 CLI、输入协议或后端接入；目标 system/release/libc/ABI/候选 triplet 只有当前源码能证明时才可使用。未提供维度 SHALL 保持 unknown，MUST NOT 取自宿主机、测试容器或 x86 构建环境。build/host/target 角色 SHALL 保留，不能全部折叠成一个架构字符串。

#### Scenario: 仅知道 riscv64 而条件还依赖 libc
- **WHEN** 配置链的接受结果依赖目标 libc 且没有明确该信息
- **THEN** scanner SHALL 保留目标条件和 unknown
- **AND** MUST NOT 因测试容器使用 GNU libc 而判为完整接受

#### Scenario: 既有编译上下文描述 x86
- **WHEN** target_arch 为 RISC-V，而既有编译数据库描述 source/x86 环境
- **THEN** scanner SHALL 在不同语义空间分别使用二者
- **AND** 目标求值不得读取 observed x86 CPU、OS 或 cache 作为默认值

### Requirement: 接受与规范化必须来自真实控制流和输出依据
Autoconf analyzer SHALL 在明确的安全子集中恢复 selector 值、变量传播、case 模式的 first-match/嵌套、有限 if 条件、有效标准输出和退出状态；仅符号化已知目标条件下的精确探测，不执行脚本。它 SHALL 按项目 config.sub 的实际转换逻辑恢复名称规范化，MUST NOT 用 scanner 的自有别名表代替项目校验。branch selected 与 target accepted SHALL 是不同判断。

#### Scenario: wildcard 分支明确拒绝目标
- **WHEN** RISC-V 值匹配到 *) exit 1
- **THEN** scanner SHALL 记录命中的失败路径及原始位置
- **AND** MUST NOT 将 wildcard 归为可用 generic 支持

#### Scenario: 含 riscv 名称的分支拒绝目标
- **WHEN** 匹配的 riscv64 分支打印错误并非零退出
- **THEN** scanner SHALL 判断该脚本路径拒绝目标
- **AND** MUST NOT 仅凭名称识别产生 accepted proof

#### Scenario: 通用分支完整接受目标
- **WHEN** 没有专用 RISC-V 分支，但通用路径输出有效系统名称且完整后续校验成功
- **THEN** scanner SHALL 保留该配置链的正向接受证明
- **AND** MUST NOT 生成仅因缺少 riscv 字面分支的迁移问题

#### Scenario: 后置 RISC-V 分支被前置失败分支遮蔽
- **WHEN** case 中较早的匹配分支失败且后面还有看似支持 RISC-V 的模式
- **THEN** scanner SHALL 按 first-match 使用实际可达分支
- **AND** 后置分支不得补成接受证明

#### Scenario: guess 成功但 sub 拒绝
- **WHEN** 已绑定 config.guess 输出有效名称而配套 config.sub 明确拒绝该名称
- **THEN** scanner SHALL 保留完整调用、输出和拒绝链
- **AND** MUST NOT 因上游 guess 成功就判整个配置链接受

#### Scenario: exit 0 没有有效规范化输出
- **WHEN** 辅助脚本成功退出但没有可证明的有效系统名称输出
- **THEN** scanner SHALL 保留规范化 unknown
- **AND** MUST NOT 把成功退出码单独作为 config.sub 支持证明

### Requirement: 未知操作和预算必须阻止过度证明
Scanner SHALL 对未知赋值、动态命令、循环/函数或不支持语法传播依赖相关的 unknown，并有界处理语法错误、调用深度、节点数、抽象状态和图预算。默认每单元 AST 节点 100000、控制流深度 64、活跃状态 128、辅助调用深度 8，图预算沿用既有约束。它 MUST NOT 执行项目 Shell/M4/编译器，MUST NOT 从不完整分支集合证明不存在接受路径。

#### Scenario: 动态命令决定 CPU 或输出
- **WHEN** 某次外部命令、eval 或未知变量影响 selector/规范化结果
- **THEN** scanner SHALL 保留原始事实及稳定 unknown 原因
- **AND** MUST NOT 在未知操作后沿用失效值产生 complete proof

#### Scenario: 大型脚本超过路径预算
- **WHEN** 分析超过显式预算或部分语法无法恢复
- **THEN** scanner SHALL 有界结束并标明 partial/unknown
- **AND** 已证明的局部事实保留，缺失路径不构成拒绝或就绪证明

### Requirement: 支持结论必须限定脚本版本配置单元和目标条件
每个接受/拒绝/unknown 结论 SHALL 绑定具体脚本内容 digest、配置单元、目标条件与使用依据。未来 bootstrap/autoreconf、工具/宏/补丁变化导致脚本内容不明时 SHALL 限定为已观测版本；局部脚本拒绝不自动等于项目 blocker，配置链接受也不等于 RISC-V 编译或项目 ready。

#### Scenario: 未来 RISC-V 构建会重新生成脚本
- **WHEN** 只知道 x86 使用的脚本内容，而 RISC-V bootstrap 可能生成另一版
- **THEN** scanner SHALL 将结论明确限定为已验证 digest 的脚本
- **AND** 对未来版本适用性保持 unknown，不执行重新生成

#### Scenario: 未绑定脚本自身拒绝目标
- **WHEN** 某候选 config.sub 的局部逻辑明确拒绝 RISC-V，但项目使用关系不明
- **THEN** scanner SHALL 保留脚本级候选和使用关系断点
- **AND** MUST NOT 输出确定的项目构建阻断

### Requirement: Autoconf 事实和证据必须兼容现有输出
Scanner SHALL 保留原始 Fact/Evidence，通过真实 Relation/ProofPath 交由后续分类与评估；MUST NOT 用 classification/assessment 节点冒充源码链。默认 V2、显式 V1、三个 artifact、源码上下各 20 行、精确命中与中英文建议合同 SHALL 保持。unknown SHALL 保持非确定阻断；历史构建输入 MUST NOT 改变本次 scanner 的静态范围声明。

#### Scenario: Finding 解释目标拒绝
- **WHEN** 有完整依据连接配置入口、辅助调用、selector 和拒绝位置
- **THEN** Finding SHALL 展示这些实际节点各自的来源、行列、上下文与命中
- **AND** conclusion SHALL 提供中文 suggestion 和英文 suggestion_en，不把分类阶段插入主链

#### Scenario: 专用分析未知但旧关键词逻辑看似支持
- **WHEN** Autoconf 专用分析产生 unknown，而旧 role 推断能从同文件找到 generic/riscv 字样
- **THEN** scanner SHALL 禁止旧推断将该事实升级为 complete 或重复产生缺口
- **AND** 其他 Make/RPM/机器元数据的既有语义 SHALL 保持独立

### Requirement: 新能力必须通过隔离单元覆盖和容器回归验收
全部新增/实质修改/抽取复用的自有可执行模块 SHALL 登记 unit inventory，覆盖正常、边界、异常路径并 fake 原生解析、文件和进程边界。整体及每个受影响模块 SHALL 达到至少 90% 行与 90% 分支覆盖，统计纳入未加载的 kb_scanner/scripts/tools 自有源码且排除项有理由。测试 SHALL 只在独立 kb-scanner-test 容器执行，真实 parser、真实项目或组件结果 MUST NOT 替代隔离单元覆盖。

#### Scenario: 独立容器执行完整门禁
- **WHEN** 执行本 change 单元与现有 scanner-wide/完整回归入口
- **THEN** SHALL 输出可复跑命令、测试结果、整体与逐模块覆盖、统计清单和持久报告位置
- **AND** 任何测试失败或覆盖不足 SHALL 保持质量任务未完成，不降低门槛或缩小业务统计范围

#### Scenario: 固定真实脚本与无副作用回归
- **WHEN** 扫描固定版本 GNU 辅助脚本及真实 Autoconf 项目，并对照人工 oracle
- **THEN** SHALL 区分 accepted/rejected/unknown，保留来源版本/哈希和支持边界
- **AND** 不执行被扫描项目、无网络/marker 副作用；AVX/RPM/枚举/候选/V1/V2/双语回归及两份 compiler JSON 哈希校验 SHALL 保留
