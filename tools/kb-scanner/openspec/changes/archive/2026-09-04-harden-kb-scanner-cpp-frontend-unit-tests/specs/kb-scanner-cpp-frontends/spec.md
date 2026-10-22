## ADDED Requirements

### Requirement: 正式 C/C++ Frontend 必须具有逐模块隔离单元测试
正式 C/C++ frontend 的 vocabulary、workspace、compilation database、Clang arguments、Tree-sitter adapter、Clang adapter 和 composite frontend SHALL 各自具有可独立运行的单元测试，测试 SHALL 隔离文件系统、parser、libclang 和下游阶段边界，并 MUST NOT 以真实集成测试数量代替模块级断言。

#### Scenario: 纯转换与确定性逻辑
- **WHEN** 单元测试验证 Evidence/Entity 构造、排序、路径规范化、参数分类或 context identity
- **THEN** 测试 SHALL 直接断言有效、边界和无效输入的返回值、稳定身份及 Diagnostic
- **AND** 测试 MUST NOT 要求真实 Tree-sitter parse、libclang translation unit、compiler executable 或项目命令

#### Scenario: Adapter 异常和降级路径
- **WHEN** Tree-sitter 或 Clang 初始化、解析、游标访问、位置转换或输入读取发生异常
- **THEN** 单元测试 SHALL 通过 mock/fake 精确触发对应分支并断言 complete/partial/unavailable/failed 状态
- **AND** 测试 SHALL 验证可恢复 Evidence、其他文件或其他 compilation context 不被删除

#### Scenario: Composite Frontend 聚合结果
- **WHEN** fake adapters 返回 complete、partial、unavailable、failed、重复 Diagnostic 或非法 Evidence 引用的组合
- **THEN** 单元测试 SHALL 验证状态传播、Diagnostic 稳定去重、Entity/Evidence 引用完整性和 producer/context 保留
- **AND** Frontend MUST NOT 因测试便利而引入 legacy DTO、全局 registry 或隐式 parser 状态

### Requirement: Frontend 测试层级与覆盖度必须可审计
测试仓库 SHALL 明确区分 frontend unit、parser/component、staged integration 和 compatibility contract 层级，SHALL 为每个正式 frontend 模块维护测试映射，并 SHALL 在独立测试容器中对隔离单元测试执行可重复的行与分支覆盖度门槛。

#### Scenario: 检查测试清单
- **WHEN** 新增、删除或重命名 `kb_scanner/frontends/cpp` 正式模块
- **THEN** 测试清单 SHALL 映射对应单元测试和适用的组件/集成测试
- **AND** 缺失模块映射 SHALL 使测试容器失败，而不是只更新总测试数量

#### Scenario: 运行隔离单元测试覆盖度
- **WHEN** `kb-scanner-test` 容器执行正式验证
- **THEN** 容器 SHALL 单独运行 frontend unit suite 并报告目标包的行覆盖率和分支覆盖率
- **AND** 任一覆盖率低于仓库中固定门槛 SHALL 产生非零退出码

#### Scenario: 运行完整回归
- **WHEN** frontend unit suite 和覆盖门槛通过
- **THEN** 同一独立测试环境 SHALL 继续运行既有 parser/component、libclang integration、staged integration 和 legacy compatibility tests
- **AND** 测试输出 SHALL 分别显示单元覆盖结果与完整测试结果，不得只报告一个合并数量

### Requirement: 单元测试加固不得改变扫描兼容与执行边界
本 change SHALL 保持正式 frontend 的外部行为、默认 legacy CLI、现有报告合同和知识事实资产不变；为测试隔离增加的 seam MUST 是显式、局部且行为保持不变的依赖注入，所有新增测试依赖 MUST 仅存在于独立 `kb-scanner-test` 容器。

#### Scenario: 增加可测试性 seam
- **WHEN** 难以在不加载真实 parser 或 libclang 的情况下触发异常分支
- **THEN** 实现 MAY 增加构造参数、私有 loader 或 protocol 形式的显式 seam
- **AND** 默认构造行为、core 返回类型、Evidence identity、Diagnostic 和排序 MUST 保持不变

#### Scenario: 验证兼容资产
- **WHEN** 单元测试加固完成并运行完整回归
- **THEN** `schemaVersion: "1.0"`、既有顶层字段、Finding 关键语义和 `scan-result.json`、`scan-report.html`、`scan.log` SHALL 保持不变
- **AND** Clang/GCC 两份事实 JSON 的内容、六类计数、source、SHA-256 及 YAML `generatedSet` 引用 SHALL 保持不变

#### Scenario: 保持静态分析和容器边界
- **WHEN** 测试构造 compilation command、危险参数或 C/C++ fixture
- **THEN** scanner 和测试 MUST NOT 执行 compiler、构建、配置、plugin、response file、项目测试或真实 RISC-V 编译
- **AND** 测试依赖 MUST NOT 安装到宿主机、生产镜像或根 Compose 服务
