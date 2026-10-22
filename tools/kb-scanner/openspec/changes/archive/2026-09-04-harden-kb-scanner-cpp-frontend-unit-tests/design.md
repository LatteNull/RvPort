## Context

`integrate-kb-scanner-cpp-frontends` 已独立实现 `kb_scanner/frontends/cpp` 七个正式模块，并在独立容器中达到 120 项全量测试。新增的 38 项测试实际由 22 项模块/组件测试、5 项真实 libclang 集成、6 项组合/staged 集成和 5 项边界合同组成；测试总数证明已有场景通过，却没有提供“每个模块的纯逻辑和异常分支均被隔离验证”的证据。

当前明显缺口包括：`vocabulary.py` 没有独立测试文件；Tree-sitter 初始化异常、同名不同目录 context、候选评分边界未隔离；Clang adapter 主要依赖真实 libclang，初始化/游标/位置异常和资源生命周期无法精确注入；composite frontend 的多文件 Diagnostic 顺序、重复去重和 baseline 整体失败传播覆盖不足；workspace 与 compilation database 仍有 discovery/read、invalid shape/token 和路径组合分支未覆盖。当前也没有模块映射或覆盖率报告，容易再次用全量测试数量掩盖单元覆盖缺口。

所有测试仍必须在独立 `kb-scanner-test` 容器执行。现有正式 frontend 行为、默认 legacy profile、120 项基线、pre-rewrite 字节冻结、结果 schema 和两份 Clang/GCC 事实数据均为不可回退边界。

## Goals / Non-Goals

**Goals:**

- 为七个正式 C/C++ frontend 模块建立明确、快速、可隔离的单元测试套件。
- 对正常、边界、异常、降级和确定性路径建立模块级断言，而非只从 staged 或真实 parser 集成侧间接覆盖。
- 保留真实 Tree-sitter grammar、libclang、staged pipeline 和 legacy compatibility 测试，并在输出中区分测试层级。
- 生成正式 frontend 单元测试的行/分支覆盖摘要，以固定门槛阻止覆盖回退。
- 用清单自动验证正式模块与单元测试文件的一一映射。
- 只在必要时增加最小、显式、行为不变的依赖注入 seam。

**Non-Goals:**

- 不增加或修改 C/C++ Evidence vocabulary、检测能力、知识加载、跨文件关系、分类或 readiness。
- 不因为测试发现现有行为不理想而顺带重写算法；真实缺陷另立 change，测试先固化事实并报告。
- 不删除或用 mock 测试替换现有真实 grammar/libclang 集成测试。
- 不切换默认 CLI，不生成新报告结构或 shadow result。
- 不修改 legacy 五个冻结文件、两份事实 JSON、生产镜像或根 Compose。
- 不执行真实 RISC-V 编译、项目构建或项目测试，不扩大到 OS/内核/驱动/板级迁移。

## Decisions

### 1. 新增独立 unit suite，而不是给现有 integration 文件继续堆 case

新增目录采用：

```text
tests/unit/frontends/cpp/
  test_vocabulary.py
  test_workspace.py
  test_compilation_database.py
  test_arguments.py
  test_tree_sitter_adapter.py
  test_clang_adapter.py
  test_frontend.py
```

每个文件对应一个正式模块，使用 `unittest` 与 `unittest.mock`，不引入第二套测试框架。现有顶层 `test_formal_cpp_frontend.py`、`test_formal_clang_frontend.py` 和 `test_frontend_staged_integration.py` 保持为 component/integration 层，不通过重命名制造单元测试数量。

备选方案是在现有七个测试文件中补 case。该方案不能从发现路径和运行输出区分隔离测试与真实依赖测试，也不利于单独计算 unit coverage，因此不采用。

### 2. 测试清单负责证明模块到测试的覆盖关系

增加机器可读 frontend test inventory，记录每个 `kb_scanner/frontends/cpp/*.py` 正式模块对应的 unit 文件以及适用 component/integration/contract 文件。合同测试枚举生产模块并与清单双向比较：新模块没有映射、清单引用不存在文件或模块被删除后残留记录均失败。`__init__.py` 只验证导出边界，不计入业务模块一一映射。

清单表达“哪些层覆盖哪个模块”，不表达测试通过或算法正确；具体行为仍由测试断言负责。

### 3. 单元测试默认隔离真实 parser、libclang 和命令执行

- vocabulary 直接验证 ID 材料、JSON-safe metadata、非法 kind、无位置排序和 context-specific Evidence。
- workspace 使用临时目录与 mock 的路径发现/异常，验证后缀、过滤、空目录、missing/unsupported、symlink/path escape 和 discovery failure。
- compilation database 使用临时 JSON，覆盖 root 非数组、非 dict entry、非标量 arguments、command tokenize、paired/joined include、define 覆盖、相对 directory、空 command、部分与全部失败、identity path redaction。
- arguments 使用表驱动 case 覆盖所有 allowlist/拒绝组、paired 缺值、joined path、compiler/source/`-c` 移除和 Diagnostic 去敏。
- Tree-sitter adapter 使用 fake parser/tree/node 或 patch loader 触发初始化、read、ERROR/MISSING、双 grammar score/tie-break、同名不同目录 context、macro expansion 与重复去重；真实节点类型正确性继续由 component fixture 验证。
- Clang adapter 使用 fake `cindex`、Index、TranslationUnit、Cursor 和 Diagnostic，验证 parse options/accepted args、初始化异常、severity/location 映射、workspace 外过滤、游标异常隔离、多 context ID、重复去重和释放路径；真实绑定兼容性继续由 libclang integration 验证。
- composite frontend 注入 fake adapters，覆盖 complete/partial/unavailable/failed 组合、多文件顺序、Diagnostic 去重、无 context、不匹配 context、非法 subject 和跨 producer 保留。

