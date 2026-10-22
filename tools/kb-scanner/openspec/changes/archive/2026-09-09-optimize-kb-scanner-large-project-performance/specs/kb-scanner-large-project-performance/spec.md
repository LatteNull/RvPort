## ADDED Requirements

### Requirement: 引用校验必须复用单次阶段索引
CppEvidenceNormalizer SHALL 在单次 normalize 的原始与派生 Evidence 集合确定后，最多一次构建完整 macro definition ID 索引并用于全部宏附属引用校验。该校验的全量 Evidence 遍历成本 SHALL 为 O(E)，附属引用查询 SHALL 为 O(M)，MUST NOT 对每个 macro parameter/replacement token 重建全量定义集合。索引 MUST NOT 跨扫描持久复用。

#### Scenario: 宏附属 Evidence 数量增长
- **WHEN** 固定规则下同时增加 Evidence 总量和宏参数/replacement token 数量
- **THEN** 完整定义索引构建次数 SHALL 不随 token 数量增加
- **AND** 事实数量、身份、span、metadata、producer/context 与原语义 SHALL 一致

#### Scenario: 宏引用缺失或错误
- **WHEN** 附属 Evidence 的 definition reference 缺失、类型错误或指向不存在的定义
- **THEN** Normalizer SHALL 保留既有 failed 状态和 invalid-macro-definition-reference Diagnostic
- **AND** 索引优化 MUST NOT 让无效事实进入成功 snapshot

#### Scenario: 同一实例连续处理两个项目
- **WHEN** Normalizer 连续接收定义集合不同的两个 snapshots
- **THEN** 每次引用校验 SHALL 只使用当前完整输入
- **AND** 先前定义 MUST NOT 使后一个项目的无效引用通过

### Requirement: 性能观测必须独立于正式结果语义
测试性能入口 SHALL 复用正式 staged pipeline 接口，记录扫描版本、运行时与 fixture/知识摘要、资源预算、总耗时、阶段开始/结束状态、数量及峰值资源。阶段包装器 SHALL 透传原参数、返回值和异常，MUST NOT 改变 core snapshots、Diagnostic、正式 artifact 或稳定身份。性能工件 SHALL 与正式报告目录分离。

#### Scenario: 扫描正常完成
- **WHEN** benchmark 完成正式 pipeline
- **THEN** 测试记录 SHALL 覆盖 workspace、knowledge、frontend、normalizer、analyzer、detector、classifier、assessor 和 projector
- **AND** 启用/禁用观测后的语义结果 SHALL 相同，正式目录仍只含固定三个 artifact

#### Scenario: 阶段尚未结束就超时
- **WHEN** scanner 在某阶段运行时超过固定测试预算
- **THEN** 测试记录 SHALL 保留最后进入阶段和已完成阶段，不补造未完成阶段耗时或报告
- **AND** 父进程 SHALL 终止并回收本次子进程，记录 timeout 与实际退出信息

#### Scenario: 分离诊断和验收测量
- **WHEN** 运行开启 coverage 或 cProfile
- **THEN** 该记录 SHALL 显式标记诊断用途
- **AND** 它 MUST NOT 代替不带这些开销的全项目墙钟验收

### Requirement: 下游性能优化必须保持完整查询与判定语义
Analyzer、Detector 或 Projector 的后续优化 SHALL 以阶段 profile 的实测热点为依据，复用现有索引或单次调用内的局部索引，保留多值关联、稳定顺序和完整 provenance。实现 MUST NOT 通过缩减输入、过滤合法证据/诊断或改变候选准入规则达成性能目标；源码 proof SHALL 按以下 fact 驱动需求生成，而非物化与所有候选无关的路径。

#### Scenario: 有证据的多值查找优化
- **WHEN** profile 确认全量关系查找是瓶颈
- **THEN** 索引 SHALL 保留全部适用 producer、configuration、occurrence 和原排序
- **AND** 没有证据的其他业务阶段 SHALL 保持原语义

### Requirement: 源码 proof 必须由现有事实需求驱动
正式管线 SHALL 复用现有 fact 和匹配规则生成保守 Evidence 需求，包含 confirmed、candidate 和 hint。基础图和全部事实 SHALL 保留；反向候选计划 SHALL 覆盖原深度内所有可能经过需求 Evidence 关系的路径，详细搜索 MUST 保留原路径顺序、状态、预算及身份算法。

#### Scenario: 命中点位于路径中间
- **WHEN** 原路径终点不是候选符号但路径关系包含候选 Evidence
- **THEN** 该路径 SHALL 纳入需求范围，不得仅按终点名称过滤
- **AND** 未知、partial 和并行边 SHALL 保留原详细搜索语义

#### Scenario: 候选无路径或没有匹配候选
- **WHEN** 候选没有可达路径，或整个扫描没有匹配需求
- **THEN** 源码事实和基础关系 SHALL 保留，候选检测 SHALL 继续，无匹配需求不触发全目标 proof 查询
- **AND** 构建/测试整体分析 SHALL 继续，不得据无 proof 宣称 ready

#### Scenario: 候选索引不可用
- **WHEN** 注入图存储没有可靠的候选索引能力
- **THEN** resolver SHALL 回到原详细查询，不得把不可用当成不可达

### Requirement: 选择分析预算必须与继承图数量隔离
构建和测试阶段 SHALL 以各自新增关系/proof 数量计算原有预算，MUST NOT 用继承源码图的数量挤占局部预算；数值上限和已知/未知判定规则 MUST NOT 提高或放宽。

