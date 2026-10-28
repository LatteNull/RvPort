## Why

`reduction-reassociation` 声明以循环为评估范围，但当前实现一次收集整个翻译单元的归约事实并生成一个 Finding。例如同一函数中向量通道累加与尾部元素累加被展示为同一条风险的两个位置，且一个候选的歧义或 IR 证据可能影响其他候选的状态和置信度。需要在扫描器内恢复独立归约候选的判断与处置边界。

## What Changes

- 按函数、独立循环和归约候选建立稳定身份，逐候选生成 assessment 和 Finding；不同循环、不同函数以及同一循环内独立累加器不得仅因规则相同而合并。
- 仅使用可归属于当前候选的 AST、IR 和 binding 证据；隔离 matched、notMatched、unknown、failed、补偿判断、置信度和人工确认状态。
- 保留同一候选的多条证据和必要关联位置，避免将“多个证据位置”误等同于“多个独立风险”。
- 保持公开结果 schema v2；修正规则版本、候选预算、计数、稳定 ID、抑制与序列化契约。新扫描的 Finding 数量和身份会改变，不重写历史扫描。
- 补充正常、边界与异常单元测试、独立预期的固定语料和 Docker 验证，要求工具整体及每个受影响模块行、分支覆盖率均至少 90%。
- 2026-10-28 用户批准扩大验收范围：补齐十条规则的真实可执行 C/C++ 输入、独立 oracle 与当前源码 observed 运行器；修正评分器对多候选、重复结果和来源摘要的核验，不改其他规则算法或前端。
- 范围仅限本扫描器；不修改前端、Java 后端或其他扫描工具，不删除前端位置选择器。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `floating-point-risk-detection`：明确归约候选粒度、证据归属和独立判断语义。
- `scanner-runtime-foundation`：明确归约逐候选调度、稳定身份、预算和异常隔离。
- `scanner-io-contract`：明确独立归约 Finding 的 v2 投影、位置、计数、抑制与历史兼容行为。
- `scanner-quality-gates`：增加归约候选隔离回归矩阵和全范围覆盖率验收。

## Impact

- 主要涉及 `src/floating_point_precision_scanner/rules.py`；按需要调整 `facts.py`、`evidence.py`、`result_v2.py`、`suppression.py`、诊断/说明、版本摘要和测试门禁。
- 优先复用既有候选级 ABI/转换规则调度与证据协议。若缺少可靠候选身份，限于本工具补足事实与版本/缓存处理；不以 TU、函数名或行号相同猜测归约关联。
- 更新相关单元/契约/Clang 集成测试及固定语料预期，验证下游仍可直接消费 schema v2。无新增服务、外部依赖或前端 API 要求。
- 提案阶段只创建文档；实现与测试结果须在 apply 阶段实际执行后记录，不沿用历史验收结论。
