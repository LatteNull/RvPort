# 实施与验证记录

最近更新：2026-09-23。实现及最终质量验证已完成，任务 23/23。最终结论见“最终验收”；下文早期暂停信息为历史记录，不代表当前状态。已按用户授权同步主规范并归档；未提交、推送或部署。

## 已执行基线

独立测试容器 `kb-scanner-cmake-verify`，工作区只读、network=none，未安装宿主依赖，未更改生产容器。

```text
docker start kb-scanner-cmake-verify
docker exec kb-scanner-cmake-verify python tests/run_source_chain_unit_tests.py --output /tmp/function-multiversion-baseline-coverage
docker exec kb-scanner-cmake-verify python -m kb_scanner scan --input tests/fixtures/cmake-demo-test1 --rules rulesets/riscv-porting --output /tmp/function-multiversion-baseline-demo
```

修改前基线：573 项隔离单元通过；149 个自有源码文件，整体行覆盖率 98.08068242402702%，分支覆盖率 94.16208791208791%。统计范围为所有 `kb_scanner/`、`scripts/`、`tools/` 自有可执行源码，包括未加载模块；排除测试资产、第三方、自动生成事实与未部署 archive，不排除自有业务逻辑。详情与编译器事实哈希见 `docs/function-multiversion-analysis.md`。

## 当前部分实现

- 新增 `frontends/cpp/function_inventory.py`：受限函数结构、属性 owner 与函数体范围采集。
- Tree-sitter/vocabulary 接入 `function_declaration`，Normalizer 增加对应 kind 与 owner 引用校验。
- 新增人工结构 oracle、语义边界说明和 `tests/unit/test_function_inventory.py`。
- 尚未实现可选 Clang 绑定、版本组分析、Detector、分类、报告投影及最终覆盖/完整回归。

## 失败记录

```text
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_function_inventory
```

结果：5 项测试，3 项通过、2 项失败：

1. `test_invalid_shape_and_template_are_conservative`：期望 bindingStatus=unknown，实际 complete。
2. `test_scope_conditions_and_unsupported_parameters`：期望 conditional=true，实际 false。

初步原因：复用的 fake Node 构造器仅在 child.parent 为空时设置父节点；本套件将已有 child 重挂到 template/namespace/preprocessor 时，旧 parent 未更新，生产代码沿 parent 看到的仍是原 translation_unit。下一步需先修正 fake AST 的 parent 一致性，再重跑定向单元和真实 parser 组件确认生产逻辑；本记录不将初步定位视为已修复或已验证。

依 apply 技能的遇错暂停规则停止继续实施，未改写断言、未降低质量门槛。最终整体/逐模块行及分支覆盖率尚未执行，不能引用修改前覆盖率证明新代码达标。未同步归档、commit、push 或部署；其他任务文件未修改。

## 本次恢复与新暂停点

修复前次 fake AST 重挂 parent 不一致，原 5 项全部通过；随后扩充 inventory 的预算标记、真实坐标、嵌套排除、参数属性反例及 UTF-8/CRLF 测试，当前 inventory 定向 11 项全部通过。固定 compiler/language/source-target/mechanism 准入矩阵，任务 1.2 完成。

新增尚未验收的实现：可选 Clang scalar function semantics、Frontend 只请求基线相关函数位置、Normalizer 范围/owner/configuration 校验与 producer 冲突保留。未运行项目或编译器探测，未更改 schema 核心。

实际命令（工作目录 `D:/projects/RvPort/tools/kb-scanner`）：

```text
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_function_inventory
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_function_inventory tests.unit.test_function_semantics tests.unit.test_function_normalization tests.unit.frontends.cpp.test_frontend tests.unit.frontends.cpp.test_clang_adapter
docker exec kb-scanner-cmake-verify python tests/run_source_chain_unit_tests.py --output /tmp/function-multiversion-progress-coverage
openspec validate implement-kb-scanner-function-multiversion-analysis --strict
git diff --check -- tools/kb-scanner
```

