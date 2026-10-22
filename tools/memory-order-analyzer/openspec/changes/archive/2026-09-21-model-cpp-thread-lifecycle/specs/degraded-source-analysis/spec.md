## ADDED Requirements

### Requirement: Propagate candidate-relevant C++ lifecycle gaps conservatively

A2 编排 SHALL 将标准库 profile 不支持、ABI wrapper mismatch、callable/object/handle/move provenance ambiguous、构造/join/detach 结果未知、异常路径、scope definition 缺失和 A3 预算 frontier 建模为候选相关 gap，并纳入 TU/entity/object/call/thread/protocol 传递依赖切片。只有可证明与目标候选无关的 A3 gap 才不阻断该候选正式评价；顶层完整性仍须保留。

#### Scenario: An unknown std thread carries the publication worker
- **WHEN** 发布候选依赖的 worker 只能从 AST 识别而 ABI broker 或对象 lineage 未证明
- **THEN** 相关候选降为 partial/unknown，不借用同名 pthread 或其他 TU 的线程实例继续判定风险

#### Scenario: An unsupported std thread is outside the candidate slice
- **WHEN** 依赖切片证明该 A3 gap 的线程、对象、调用和路径与一个完整 C pthread 候选无关
- **THEN** C pthread 候选保留既有评价，顶层报告仍记录非完整 scope 与 A3 gap

### Requirement: Keep AST-only C++ thread candidates below execution proof

AST-only 模式 SHALL 可保存 `std::thread` 构造、callable、对象操作和源码控制候选，但 MUST 保持 `evidence_level=source-only`、`verdict=unknown`、`safety=not-established`，不得建立动态 ThreadInstance、thread-start/exit、join-complete、MHP、RF、SW、HB、risk 或 discharged。

#### Scenario: Source contains a direct lambda thread and join
- **WHEN** AST 可信地识别 lambda 构造与 join 语句但相关 IR/ABI 证据不可用
- **THEN** 输出 source candidate 及缺失证据并退出 partial，不产生已启动或已 join 的线程关系
