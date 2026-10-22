# 实施与验收记录

状态：功能、单元覆盖、完整回归和最终资源复验均已通过；待用户授权同步、归档。仅修改 tools/kb-scanner，不涉及其他任务目录。

## 固定对照

- Scanner 对照提交：`44c756faa7e7485c09e675f5fbeae7fd82407454`。
- 独立镜像：`rvport-kb-scanner-test:local`，ID `sha256:394ff7dcfb096cb5e9479ff5fd06e10d1c3756b89f302d616decf83819d9ae0c`。
- clang-x86-entries.json SHA-256：`adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7`。
- gcc-x86-entries.json SHA-256：`89775341ee880b13ac4f10a30558ff5d52875b25a3233114a5765601f0a9dad9`。
- libarchive 沿用 `tests/fixtures/candidate-usage-performance/PROVENANCE.json`：upstream `c4cfba676d2b86d6a2a7c508cd90a75c4dfaa1d9`，822 文件，输入摘要 `f52edca120bdcd98d6c3316a2c5a42c09e38a99fc2189fa07b33cd3eb85fd67c`；旧 810 文件清单与审校不改写。
- 资源门槛：2 CPU/2 GiB/无 swap/每扫描 <300 秒，功能增加相对耗时作为诊断，不改覆盖及预算门槛。
- 人工真值：`tests/fixtures/macro-build-effects/oracle.md`，实现前固定；差异账本后续追加，不能覆盖历史 golden。

## 模块映射与边界

| 职责/文件 | 隔离单元入口 | 支持/unknown |
| --- | --- | --- |
| frontends/build/macro_arguments.py、make_effects.py、make_values.py | tests.unit.test_make_macro_arguments，tests.unit.test_make_effects | 有界 include/条件/明确自动变量，动态 Make unknown |
| frontends/build/cmake/usage.py、macro_conflicts.py | tests.unit.cmake.test_usage，tests.unit.cmake.test_macro_conflicts | 既有传播、冲突/顺序断点，动态表达式 unknown |
| normalization/build.py、build_effects.py | tests.unit.test_build_macro_normalization，tests.unit.test_build_effects | 多来源、use identity、引用/配置校验 |
| frontends/cpp/macro_records.py 与 adapter 接线 | tests.unit.test_macro_records 及既有 frontend suites | 纯记录和原生生命周期，不支持预处理 unknown |
| analyzers 的宏状态/表达式/实参、build_macro_binding/macro_resolution/evidence_graph | tests.unit.test_macro_effects 及既有对应 suites | TU 状态与有界 proof，不做全量预处理 |
| detector/classifier 接线（若变更） | tests.unit.test_macro_effect_detection 及既有对应 suites | 正式知识匹配，缺 proof 不升级执行 |
| projection/v2/source_chain/chain 等实际修改文件 | tests.unit.test_macro_effect_projection 及既有投影 suites | 真实来源和配置隔离，不改核心 schema |

所有实际文件已逐项登记覆盖 inventory；交付状态以最终门禁为准。测试驱动如新增可执行逻辑须另有隔离单测/覆盖。

## 本轮记录

已读取 proposal/design/5 份 specs/tasks，核对现有 Make/CMake/宏绑定/源码链入口。历史结果仅作对照，不能替代当前实现验收。

### 增量实现与验证（2026-09-24，尚非最终验收）