第二条定向套件 33 项，30 通过、3 报错。全量隔离单元 591 项，588 通过、3 报错，执行 13.714 秒。三项均在 `test_function_normalization.py`：`test_configuration_separation_and_input_immutability`、`test_owner_subject_location_configuration_and_type`、`test_producer_merge_conflicts_and_normalizer_failure`。测试构造 `id='config-other'`、`subject_id='other'`、`id='another'`，不满足现有完整小写 SHA-256 合同；未运行到对应业务断言。下次应使用 `stable_id` 构造，包括配置引用，保持断言与生产合同不变。

覆盖统计含所有 152 个自有可执行源码文件（含未加载模块），整体行 98.0492902551598%、分支 94.13870246085011%。范围与排除理由同上。新增模块尚未全部登记到逐模块 inventory，不能把报告中的空 `failedCoverage` 当作本 change 达标；从完整 `coverage.json` 另核实实际受影响模块如下：

| 模块 | 行覆盖率 | 分支覆盖率 |
|---|---:|---:|
| frontends/cpp/function_inventory.py | 100% | 96.4286% |
| frontends/cpp/function_semantics.py | 100% | 100% |
| frontends/cpp/frontend.py | 100% | 100% |
| frontends/cpp/clang_adapter.py | 86.1905% | 75.5556% |
| frontends/cpp/tree_sitter_adapter.py | 96.5318% | 90.2439% |
| frontends/cpp/vocabulary.py | 100% | 100% |
| normalization/functions.py | 93.4783% | 90.9091% |
| normalization/cpp.py | 92.3611% | 91.3793% |

Clang adapter 未达 90/90，需要补新增接线及原有 enum/异常分支的隔离单元，不能用真实 parser 组件替代。任务 1.4 与 2.x 均保持未完成；后续版本组、Detector、分类、投影、真实组件、性能及完整回归尚待实现/执行。

持久报告：`D:/projects/RvPort/.codex-tmp/kbscanner-function-multiversion-20260922/function-multiversion-progress-coverage/summary.json`、`coverage.json`、`html/index.html`。导出完成后停止本次启动的独立容器。OpenSpec strict 与相关 tracked diff 格式检查通过；仅有仓库 LF/CRLF 提示。两份 compiler JSON SHA-256 与基线完全一致。

本次按 apply 技能遇错暂停，未同步归档、提交、推送或部署。下一阶段仍是当前 change 的 apply，不具备归档条件。

## 2026-09-23：主体链路接入，V1 与文本基线未通过

### 本轮完成的实现与证据

- 修复前次测试简写 ID，使用 `stable_id`，归一化 4 项测试通过。
- 完成函数 inventory、可选 Clang scalar hint、Normalizer 结构/owner/配置校验；Clang 缺失、冲突不覆盖 baseline，也不推断项目编译器版本。
- 新增 `analyzers/function_multiversion/` 的纯属性解码、版本化 profile、分桶、default 状态、函数体事实关联与既有 proof 绑定。单 target 不产生缺失推理，编译器 profile 缺失仍为 unknown。
- 接入组合 Analyzer/Detector；非执行成员边不成为替代或选择证明。源码链显式显示真实 attribute → 函数 → intrinsic，复用 ±20 行。
- 初步接入 V2 自包含 namespace、顶层目录、中文 HTML 与双语建议。V2 真实 CLI 已产出三种 artifact；AVX intrinsic 保持 high、单 occurrence；两个 clone 引用一个真实 body。
- 初步扩展机器可读模块映射，尚需在最终交付前完善现有受影响模块到本轮新增测试的精确映射，故任务 1.4 保持未完成。

### 实际执行

工作目录均为 `D:/projects/RvPort/tools/kb-scanner`，使用独立、只读挂载、无网络测试容器，没有安装宿主依赖或更新生产容器。