#### Scenario: 继承大量无关 proof
- **WHEN** 同一构建或测试事实分别接收少量和大量无关继承 proof/关系
- **THEN** 本阶段新增的选择链路、截断和预算 Diagnostic SHALL 一致
- **AND** 原有候选、schema、源码行数及 provenance SHALL 保持

#### Scenario: 多条关系关联同一 Evidence
- **WHEN** 索引替代对完整关系集合的重复查找
- **THEN** 查询 SHALL 返回全部适用的 producer、configuration 和 occurrence 关系
- **AND** 完整/未知状态、proof 引用和最终结论 SHALL 与优化前语义一致

#### Scenario: 尚无性能证据
- **WHEN** 某阶段没有 profile 证实的重复工作瓶颈
- **THEN** 本 change SHALL 保持该阶段原实现和业务语义
- **AND** 不得为潜在速度收益引入新 parser、并行系统或全局缓存

### Requirement: 全项目性能验收必须固定输入与资源
独立性能入口 SHALL 使用 libarchive commit `c4cfba676d2b86d6a2a7c508cd90a75c4dfaa1d9` 的完整快照，通过项目相对路径/内容 SHA-256 manifest 验证默认 810 个输入（802 C/C++、8 构建输入）、既有默认排除项、comment/language 参数和无 compilation database 状态。验收 SHALL 在唯一独立测试镜像的 2 CPU、2 GiB 内存、禁用额外 swap 的容器内，连续运行两个独立的新 scanner 进程；每次默认 V2 SHALL 在 300 秒内 exit 0 并产生通过 schema/引用校验的三个 artifact。

#### Scenario: 完整 fixture 通过验收
- **WHEN** 两次扫描均使用核验后的完整输入且不启用 profiler/coverage
- **THEN** 每次扫描 SHALL 满足预算、保留完整输入覆盖并正常发布 scan-result.json、scan-report.html、scan.log
- **AND** 记录 SHALL 保留两次实际耗时、峰值资源和语义审校结果，不仅挑选最快一次

#### Scenario: 缺失或变化的全量输入
- **WHEN** 显式 mount 不存在、文件缺失、多出扫描输入或摘要不符
- **THEN** 独立性能门禁 SHALL 非零退出并说明 provenance/input 错误
- **AND** 它 MUST NOT 自动下载、缩减为预览/崩溃样例或 skip 后报告通过

#### Scenario: 计时边界与失败分类
- **WHEN** scanner 子进程开始执行
- **THEN** 300 秒预算 SHALL 覆盖 Python scanner 启动至完整 artifact 发布，镜像构建和 fixture 预检时间另记
- **AND** timeout、native signal、OOM 与普通 scanner failure SHALL 按证据区分，旧输出 MUST NOT 被认作本次成功

### Requirement: 性能修改必须具有复杂度与逐模块单元门禁
本 change 新增或实质修改的业务及性能支撑 Python 模块 SHALL 登记隔离 unit inventory，在独立 kb-scanner-test 容器达到每模块至少 90% line / 80% branch。synthetic complexity tests SHALL 用受控遍历/访问计数验证索引复用，而非只用墙钟比例或源码文本断言；真实项目验收 MUST NOT 替代这些单元测试。

#### Scenario: 检查修改模块与测试映射
- **WHEN** normalizer、后续索引模块或性能支撑模块发生修改
- **THEN** inventory SHALL 映射相应 fake/mock 单元测试与独立覆盖门禁
- **AND** 缺失映射、零执行行或任一模块覆盖不足 SHALL 阻止完成

#### Scenario: 验证结果等价与复杂度
- **WHEN** 合成输入含多 producer/context、有效/无效引用、空集合、乱序和连续多次调用
- **THEN** 测试 SHALL 同时校验完整 StageResult/snapshot 等价和重复遍历次数上限
- **AND** 即使运行很快，若引用/Diagnostic/身份发生未批准变化，门禁 SHALL 失败

### Requirement: 性能优化必须维持版本化报告与静态容器边界
扫描 SHALL 继续默认 Schema V2、显式 V1，保留既有必需字段、Finding/evidenceChain/trace、summary、readiness、Diagnostic、退出码语义和固定三个 artifact。两份 Clang/GCC generated facts 字节、知识 manifest/curated 来源和既有高价值回归 SHALL 保持不变。scanner 与性能验收 MUST NOT 执行目标项目配置/编译/测试、扩大到 OS 迁移、安装宿主机依赖或修改生产镜像/根 Compose/后端。

#### Scenario: 默认 V2 与显式 V1 回归
- **WHEN** 同一确定性输入在优化前后分别输出默认 V2 和显式 V1
- **THEN** 规范化机器路径后的语义字段、证据闭包和退出状态 SHALL 一致
- **AND** unknown/provisional MUST NOT 因性能优化或零命中升级为 ready

#### Scenario: 全量旧版本没有报告
- **WHEN** 优化前完整 libarchive 因超时没有可比较报告
- **THEN** 验收 SHALL 明示无旧全量 finding baseline，通过引用/schema/覆盖校验和代表性人工审校建立新基线
- **AND** 它 MUST NOT 用预览零 finding 或自动批准的当前输出宣称语义完全等价

#### Scenario: 容器化运行性能测试
- **WHEN** 独立性能入口启动扫描
- **THEN** 容器 SHALL 网络关闭、只读挂载源码和知识并隔离可写测试输出
- **AND** 只能清理本次创建的进程/容器，不得影响其他任务或现有服务