- Make 多来源 `-D/-U`、静态 include、条件赋值合流、显式 `$@/$<`、编译使用实例身份已接入；多来源参数通过独立来源 Evidence 连接，不伪造拼接后的连续位置。CMake 保留已有 usage 传播，新增冲突/无顺序依据拒绝；显式同命令选项顺序仍可证明。
- 独立容器 `unit-02`：752 单元全部通过；总体行 98.6225%、分支 95.4240%，178 个源码文件，本组实际模块均达 90/90。`unit-01` 的 frontend/macro_arguments 覆盖不足已通过补异常路径修复，不降低门槛。
- `macro_state.py` 支持定义/未定义/未知、整数和布尔组合、使用时对象别名展开与确定性合流。`unit-03` 中该模块、macro_session、macro_records 均为 100% 行/分支；该轮总体测试 764 通过，但 Tree-sitter adapter 分支 89.881%，因此整轮未通过。
- 作用链已接入正式 Detector 的 compiler knowledge 匹配；固定实参的执行需完整 forwarding proof，不使用或仅传值保持 candidate。新增 `macro_argument_token` 属于内部事实，不修改 V2 核心 schema；V1 detector 映射使用现有规则身份。
- 新真实解析组件入口：`python -m unittest tests.test_macro_build_effect_component.MacroBuildEffectComponentTests -v`，容器只读挂载源码且禁止项目 subprocess。Make/CMake 正例、未使用/数据传递/#/##、注释/字符串、两次不同调用、inactive/普通函数反例已通过；多 TU 共享头文件新增 selected/inactive occurrence 审校正在收尾。
- `unit-04/05` 发现 V1 新 detector 映射遗漏、旧投影 fake 缺 relations 属性和 RPM 隔离测试入口迁移，已按原因修复。`unit-06` 776 单元、0 失败/错误；Tree-sitter adapter 分支 89.535%，仍不能标记最终质量验收。新增采集预算及多配置测试后须再次运行完整门禁。
- 每轮完整结果保留在 `D:/projects/RvPort/.codex-tmp/macro-build-effects-20260924/unit-*/`，不覆盖历史报告或 golden。当前全量真实项目回归、固定 libarchive/规模性能、最终差异账本尚未完成；不具备归档条件。

覆盖统计命令为只读 scanner 挂载的独立镜像内 `python tests/run_source_chain_unit_tests.py --output /output`；生产源码统计范围 `kb_scanner/`、`scripts/`、`tools/`，包括未加载源码；第三方、归档源码、规则数据及测试本身沿用 inventory 中明确分类，不新增生产代码排除。

### 后续修复与复验记录

- `unit-07` 首次通过全部 777 项与 90/90 门禁。之后按真实项目/规模反馈继续修复，不把中间通过当最终完成。
- `regression-01`：276 项，6 失败/1 错误。新增实参遗漏语言 metadata 已修复；词汇/inventory 数量同步新内部 kind；Make 实际 CPPFLAGS 引用补入人工链路断言。剩余报告摘要差异经固定旧提交逐字段审校后新增账本，不覆盖旧 golden。
- `libarchive-01`：300 秒超时，无 OOM。`libarchive-profile-02` 为有界诊断（不能作为通过），定位 CMake 内部与公共入口重复绑定宏，以及无需求的普通宏展开。去重、正式知识反向需求索引、不可变环境合流快速路径后，`libarchive-04` 两轮 270.23/283.07 秒通过，峰值 1242724/1248960 KiB，无 OOM。原始 290122 条 facts 全部保留；不靠缩减事实或放宽门槛达标。
- `unit-08/09` 发现旧 CMake fake 应挂公共入口（绑定一次且独立 100000 新边预算）、新增 fake 的 context ID 应为合法 SHA-256，已修复。`unit-10` 782 项通过。
- 初始 16/32 TU 规模样例揭示共享宏文件的旧 include 旁支跨 TU，导致链路预算提前耗尽。现按 invocation/configuration 索引邻接，并只遍历该作用已证文件范围的 include；新增隔离与真实 16 TU 回归。32 TU 的 2048 个原始实参 Finding 已逐条核验 complete、high、Makefile 上游和 TU 隔离；旧失败规模报告保留，不当作通过。
- `unit-11`：783 项、0 失败/错误，183 个自有源码文件；整体行 **98.660842%**、分支 **95.572546%**，所有登记及受影响模块 ≥90/90，`failedCoverage={}`。无分支模块的 branch 为 null/不适用。报告：`.codex-tmp/macro-build-effects-20260924/unit-11/{summary.json,coverage.json,html/}`。
- `regression-02`：268 项真实解析/CLI 回归全部通过（406.392 秒）；数量变化来自去掉新组件模块里重复导入的已有测试类，不删除原断言。最后源码链邻接优化后的最终回归仍另跑，不能用本轮代替。
- 测量均复用现有 `tests.run_usage_scale_tests`、`tests.source_chain_benchmark`、`tests/run-performance-container.ps1`，未新增或修改测量驱动，不新增宿主依赖。