```text
docker start kb-scanner-cmake-verify
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_function_normalization
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_function_multiversion tests.unit.test_function_normalization
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_function_clang_contract tests.test_function_multiversion_frontend
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_function_multiversion_pipeline
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_function_multiversion tests.unit.test_function_multiversion_pipeline tests.test_function_multiversion_frontend
docker exec kb-scanner-cmake-verify python tests/run_source_chain_unit_tests.py --output /tmp/function-multiversion-progress-20260923
docker exec kb-scanner-cmake-verify python -m unittest tests.test_tree_sitter_native_crash_regression tests.test_tree_sitter_source_span_regression
```

分阶段定向结果：4、14、6、9 项分别通过。扩展后的定向套件 26 项中 25 通过、1 失败：`test_cli_v2_v1_preserves_intrinsic_and_real_source_chain` 的 V2 部分通过，随后 V1 退出 2。失败后仅作诊断与报告保存，没有继续更改实现。

原生崩溃与字节位置组件回归：6 项通过（20.922 秒），包含固定 cJSON/zlib/libarchive 缩减输入及 V1/V2。真实 parser 组件不计入隔离单元覆盖率。

全量隔离单元：615 项，614 通过、1 失败、0 error，19.275 秒。失败为既有双语文本审校测试：新增 `multiversion_unknown` / `multiversion_gap` 尚未加入人工 `tests/fixtures/bilingual-suggestions/expected-pairs.json`。不得删除此检查或用自动重写基线绕过审校。

整体统计覆盖 159 个自有可执行文件，包括未被加载的 `kb_scanner/`、`scripts/`、`tools/` 文件。排除理由沿用上文，仅测试资产、第三方、自动生成数据和未部署 archive。整体行 98.38615268835187%、分支 94.74914965986395%，全部登记模块达到 90/90；无分支的包入口指标为不适用。因测试失败，summary.passed=false，质量任务 5.1 不勾选。

| 本轮主要模块 | 行 | 分支 |
|---|---:|---:|
| function_inventory | 100% | 96.4286% |
| function_semantics | 100% | 100% |
| clang_adapter | 100% | 97.7778% |
| frontend | 100% | 100% |
| tree_sitter_adapter | 96.5318% | 90.2439% |
| vocabulary | 100% | 100% |
| normalization/functions | 100% | 100% |
| normalization/cpp | 95.1389% | 94.8276% |
| function_multiversion/attributes | 100% | 100% |
| function_multiversion/grouping | 97.2603% | 92.8571% |
| function_multiversion/bindings | 98.9583% | 96.4286% |
| function_multiversion/analysis | 100% | 92.8571% |
| detectors/function_multiversion | 100% | 100% |
| projection/v2/multiversion | 100% | 100% |
| pipeline/composite | 100% | 100% |
| projection/v2/source_chain | 99.3421% | 97.5% |

其余登记模块百分比、逐行/分支明细见完整报告。两份原始 compiler facts SHA-256 与此前一致。

### 暂停原因与恢复顺序

1. V1 的 `projection/policy.py` 尚未登记 Detector ID `function-multiversion`，`present()` 会抛出 unmapped detector 的 ValueError。通过真实应用接口复验，V1 diagnostic 为 `projection.failed: Compatible report projection failed: ValueError`；V2 已生成有效报告，不是 Tree-sitter 崩溃。
2. 两条新增双语文案需要人工审校后加入 expected-pairs，并补齐 V1 的对应标题/说明/建议映射。
3. 随后继续未勾选任务，尤其候选合并后的完整 inactive/foreign 排除证明、输出 selection bindings 与共享输出预算、逐例风险 oracle、映射完整性、V1/V2 合同和性能。不能因当前覆盖率达标就视为上述语义已验收。
4. 本轮尚未执行完整 `--regression-only` 或 10000/20000 性能入口；整体质量、文档交付及归档条件仍不成立。

持久目录：`D:/projects/RvPort/.codex-tmp/kbscanner-function-multiversion-20260922/`：

- `function-multiversion-progress-20260923/summary.json`、`coverage.json`、`html/index.html`。
- `function-multiversion-cli-audit/scan-result.json`、`scan-report.html`、`scan.log`：V2 成功样例。