测试只调用 scanner Python API，不运行 compiler executable、构建、配置或项目测试命令。

### 4. 可测试性修改限于显式 loader/injection seam

优先使用 `unittest.mock.patch` 和现有 `CppFrontend` 构造注入。若 lazy `clang.cindex` import 或 Tree-sitter parser 构造无法稳定替换，可新增私有 loader 参数或小型 protocol/callable；默认值仍加载当前固定实现，第三方对象不得进入公共返回类型。

任何 seam 修改必须先由 characterization test 固定原行为，并由现有真实 parser tests 证明默认路径无变化。不得为了达到覆盖率而捕获本应失败的异常、删除 Diagnostic 或改变状态传播。

### 5. 覆盖率只针对隔离 unit suite，并设置双门槛

选择 `coverage.py` 作为 test-only pinned dependency，仅加入 `requirements/test.lock`。unit coverage runner 只加载 `tests/unit/frontends/cpp`，source 限定为 `kb_scanner/frontends/cpp`，启用 branch coverage，并将数据和临时 JSON 写入容器 `/tmp`。

初始质量门槛为：

- 行覆盖率至少 90%；
- 分支覆盖率至少 80%；
- 七个业务模块均必须有 executed lines，不允许用高覆盖模块掩盖完全未执行模块。

门槛以 unit suite 单独计算，真实 Tree-sitter/libclang 集成执行不得抬高该数字。选择 90/80 而非形式上的 100%，因为第三方对象析构、解释器/平台防御分支可能不适合通过脆弱 mock 强行触发；未覆盖行和分支仍在摘要中明确列出。后续只能提高门槛；降低必须修改规格并说明原因。

### 6. 一个测试容器顺序执行 unit gate 与完整回归

保留唯一 `kb-scanner-test` 服务，不增加第二个 Compose 服务。测试入口先运行隔离 unit suite 和覆盖检查，成功后再运行完整 unittest discovery；任一步失败均保持非零容器退出码。输出分别标注 `frontend-unit` 覆盖摘要与 `full-regression` 测试数量，避免再次把两者合并表述。

测试运行器可以是测试目录下的小型 Python orchestration script；它只组织 unittest/coverage，不成为 scanner runtime 模块。容器仍使用 `network_mode: none`、只读根文件系统和 `/tmp`，不修改生产 Dockerfile 或根 Compose。

### 7. 兼容回归和事实数据继续作为独立门槛

完整回归必须保留当前 120 项测试并包含新增 unit tests。既有合同继续验证 legacy 五文件字节冻结、`schemaVersion: "1.0"`、顶层字段、Finding 关键语义、三个 artifact，以及：

- `clang-x86-entries.json` SHA-256 `adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7`；
- `gcc-x86-entries.json` SHA-256 `89775341ee880b13ac4f10a30558ff5d52875b25a3233114a5765601f0a9dad9`；
- 两份数据的六类计数、source 和 YAML `generatedSet` 引用。

新单元测试不读取或复制事实数据来验证 frontend 逻辑；事实资产只由兼容合同验证，留给后续 Knowledge/Detector 正式消费。

## Risks / Trade-offs

- [风险] 为追求覆盖率写出依赖私有实现细节的脆弱测试。→ 优先断言公共/模块边界行为；私有 helper 只在其承载安全或稳定身份规则且无法从公共入口精确定位时直接测试。
- [风险] mock 的 Tree-sitter/Clang 对象与真实 binding 行为漂移。→ mock tests 只验证 scanner adapter 控制流，现有真实 grammar/libclang tests 继续作为兼容门槛。
- [风险] 覆盖工具改变宿主机或生产依赖。→ 仅固定在 test lock 和测试镜像，数据写 `/tmp`，不改生产镜像。
- [风险] unit suite 和 full regression 重复执行新增测试，增加时间。→ 测试 runner 分离 suite discovery，避免重复；如实现复杂度过高，可接受短时重复但必须在输出中明确。
- [风险] 单元测试暴露真实实现缺陷。→ 不在测试 change 中悄悄改变语义；先增加失败 characterization/记录，再为行为修复另立 change，除非只是明确的异常隔离 seam。
- [风险] 90/80 门槛仍可能遗漏关键语义。→ 使用显式场景矩阵和逐模块 executed-lines 要求，覆盖率只作为补充指标而非完成定义。

## Migration Plan

1. 固化 120 项基线、七模块清单、现有测试层级及未覆盖场景矩阵。
2. 增加 test-only coverage 依赖和独立 unit suite 运行入口，先保证无应用代码改动时能报告真实基线。
3. 按 vocabulary → workspace → compilation database → arguments → Tree-sitter → Clang → composite frontend 顺序补齐隔离测试；仅在被测试阻塞时增加最小 seam。
4. 达到行 90%/分支 80% 和逐模块 executed-lines 门槛后，运行完整容器回归、安全 marker、legacy freeze、输出兼容与事实数据合同。
5. 更新测试文档，分别记录 unit coverage 与 full regression 数量，运行 OpenSpec strict validation。

回滚删除新增 unit suite、inventory、coverage runner 和 test-only dependency；如果增加了 injection seam，则只有在现有真实 parser/integration tests仍通过的前提下回滚。默认 CLI 和报告合同从始至终不切换。

## Open Questions

无。测试层级、目标模块、容器边界、覆盖门槛和兼容资产已确定；apply 阶段先采集覆盖基线，再按未覆盖列表补齐。
