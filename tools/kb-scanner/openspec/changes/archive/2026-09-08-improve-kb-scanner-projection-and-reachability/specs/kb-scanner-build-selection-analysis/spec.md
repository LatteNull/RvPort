## ADDED Requirements

### Requirement: 构建选择必须闭合到 selected source 和 x86 dependency
Build Selection Analyzer SHALL 从目标 selector/configuration、target、source membership、condition、argument 和 source Evidence 建立有界的 selector → target → source → x86 dependency Relation/ProofPath。只有路径中的每条关系均 complete、configuration 一致且目标为 selected 时，source dependency 才 SHALL 被标记为 reachable/selected；缺失或冲突输入 MUST 保持 partial/unknown。

#### Scenario: RISC-V 配置选择含 AVX 依赖的源码
- **WHEN** 完整构建关系证明目标配置选择某源码，且该源码具有 knowledge-backed x86 Evidence
- **THEN** Analyzer SHALL 产生引用 target、source、x86 Evidence 和全部 Relation ID 的 complete proof
- **AND** Detector/Classifier SHALL 可据此判断该依赖对目标可达

#### Scenario: 只有局部源码命中而缺少 target membership
- **WHEN** x86 Evidence 存在但无法证明源码属于 selected target
- **THEN** reachability SHALL 保持 unknown 并记录缺少的关系
- **AND** Analyzer MUST NOT 仅凭文本命中声称 selected 或 inactive

### Requirement: 构建参数聚合前必须保留逐 occurrence 证据
Build Frontend/Analyzer SHALL 为每个构建参数 occurrence 保留独立 Evidence、精确 start/end span、configuration 和 selection status，并 SHALL 通过稳定根因关系允许 Projector 聚合，而不是在分析阶段只保留每文件一个代表值。

#### Scenario: 四个 Makefile 包含二十四个 x86 flag occurrence
- **WHEN** 人工基线列出 24 个实际参数位置
- **THEN** AnalysisSnapshot SHALL 恢复且仅恢复这 24 个 occurrence，并逐项匹配 path、span、flag 和 selection status
- **AND** 最终 Finding 可聚合但 trace MUST 可还原全部 occurrence

#### Scenario: 相同 flag 在不同配置状态出现
- **WHEN** 同一 flag 分别位于 selected、inactive 或 unknown configuration
- **THEN** 每个 occurrence SHALL 保留自己的 configuration 和状态
- **AND** 聚合关系 MUST NOT 用一个 occurrence 的状态覆盖其他 occurrence

### Requirement: 构建闭包修正必须具有隔离单元与人工回归门禁
本 change 修改的 target/source resolver、reachability analyzer、occurrence collector 和 proof builder SHALL 分别映射到隔离单元测试，并 SHALL 在唯一 `kb-scanner-test` 容器中达到每模块至少 90% line / 80% branch。AVX build baseline 中已实现的 24 个 occurrence SHALL 从 deferred 记录迁入正式字段级回归。

#### Scenario: 运行构建分析单元门禁
- **WHEN** 独立容器执行 build-selection unit inventory
- **THEN** fake workspace/snapshot 测试 SHALL 覆盖 complete、inactive、partial、conflict、budget 和乱序输入并满足覆盖门槛
- **AND** 测试 MUST NOT 执行 make、cmake、compiler 或项目命令

#### Scenario: 运行 AVX 构建人工对照
- **WHEN** 新 scanner 扫描 AVX fixture
- **THEN** 24 个 flag occurrence SHALL 与正式人工 baseline 逐字段一致且无 missing/extra
- **AND** baseline MUST NOT 再把已实现的构建证据标为 deferred
