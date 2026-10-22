# 实施验证记录

实施验收日期：2026-09-22。范围仅 `tools/kb-scanner`；实施验收时尚未同步、归档、commit、push 或生产部署。后续流程状态见文末记录。

## 实现结果

- 复用授权清单/source file 身份，新增路径观察、局部家族分桶与非执行成员边；不新增代码 Evidence、不重扫目录。
- 支持同目录角色前后缀、镜像架构目录、unlabelled/foreign 上下文、大小写/多槽位歧义与稳定预算。仅 x86 锚定家族进入输出。
- 复用已有 source selection proof，核对端点、有效 Evidence、configuration、连续路径和完整性；不重新搜 proof、不制造 alternative_to。
- 通过现有 V2 namespace extension 提供顶层目录及单 Finding 自包含候选，新增双语解释和 HTML 中文摘要。没有位置的路径不生成假行号或命中，不改变核心 schema/V1。
- 候选不增加迁移 Finding、不影响已有风险/阻断/评估；纯路径家族在没有 Findings 时仍可见。

实现细化：现有 C++ Frontend 已为所有授权源码创建 source file 实体，故 inventory adapter 只附加元数据，不重复创建实体。成员/家族使用 scanner-owned 结构记录，借现有 Entity properties 传递；没有扩展公共模型字段。对外绑定来源采用路径/行号描述，不导出在 Finding 内无法闭合的内部 proof/relation ID。Autoconf 没有 source membership proof 的赋值保持 unknown，不借该 change 扩大 Shell 语义。

## 环境与实际命令

复用已停止的 `kb-scanner-cmake-verify` 独立测试容器，镜像为既有 scanner 测试镜像；工作区及真实 AVX fixture 只读挂载，network=none、输出位于 /tmp。未安装本机依赖、未构建生产镜像、未启动根 Compose。

从仓库根执行：

```text
docker start kb-scanner-cmake-verify
docker exec kb-scanner-cmake-verify python tests/run_source_chain_unit_tests.py --output /tmp/architecture-family-baseline-coverage
docker exec kb-scanner-cmake-verify python -m kb_scanner scan --input tests/fixtures/cmake-demo-test1 --rules rulesets/riscv-porting --output /tmp/architecture-family-baseline-demo
docker exec kb-scanner-cmake-verify python tests/run_source_chain_unit_tests.py --output /tmp/architecture-family-final-coverage
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_architecture_family tests.test_architecture_family_component
docker exec kb-scanner-cmake-verify python tests/run_container_tests.py --regression-only
docker exec kb-scanner-cmake-verify python -m tests.architecture_family_performance --output /tmp/architecture-family-performance-final
```

最后新增组合管线上游失败短路测试后，最终隔离门禁再次执行；定向命令最终为 14 项新单元 + 6 项组件测试，共 20 项通过（7.319 秒）。14 项新单元均纳入下述 573 项门禁。

在 `D:/projects/RvPort/tools/kb-scanner` 执行：

```text
openspec validate implement-kb-scanner-architecture-family-analysis --strict
```

## 测试和覆盖率

| 检查 | 结果 |
|---|---|
| 修改前隔离基线 | 559 项通过；行 98.0082%，分支 93.9550%，142 个自有源码文件 |
| 最终隔离门禁 | 573 项通过；行 98.0807%，分支 94.1621%，149 个自有源码文件 |
| 完整回归 | 244 项通过，275.509 秒，含当时 5 项新增组件测试 |
| 新增组件最终定向复验 | 6 项全部通过，含随后补充的根外软链接反例；不与完整回归重复累计 |
| OpenSpec 严格验证 | 通过 |
| 已跟踪/新增文件空白格式检查 | 通过；Git 的 LF→CRLF 提示是现有换行策略，不是内容错误 |

中间测试发现并修正了旧 mapper fake 缺少 entities 字段、V1 测试比较不同临时目录导致差异，以及组合管线原有失败分支单测不足。未降低覆盖门槛或改写业务期望来通过测试。

覆盖统计纳入全部自有 `kb_scanner/`、`scripts/`、`tools/` 可执行代码，包括未加载模块。排除测试/fixture/runner、未部署 archive、生成规则 JSON 和容器中第三方依赖；没有排除自有业务逻辑。原生 parser 和完整 CLI 组件测试不计入隔离单元门禁。

受影响模块门禁：

| 模块 | 行 | 分支 |
|---|---:|---:|
| frontends/family_inventory.py | 100% | 100% |
| analyzers/architecture_family/paths.py | 100% | 100% |
| analyzers/architecture_family/grouping.py | 100% | 100% |
| analyzers/architecture_family/bindings.py | 100% | 100% |
| analyzers/architecture_family/analyzer.py | 100% | 100% |
| analyzers/architecture_family/__init__.py | 100% | 不适用：无分支 |
| pipeline/composite.py | 100% | 100% |
| projection/v2/families.py | 100% | 100% |
| projection/v2/mapper.py | 96.7742% | 100% |
| projection/v2/projector.py | 100% | 100% |
| projection/v2/renderers.py | 100% | 100% |