### 增量语义审校

固定旧 scanner `44c756f` 通过 `git archive` 提取到独立容器 `/tmp`，输入路径/镜像保持一致，未修改当前 checkout。旧、新 V1/V2 工件在 `.codex-tmp/macro-build-effects-20260924/differential/{before,after}/`。

- source-evidence-chain：V2 只改变两条 Finding 的源码链，以及 intrinsic 的作用 occurrence/configuration/primaryOccurrenceId 和宏作用扩展；结论、summary、用途审计、日志不变。V1 仅 trace 增补来源。真正的 `$(CPPFLAGS)` 使用点不再丢失，知识旁支与 20/20 合同保持。
- AVX：828 条 Finding、规则分布、严重度、建议、blocking/actionable 和 diagnostics 保持。V2 JSON 完全一致（`659034777b7b54992ff115fa7af9b38aeebd6d543c60589314a0e3aa92f997c4`）。V1 仅 12 条宏 Finding 与汇总 trace 加入原始实参/作用关系。
- 新增固定账本 `tests/fixtures/macro-build-effect-report-differential.json`；未涉及样例继续使用旧精确摘要，原 compiler facts、原 schema 文件和 V2 核心模型均未修改。
- libarchive 对历史 round51 的审校：64 条（53 issues/11 hints）不变。`archive_ppmd_private.h` 的 MY_CPU_X86 定义及 `defined(MY_CPU_X86) || defined(_M_ARM)` 两个候选由 `candidate-evidence-not-sufficient` 更精确地记录为 `input-or-relation-unknown`，仍为 medium/unknown、非 blocking、双语建议不变；由此两条 Finding ID 改变。另一个 MY_CPU_X86 使用的链路增补未知来源，仍为 unknown。未把未知平台宏证明成 RISC-V 支持或执行，也没有删除 26 项历史数据用途候选。其余共同 ID 的结论未变；全部最终字段摘要在最终性能验收后补记。

### 复验命令（工作目录 D:/projects/RvPort/tools/kb-scanner）

以下 Python 命令均在独立镜像内运行；宿主只运行 Docker/PowerShell/OpenSpec/Git 只读操作。通用限制为 `--cpus 2 --memory 2g --memory-swap 2g --network none --read-only`，scanner/fixture 只读挂载，输出单独可写挂载，未运行项目代码或重建生产镜像。

```text
python tests/run_source_chain_unit_tests.py --output /output
python tests/run_container_tests.py --regression-only
python -m unittest tests.test_macro_build_effect_component -v
python -m tests.run_usage_scale_tests --output /output/usage
timeout 300 python -m tests.source_chain_benchmark /fixtures/16 /output/16-accepted
timeout 300 python -m tests.source_chain_benchmark /fixtures/32 /output/32-accepted
timeout 300 python -m tests.source_chain_benchmark /fixtures/32 /output/32-final --instrument
```

上面的 `python -m unittest ...` 是真实解析组件入口，与隔离单元覆盖统计分开。

宿主性能入口为：

```powershell
./tests/run-performance-container.ps1 -Source 'D:/projects/RvPort/.codex-tmp/kbscanner-sources-clean-20260909/libarchive' -Output 'D:/projects/RvPort/.codex-tmp/macro-build-effects-20260924/libarchive-07-serial' -FixtureDir tests/fixtures/candidate-usage-performance
openspec validate improve-kb-scanner-macro-and-build-effect-proofs --strict
```

输出目录必须使用新路径，不能覆盖历史工件。临时 16/32 TU 输入位于 `.codex-tmp/macro-build-effects-20260924/macro-scale-inputs/`（已在 ignore 范围），人工预期分别为 1024/2048 个独立 intrinsic 实参位置，输入不运行构建。

### 最终功能验证与规模样例