保存报告后停止测试容器。按 apply 技能遇错暂停；未同步归档、commit/push 或部署，未修改其他任务文件。

## 2026-09-23：最终验收

### 本轮补齐

1. V1 登记 `function-multiversion` Detector，沿原字段输出双语标题、解释、建议和相同风险；V1/V2 三 artifact 组件通过。新增两条文案经人工审校加入 expected-pairs。
2. 属性候选合并保留原 Evidence、Knowledge、Relation 及 metadata provenance。每个属性 occurrence 均被完整排除才允许整组 inactive；部分排除、跨配置、截断不能借用该结论。Foreign guard 不新增 x86 多版本问题，独立 confirmed intrinsic/high/blocker 保持。
3. V2 自包含 selectionBindings 输出实际 source/configuration/scope，不泄露 proof/relation ID；语义 hint、选择绑定及来源共享输出预算。版本成员仍非执行边，单 target 不产生 fallback 缺口。
4. 补同一行多函数按列定位、完整/部分排除、selected intrinsic blocker、Assessor 不提升 ready、两个 namespace 并存等隔离单元；补 14 例人工结构与逐例事实/风险/禁止结论 oracle。
5. 提供 `tests/performance/function_multiversion.py`，保留旧报告基准并新增独立人工差异 ledger；更新前端词汇、模块映射和旧测试入口。

### 命令与实际结果

所有 scanner Python 命令只在 `kb-scanner-cmake-verify` 内执行；宿主工作目录 `D:/projects/RvPort/tools/kb-scanner`。只读根文件系统、两个 bind mount 均 RW=false、network=none 已复核。未安装宿主依赖、执行项目命令或修改生产容器。

```text
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_function_multiversion_pipeline tests.unit.schema_v2_projection.test_finding_mapper tests.unit.schema_v2_projection.test_projector
docker exec kb-scanner-cmake-verify python tests/run_source_chain_unit_tests.py --output /tmp/function-multiversion-coverage
docker exec kb-scanner-cmake-verify python tests/run_container_tests.py --regression-only
docker exec kb-scanner-cmake-verify python tests/run_container_tests.py --frontend-unit
docker exec kb-scanner-cmake-verify python -m kb_scanner scan --input tests/fixtures/cmake-demo-test1 --rules rulesets/riscv-porting --output /tmp/function-multiversion-final-demo
```

- 最后定向隔离套件：26 项通过，0.149 秒。
- **最终全量隔离单元：621 项通过，0 failure / 0 error，15.053 秒。** 所有自有 `kb_scanner/`、`scripts/`、`tools/` 源码含未加载文件，共 159 文件；整体行 **98.39474340846711%**、分支 **94.77013918177984%**。`failedCoverage={}`、`passed=true`。
- **最终完整回归：251 项全部通过，334.037 秒。** 含新增 6 项真实 parser/CLI 组件、14 例人工 report oracle、AVX/CMake 与原生崩溃三项目缩减样例；这些不计入上述隔离单元覆盖率。
- 旧 `--frontend-unit` 入口：76 项通过；它包含历史导入的原生/CLI 测试，因此只作为旧入口兼容复验，不作为本次隔离单元达标依据。
- 补充真实 C guard 审校：`__aarch64__` 下 `target_clones("sve,default")` 无 x86 Finding；`__x86_64__` 下 `target_clones("avx2,default")` 的多版本观察为 low/inactive，不能被新 Detector 恢复成 medium。
- CMake demo 固定输入无本轮相关构造：JSON、HTML、scan.log 与最初保存的三个 artifact 分别 SHA-256 完全相同。

首轮完整回归 251 项有 5 项失败，均已查明并复验：结构事实数 29→30、词汇新增两个 kind、前端文件数 8→10，以及两个旧整报告摘要检查。并非将失败断言删除：新增 accelerated 函数事实的身份断言；保留所有旧 ledger；逐字段审校后新建 `function-multiversion-report-differential.json` 并继续严格比对完整摘要。最初新增 oracle 的 readiness 误按对象读取，已按既有 V2 字符串合同修正；14 个期望的事实/风险断言没有放宽。

