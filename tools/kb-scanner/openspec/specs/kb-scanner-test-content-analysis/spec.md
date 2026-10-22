# KB Scanner 测试内容分析规范

## Purpose

定义原始 C/C++ 测试内容的有界静态清单、入口与一跳调用关联、标准断言语义及架构事实用途证明，区分编译选择与运行选择，并明确预算、不确定性和独立容器验收要求。

## Requirements

### Requirement: 原始测试内容必须形成有界且可定位的清单

Scanner SHALL 从已收集 C/C++ 输入恢复测试相关函数/入口、body、直接调用、assert 形态、局部定义/写入及控制条件的 scanner-owned 标量清单，并关联既有事实锚点、producer、TU/configuration 与真实 span。第三方原生对象 MUST NOT 进入后续快照；仅名称/目录或框架宏形态 SHALL 保持候选。

#### Scenario: 普通测试入口与辅助函数

- **WHEN** 显式测试可执行目标具有唯一 main，且同 TU 存在普通辅助函数
- **THEN** SHALL 区分 main、辅助函数和各自实际 body/命中位置
- **AND** 没有调用证明的辅助函数 MUST NOT 仅因同文件被解释为 main 已测试的内容

#### Scenario: 框架宏或损坏语法

- **WHEN** 输入使用第三方框架注册宏、嵌套 lambda，或相关 body 存在 ERROR/MISSING/partial
- **THEN** SHALL 保留可恢复标量来源并给出候选/不完整原因，不把嵌套 callable 内容归给外层入口
- **AND** MUST NOT 用宏名、词法相邻或损坏节点补造完整测试关系

### Requirement: 测试内容关联必须限定为唯一同 TU 一跳及局部直线绑定

Test Content Analyzer SHALL 以已有图、清单和知识引用建立有来源的入口/调用/断言/事实关系。确认的辅助调用 SHALL 限于同 TU 普通函数的唯一直接一跳；局部值连接 SHALL 限于同一直线 block 的普通 scalar 单次初始化到后续使用，且没有中间写入、遮蔽、取地址、别名或逃逸。它 MUST NOT 读取源码、运行 parser 或执行项目命令。

#### Scenario: 唯一一跳调用包含 x86 fact

- **WHEN** 已确认测试入口直接调用唯一辅助函数，辅助函数内存在知识支持的 intrinsic
- **THEN** SHALL 关联调用点、定义/body、intrinsic 及各自配置和条件
- **AND** 关系 SHALL 只证明局部静态调用关联，不声称运行发生或断言通过

#### Scenario: 调用不能唯一解析

- **WHEN** 调用涉及重载、模板、成员/虚调用、函数指针、跨 TU、递归或第二跳
- **THEN** 受影响内容关系 SHALL 保持 unknown，保留断点和原始 x86 事实
- **AND** MUST NOT 通过函数同名或提高图深度绕过语义限制

#### Scenario: 直线绑定失效

- **WHEN** 初始化值在 assert 前被重写、发生分支合流、逃逸或有未知影响
- **THEN** SHALL 停止确定值来源绑定，记录 unknown 原因
- **AND** MUST NOT 由旧定义推出断言的架构期待

### Requirement: 断言用途必须有结构与架构事实双重依据

标准 assert 的确认 SHALL 具备标准头来源、有效宏环境及无未知覆盖/重定义的证明，复用 NDEBUG 和既有宏作用语义。断言参数内的架构依赖 SHALL 来自现有知识、探测或已确认执行用途，而非任意数值、位宽、名称或数据枚举。Scanner SHALL 只说明依赖/期待关系，不求值任意断言结果。

#### Scenario: Intrinsic 参与断言

- **WHEN** 有效 assert 的参数包含 knowledge-backed intrinsic，且源码关系完整
- **THEN** SHALL 展示断言位置、intrinsic 锚点、条件与来源
- **AND** MUST NOT 仅据此声称目标上的断言一定失败

#### Scenario: NDEBUG 或同名覆盖

- **WHEN** NDEBUG 已证明生效，或 assert 被局部重定义/宏环境未知
- **THEN** SHALL 分别说明标准断言不生效或语义未知，不声称其参数必然求值
- **AND** 断言外的 intrinsic、参数或编译依赖 SHALL 继续独立分析

#### Scenario: 普通期望或数据枚举

- **WHEN** 断言只是 value 等于 42、sizeof(long) 等于 8，或比较表示 codec 数据的 X86_FILTER
- **THEN** MUST NOT 仅凭常量、大小或名称生成 x86 执行要求
- **AND** 既有 fact/Observation SHALL 保留，候选用途按既有完整纯数据证明排除分类或保持 unknown

### Requirement: 测试分析必须按事实锚点索引且显式处理预算

实现 SHALL 按 path/TU/configuration 建立可复用内容及事实位置索引，不得对每个测试反复遍历全项目 facts。新清单默认每文件 10000 条、每次扫描 100000 条，每个断言局部绑定最多检查 128 个相关语句；测试阶段既有资产/关系/proof/深度/访问预算 SHALL 保持，按本阶段新增量计费。

#### Scenario: 规模增加但事实稀疏

- **WHEN** 普通断言数量从 1 万增至 2 万，只有少量架构事实
- **THEN** 受控访问计数 SHALL 证明索引复用和锚点查询，而不是测试数乘全图大小的遍历
- **AND** 无架构事实的普通断言 MUST NOT 逐个制造 unknown Finding

#### Scenario: 任一预算截断

- **WHEN** 内容记录、绑定语句、关系或 proof 达到预算
- **THEN** SHALL 发出稳定且可定位的 Diagnostic/截断计数，保留已恢复事实与必要锚点
- **AND** 不完整范围 MUST NOT 用于证明无依赖、覆盖完整或 ready

### Requirement: 测试内容能力必须通过隔离覆盖与静态容器验收

所有新增/修改自有可执行模块 SHALL 登记隔离单元测试，覆盖正常、边界、异常及复杂度行为；整体与各受影响模块行覆盖率和分支覆盖率 SHALL 均至少 90%，统计包含未被加载源码。组件/集成/性能测试 MUST NOT 替代隔离单元覆盖。测试 SHALL 仅在独立 kb-scanner-test 容器内执行，不安装本机依赖或修改生产服务。

#### Scenario: 完整交付验收

- **WHEN** apply 准备完成
- **THEN** SHALL 提供实际可复跑命令、模块映射、统计范围/排除理由、整体/逐模块覆盖率与报告位置，以及完整回归、手写 oracle 和 V1/V2 差异审校
- **AND** 任一门禁未通过或未执行 SHALL 保持对应任务未完成

#### Scenario: 固定真实输入和规模测试

- **WHEN** 执行固定 libarchive 822 文件已批准 manifest 与 1 万/2 万测试内容规模验收
- **THEN** SHALL 保留旧基线，真实项目两次独立进程均在 2 CPU/2 GiB/无额外 swap 下 300 秒内完成三个合法工件并 exit 0
- **AND** SHALL 报告新增阶段成本、峰值资源、规模访问计数、超预算行为及输入/源码哈希，不缩小输入或自动批准当前输出

#### Scenario: 知识与领域边界

- **WHEN** 新分析在缺少 compilation database 的项目上运行
- **THEN** SHALL 复用现有前端及原始 Clang/GCC x86 事实，两份文件 SHA-256 前后保持一致
- **AND** MUST NOT 执行被扫描项目配置/构建/测试，或引入 OS、交叉编译误选与真实通过结论