- 最终源码完整回归 `regression-03.log`：**269 项全部通过，420.385 秒**（这是整套测试耗时，不是单项目扫描）；包含三个固定上游原生崩溃样本、AVX、CMake demo、源码链、枚举、家族、多版本、用途、RPM/Autoconf。
- 最终真实 cJSON：108 文件/8 Findings，exit 0，峰值 172888 KiB；zlib：127 文件/24 Findings，exit 0，峰值 189284 KiB，三工件齐备，无原生崩溃。报告在 `real-projects/{cJSON-final,zlib-final}/`。真实工程扫描与原生缩减样本回归分开记录，不重复计算测试数量。
- 最终业务源码摘要（性能工具的规范 JSON 算法）：`df9a867e4b57935d8464d27e991d1d7750c590cee74e73e0246094b6b0d5d5fe`；用途规模驱动使用另一 JSON 空格格式，其摘要为 `1971d25d6678eba13a35194a15060b3d21d94ad6c4668fdaa0fea16b53283070`，最终核对源码文件清单，不能直接比较两种序列化的摘要。

宏规模使用相同固定代码和预算，非 instrument 扫描均在 300 秒 timeout 内正常结束：

| 样例 | 输入摘要（文件名→SHA-256 的紧凑 JSON） | 采集/归一化/分析/报告秒 | RSS KiB | JSON/HTML/log 字节 | 语义验收 |
| --- | --- | --- | --- | --- | --- |
| 16 TU，18 文件 | `160b07b077724b4e719d009f64f23de4df0c6115fdd410bcba4141290bd942ae` | 0.769 / 0.165 / 1.995 / 10.034 | 188000 | 53112401 / 1318025 / 106797 | 1024 Findings，全部 complete/high，8192 条展示中的作用边 |
| 32 TU，34 文件 | `e09ed0444166b8a835300a98e63708babd1c6b0168cbf76bc17e0d81b413b480` | 1.308 / 0.203 / 3.085 / 26.066 | 313916 | 107650257 / 2635689 / 213181 | 2048 Findings，全部 complete/high，16384 条展示中的作用边 |

逐条断言原始行的 `[startColumn-1:endColumn-1]` 恰为 `_mm256_add_epi32`、位置不重复、每段 primaryPath 有实际边、起点为 Makefile、所有源码属于当前 TU/shared.h/Makefile。并非只校验数量。

独立 32 TU instrument 诊断：源码索引 1 次/0.454 秒；查询 2048 次/6.574 秒，32768 visits、28672 paths；context 8327 次/1.162 秒、4231 个唯一 span、34 次文件读取拆行。业务 Analyzer 2.664 秒包含环境/作用索引及其他图分析，不冒充纯索引时间；报告 16.082 秒包含投影、校验、发布。每条源码查询 16 visits/14 paths，未触及原 256/32 限制。没有实现跨配置宏结果缓存，不虚报该缓存命中率；文件/源码上下文缓存由上述唯一计数验证。

`libarchive-06` 在多组大测试并发时于报告阶段前达到 300 秒，无 OOM；前端/归一化/分析分别 104.31/41.20/127.83 秒，高于已通过轮次的 92.27/34.54/111.75。保留失败工件，不据此放宽门槛。减少本任务的大型并发后以 `libarchive-07-serial` 新输出目录复验；目录名只是标签，首轮早段仍与用途矩阵最后一项有短时重叠，最终记录以实际资源与两轮完成数据为准。

### 最终用途规模矩阵

`scale-accepted/usage/summary.json` 已完成 **4 组/8 次**，passed=true（不能以中途仅 3 组的临时 passed 字段当作全部完成）。源码清单逐文件与当前 178 个 scanner Python 文件一致；固定资源为 2 CPU/2 GiB/无 swap。 compact 基线追加在 `tests/fixtures/macro-build-effects/scale-baseline-20260924.json`，保留每阶段、工件字节、预算计数；不替换旧用途基线。

| 引用数/密度 | 关闭/开启秒 | 开启峰值 KiB | 开启截断根数 |
| --- | --- | --- | --- |
| 10000 稀疏 | 14.79 / 20.79 | 275768 | 0 |
| 10000 密集 | 91.92 / 76.99 | 808952 | 1788 |
| 20000 稀疏 | 24.47 / 28.83 | 363724 | 0 |
| 20000 密集 | 169.97 / 177.36 | 1332416 | 14928 |