### 受影响模块覆盖率

百分比为最终隔离门禁结果；无分支的 `__init__.py` 标为不适用。完整逐行/分支明细和其他既有登记模块见持久 `summary.json`、`coverage.json`、HTML。

| 模块（kb_scanner/ 下） | 行 | 分支 |
|---|---:|---:|
| frontends/cpp/function_inventory.py | 100% | 96.4286% |
| frontends/cpp/function_semantics.py | 100% | 100% |
| frontends/cpp/frontend.py | 100% | 100% |
| frontends/cpp/clang_adapter.py | 100% | 97.7778% |
| frontends/cpp/tree_sitter_adapter.py | 96.5318% | 90.2439% |
| frontends/cpp/vocabulary.py | 100% | 100% |
| normalization/functions.py | 100% | 100% |
| normalization/cpp.py | 95.1389% | 94.8276% |
| analyzers/function_multiversion/attributes.py | 100% | 100% |
| analyzers/function_multiversion/grouping.py | 97.2603% | 92.8571% |
| analyzers/function_multiversion/bindings.py | 98.9583% | 96.4286% |
| analyzers/function_multiversion/analysis.py | 100% | 92.8571% |
| analyzers/function_multiversion/__init__.py | 100% | 不适用 |
| detectors/function_multiversion.py | 100% | 98.0769% |
| pipeline/composite.py | 100% | 100% |
| classifiers/policy.py | 98.7342% | 98.0769% |
| projection/policy.py | 100% | 100% |
| projection/v2/multiversion.py | 100% | 100% |
| projection/v2/mapper.py | 96.8421% | 100% |
| projection/v2/projector.py | 100% | 100% |
| projection/v2/renderers.py | 100% | 100% |
| projection/v2/source_chain.py | 99.3421% | 97.5% |
| projection/v2/suggestions.py | 100% | 100% |

排除仅限测试/测量资产、容器安装的第三方依赖、自动生成事实/规则数据及不部署的 archive；不排除难测业务逻辑，不收窄分母，不降低既有 90/90 门槛。单元原生解析边界使用 fake/mock，真实组件另计。

### 性能与报告差异

对 10000、20000 各依次执行 baseline/current/budget，每个独立进程，未与其他 scanner 测试并发测量：

```text
docker exec kb-scanner-cmake-verify python -m tests.performance.function_multiversion --count 10000 --mode baseline --output /tmp/function-multiversion-performance
docker exec kb-scanner-cmake-verify python -m tests.performance.function_multiversion --count 10000 --mode current --output /tmp/function-multiversion-performance
docker exec kb-scanner-cmake-verify python -m tests.performance.function_multiversion --count 10000 --mode budget --output /tmp/function-multiversion-performance
docker exec kb-scanner-cmake-verify python -m tests.performance.function_multiversion --count 20000 --mode baseline --output /tmp/function-multiversion-performance
docker exec kb-scanner-cmake-verify python -m tests.performance.function_multiversion --count 20000 --mode current --output /tmp/function-multiversion-performance
docker exec kb-scanner-cmake-verify python -m tests.performance.function_multiversion --count 20000 --mode budget --output /tmp/function-multiversion-performance
```

每千个普通函数含一组共享体 clone 与一条 intrinsic。baseline 仅在同版进程内关闭新增 inventory/analyzer，并非运行 Legacy；输入、知识及其余阶段相同。当前 10000/20000 分别物化 10/20 个函数、10/20 个组、10/20 次体事实关联，原 20/40 条 high Finding 的 conclusion 和 occurrences 逐字段不变，仅新增 10/20 条 medium/unknown 多版本观察。

| 函数数 | baseline 扫描 | current 扫描 | 增量 | inventory / analysis | baseline/current 峰值 RSS |
|---|---:|---:|---:|---|---|
| 10000 | 2.0378 秒 | 2.3537 秒 | 0.3159 秒（15.5%） | 0.2978 / 0.0034 秒 | 115940 / 127940 KiB |
| 20000 | 3.6359 秒 | 4.1898 秒 | 0.5539 秒（15.2%） | 0.5213 / 0.0052 秒 | 168760 / 190688 KiB |