## 差异审校

- 同一输入开/关家族 Analyzer 的 demo、真实 AVX、family-demo 报告：仅剔除本次家族 extension 后，其余 JSON 完全一致；没有用 Finding 数量相等替代字段对比。
- 修改前独立保存的 demo JSON 与最终 demo JSON 字节相同（PowerShell 原始文本比较）；该项目路径没有匹配家族模板，不产生额外 extension。
- 新家族示例形成 1 个 family、2 个成员；generic 对目标 selected，x86 对目标 inactive，均有 CMake 源位置。`alternativeStatus` 仍为 unknown，不声称两份函数行为等价。
- 真实 AVX 本轮得到 0 个家族，这是首版局部模板的实际结果，不是已经证明无替代。原有人工审校事实、结论和源码链保持不变。
- V1 差异测试只规范化两个临时工作区的绝对根路径，所有其他字段一致。
- 默认 V2 自包含链、双语建议、±20 行、已有 namespace 共存、HTML 转义、空文件、解析恢复、排除项和根外软链接均有测试。
- 完整回归含固定 libarchive、zlib、cJSON 缩减 fixture 与既有审校样例；不宣称重新全量扫描或构建三个远端仓库。

## 性能

合成分桶测试开启 tracemalloc，统计的是分组阶段分配峰值，不是全进程 RSS：

| 路径数 | 家族数 | 分桶操作数 | 时间 | 峰值分配 |
|---:|---:|---:|---:|---:|
| 10000 | 5000 | 10000 | 1.009 秒 | 14844644 bytes |
| 20000 | 10000 | 20000 | 2.249 秒 | 31076114 bytes |

未出现全量两两枚举。真实项目样本的新增家族 Analyzer 耗时分别为 demo 0.000263 秒、AVX 0.000918 秒、family-demo 0.000659 秒，均未触及“超过基线 10% 且超过 1 秒”的该步骤调查阈值。

完整扫描单轮时间为 demo 2.967→2.578 秒、AVX 13.609→15.493 秒、family-demo 1.142→0.949 秒。单轮全链路时间存在抖动，不把这些数字当作稳定加速/减速结论；测试输出同时保留总时间与家族阶段时间，不隐藏 AVX 总时间增加。

## 工件与不变资产

报告根：`D:/projects/RvPort/.codex-tmp/kbscanner-architecture-family-20260922/`（Git 忽略）。

- `architecture-family-final-coverage/summary.json`、`coverage.json`、`html/index.html`：完整单元/覆盖率门禁。
- `architecture-family-baseline-coverage/`、`architecture-family-baseline-demo/`：修改前基线。
- `architecture-family-performance-final/performance.json`：操作计数和性能。
- `architecture-family-performance-final/family-demo-family/scan-report.html`、`scan-result.json`：可查看的候选家族示例。
- 同目录 demo/avx 的 baseline/family 子目录：逐字段差异检查的输入输出。

容器输出位于 tmpfs，Docker cp 无法直接读取该挂载内容；已经通过容器 tar 流导出并在宿主核对 summary 和示例 JSON。没有为导出重建容器。

两份编译器事实 SHA-256 不变：

- clang：`adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7`
- gcc：`89775341ee880b13ac4f10a30558ff5d52875b25a3233114a5765601f0a9dad9`

实施阶段未修改、未暂存其他任务的 `tools/memory-order-analyzer/openspec/changes/expand-thread-entry-discovery/`。所有实施变更仅属于本 change；同步归档、提交推送或部署均需后续明确授权。

## 同步与归档记录（2026-09-22）

用户明确授权先同步再归档后，将 9 条新增要求同步到 4 份主规范：新增架构家族分析规范（5 条），分类评估（1 条）、证据图（1 条）和 V2 报告（2 条）追加要求。既有要求保持不变。

在 `D:/projects/RvPort/tools/kb-scanner` 执行归档前校验：

```text
openspec validate implement-kb-scanner-architecture-family-analysis --strict --no-interactive
openspec validate --specs --strict --no-interactive
```

change 严格校验通过，16/16 份主规范通过，21/21 项任务完成。归档目录为 `openspec/changes/archive/2026-09-22-implement-kb-scanner-architecture-family-analysis/`；移动前后逐文件 SHA-256 一致，包括 `.openspec.yaml`，随后补充本记录与文档链接。

本轮仅同步规范、归档及更新文档引用，没有修改可执行代码，因此未重跑容器测试，覆盖率不适用于本轮文档操作；上文保留的是实施阶段实际验收结果。未 commit、push 或部署，未改动其他任务文件。此 change 的 OpenSpec 流程结束。