密集场景的截断是既有全扫描查询访问预算行为：全部预期候选根仍被采集，超限根保持 unknown 和截断原因，不能当作排除；原 acceptance 同时核验数量、预算与完整报告，不为通过关闭 producer。相对耗时只作诊断，绝对 300 秒/2 GiB 门槛不变。

### 最终 libarchive 门禁与边界复核

`libarchive-07-serial/benchmark/performance.json`：两轮 **256.3096/248.3001 秒**，exit 0、无 OOM，峰值 **1275192/1272092 KiB**；两轮 semanticDigest 同为 `c544b2a4fee73e2a7798e868bfa534177ad07222090fba1d0d879da587248c43`。三工件与本轮已逐字段审校的 libarchive-04 完全一致。追加 [libarchive 审校与性能基线](../../../../tests/fixtures/macro-build-effects/libarchive-review-20260924.json)，旧输入清单和审校不覆盖。

另确认聚合诊断减少一项的具体原因：`libarchive_fe/lafe_setmode.c:59–60` 的注释含 `#`，旧 macro lexer 错当字符串化；真实 grammar 分别替换旧/新 lexer 对照后，旧有 stringification 警告，新无，comment 原文仍保留。补入隔离单元回归，不改变 compiler facts。

补齐该回归后的最终 `unit-12`：**784 项、0 失败/错误，passed=true**；统计全部 183 个自有生产源码文件（含未加载源码），整体行 **98.668003%**、分支 **95.590327%**，所有登记及受影响模块均达 90%/90%，`failedCoverage={}`；无分支模块标为不适用。报告位于 `D:/projects/RvPort/.codex-tmp/macro-build-effects-20260924/unit-12/{summary.json,coverage.json,html/}`。本轮只补单元测试，业务源码与最终完整回归、规模及 libarchive 验收使用的版本一致。

最终 strict OpenSpec、JSON 内容校验、scanner 范围 `git diff --check` 通过。Schema 文件、V2 核心模型、两份 compiler facts 未改；未运行被扫描项目、未安装宿主依赖、未重建生产容器，未提交或推送。临时输入/报告留在已忽略的 `.codex-tmp` 供回顾。下一阶段是同步主规格并归档当前 change。

### 同步与归档（2026-09-24）

按用户授权，先将 5 份 delta 中的 11 条新增要求同步至对应主规格，并逐字核对原要求保留、新增要求完整且不重复。`openspec validate --specs --strict --no-interactive` 为 18 passed / 0 failed，当前 change strict 校验通过，24/24 任务完成。随后在 `D:/projects/RvPort/tools/kb-scanner` 执行 `openspec archive improve-kb-scanner-macro-and-build-effect-proofs --skip-specs --yes`；`--skip-specs` 仅避免重复应用已经同步的要求，并非跳过同步或校验。CLI 关于超过 10 条 delta 的拆分建议为非阻断提醒。

归档目录为 `openspec/changes/archive/2026-09-24-improve-kb-scanner-macro-and-build-effect-proofs/`，保留 `.openspec.yaml`、所有任务及验收记录；开发计划和相对链接已同步。本阶段仅修改规格与文档，不更改实现或测试，不重新运行代码覆盖率；本 change 流程结束，未提交、推送或部署。

### 提交前复验（2026-09-24）

收到单独 commit/push 授权后，以同一独立测试镜像、2 CPU/2 GiB/无 swap、只读挂载和禁网限制，重新运行 `python tests/run_source_chain_unit_tests.py --output /output`。784 项单元测试通过，183 个自有生产文件（含未加载源码）整体行 98.668003%、分支 95.590327%，受影响模块门槛全部通过；排除范围不变。报告保留在 `D:/projects/RvPort/.codex-tmp/macro-build-effects-20260924/commit-unit/{summary.json,coverage.json,html/}`。此次未重跑已完成的完整回归和性能矩阵；仅追加本复验记录，不修改生产代码或历史审校。