均未同时超过 10% 且 1 秒；增量主要为一次轻量 inventory，未出现全函数两两比较。单次测量不代表所有真实项目 SLA。budget（组/版本/关联=1/1/0）分别 3.1875/4.7737 秒，partial、保留 1 组、关联 0、defaultGap 0，未删除原 x86 事实。

zlib-shape 人工审校：原 3 个 Finding、severity/actionable/blocking/occurrences 和 V1/V2 日志字节均不变；新增 accelerated 的 owner 事实。V1 只有属性 Finding 的 trace 变化；V2 仅新增 namespace 及真实 attribute→function 源码链，链完整不等于执行可达完整。禁用新增阶段能完全重现旧 JSON/日志摘要，旧 ledger 原样保留。

### 安全、交付与复验资料

两份 compiler JSON 仍为初始 SHA-256：clang `adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7`，gcc `89775341ee880b13ac4f10a30558ff5d52875b25a3233114a5765601f0a9dad9`。排除/根外路径、只读输入、恶意构建文本不执行、原生 Point 禁用与崩溃组件均通过。核心 schema 未改，默认 V2/显式 V1 和后端输入保持；没有扩大到 ARM/OS、交叉编译误选或真实编译。

持久根目录 `D:/projects/RvPort/.codex-tmp/kbscanner-function-multiversion-20260922/`：

- `function-multiversion-coverage/{summary.json,coverage.json,html/index.html}`：最终 621 项隔离单元。
- `function-multiversion-performance/`：六组测量 JSON、baseline/current/budget 完整 artifact。
- `function-multiversion-differential/`：zlib-shape V1/V2 对照及新报告。
- `function-multiversion-final-demo/`：与修改前逐字节相同的 CMake demo 三 artifact。
- `function-multiversion-guards/`：额外 foreign/x86 guard 审校报告。

中文能力/边界与性能复现文档已更新，开发计划新增第 19 节。OpenSpec 操作根始终是 `tools/kb-scanner`。`openspec validate implement-kb-scanner-function-multiversion-analysis --strict` 通过；apply 状态为 all_done（23/23）。根仓库 `git diff --check -- tools/kb-scanner` 与新增文件的 no-index check 均无格式诊断。本轮只修改该目录，未触碰其他任务的 memory-order-analyzer 文件。报告已导出，本次启动的独立测试容器已停止；未修改生产容器。

最终交接为用户授权后同步规范并归档：聊天命令 `/opsx:archive implement-kb-scanner-function-multiversion-analysis`，不在 apply 中自动执行。

## 同步与归档记录（2026-09-23）

用户已授权同步并归档。已将 5 项能力的 12 条新增要求合入主规范：新增函数多版本能力（5 条），补充 C/C++ 前端（2 条）、证据图（1 条）、分类与评估（2 条）以及 V2 报告（2 条）。4 项既有主规范内容完整保留，增量内容逐项一致。

归档路径：`tools/kb-scanner/openspec/changes/archive/2026-09-23-implement-kb-scanner-function-multiversion-analysis/`，包含 `.openspec.yaml` 和全部 23 项已完成任务。开发计划与能力文档的验证记录链接已更新。

在 `tools/kb-scanner` 执行 `openspec validate --all --strict --no-interactive`：归档前 18 项通过（1 个 change、17 项规范），归档后 17 项规范通过。`openspec list --json` 确认无活动 change。根仓库执行 `git diff --check -- tools/kb-scanner` 无格式错误；归档内 Markdown 相对链接及两处文档链接已检查。

本阶段仅同步规范、移动 change 目录和更新文档，不修改可执行代码，因此未重复运行容器单元测试；实现阶段的测试、覆盖率与报告位置见上文。本次未提交、推送、部署或修改其他任务目录。该 change 的 OpenSpec 流程结束。
