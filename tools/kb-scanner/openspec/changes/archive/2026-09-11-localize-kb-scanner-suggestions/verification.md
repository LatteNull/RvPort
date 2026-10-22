# 双语建议实施验收记录

## 已冻结基线

- 2026-09-11，scanner 基线沿用源码链交付后的实现；冻结时仓库 HEAD 为 `363d9fa123c37e957585011d3b623e28d797b098`，其他任务的 backend 等改动不在范围。
- 独立镜像 `rvport-kb-scanner-test:local`，ID `sha256:6239c14ed91b006edb5e6298348deb19cd60f87aa9b3bb85043db35767e5e05a`。复用镜像，不安装本机依赖、不更新生产服务。
- 固定输入为 `tests/fixtures/{architecture-candidate-noise,source-evidence-chain,architecture-enum,rpm-architecture}`，分别冻结 V1/V2 的三个 artifact，源目录只读、无网络、无特权。
- 持久本地目录：仓库根 `.codex-tmp/localize-suggestions-20260911/before`；`freeze.py` 为本次容器审校辅助，产物和辅助脚本不提交。
- Clang SHA-256：`adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7`。
- GCC SHA-256：`89775341ee880b13ac4f10a30558ff5d52875b25a3233114a5765601f0a9dad9`。
- 旧 V2 suggestion 只有两个英文模板，HTML 直接显示该字段，V1 中英字段已存在。差异允许清单仅为 V2 conclusion.suggestion 与 suggestion_en；其他 JSON 字段、V1、scan.log 和知识哈希不得改变。

## 实施内容

- 新增 V2 纯展示 `suggestions.py`，按已有 impact/status/findingType 选取七组成对中英文模板，未知类型保守兜底。mapper 不重扫或重新分类。
- Conclusion 将历史缺省与显式非法英文值分开；projector 发布前调用 producer 专用双字段非空校验。复用现有 HTML/JSON/log renderer，无需修改 renderer 业务代码。
- Schema/vocabulary、隔离单测、机器可读模块 inventory、组件合同、新 golden 及消费者迁移说明已更新。旧样例和旧账本不改写。

## 单元测试与覆盖门槛

独立容器执行 `tests/run_source_chain_unit_tests.py --output /out/after-unit`：493 项隔离单测全部通过。基线 481 项全部通过，整体为 97.82% 行 / 93.36% 分支；本次结果如下：

| 统计范围 | 行覆盖率 | 分支覆盖率 |
| --- | --- | --- |
| 整体 129 个源码文件 | 97.83% | 93.40% |
| `projection/v2/suggestions.py` | 100% | 100% |
| `projection/v2/mapper.py` | 96.51% | 100% |
| `projection/v2/models.py` | 100% | 100% |
| `projection/v2/projector.py` | 100% | 100% |
| 复用 `projection/v2/renderers.py` | 100% | 100% |
| 复用 `projection/v2/validation.py` | 98.11% | 97.30% |

整体命中 9464/9674 行、3394/3634 分支；本次受影响模块全部超过 90% 行/90% 分支门槛，原有其他逐模块门槛也通过。上述模块均存在分支，没有将无分支记作满覆盖。统计范围保留全部 `kb_scanner/`、`scripts/`、`tools/`，包括未加载文件和仍在运行包中的 Legacy；没有缩小分母或增加 pragma 排除。

排除项仅为测试/fixture/测试 runner、非部署归档、非可执行 rulesets 事实数据及容器第三方依赖。隔离门禁 fake 原生 C/C++、Make、RPM shell 解析；排除的九个真实解析/跨阶段用例在 summary 中逐项记录，组件结果不抵充单元覆盖。mapper 使用 fake index/chain/context，producer 使用 fake mapper/publisher，建议策略本身无 I/O。

持久报告（本地审校产物，不提交）：

## 合同与回归

- `tests.test_bilingual_suggestions` + `tests.test_schema_v2_design_contract`：18 项通过。涵盖真实 JSON Schema/引用合同、历史英文缺省、显式非法值、固定 snapshots 的 partial/ambiguous/阻断/构建选择/测试缺口、四组真实输入及默认/en-US locale 对照。
- `--schema-v2-projection-unit`：86 项通过，该历史辅助 gate 输出 99.37% 行 / 98.13% 分支。
- `--architecture-enum-unit`：129 项通过，该历史辅助 gate 输出 96.15% 行 / 89.76% 分支。它采用自身历史范围与门槛，包含真实解析组件，不作为本次 90/90 隔离验收依据；本次必达数字见上表及 scanner-wide summary。
- `--candidate-semantic-admission-unit`：480 项通过。
- `--regression-only`：225 项全部通过（248.468 秒），包含 AVX、RPM、枚举、候选、V1、源码链、cJSON/zlib/libarchive 原生崩溃等完整回归。

以上历史辅助门禁未被替代或降低；本次新增模块登记到默认调用的 scanner-wide 90/90 gate。持久日志位于 `.codex-tmp/localize-suggestions-20260911/{contracts,schema-unit,enum-unit,candidate-unit,regression}.log`。

## 差异账本

八次 before/after 扫描完成，四组输入分别为候选噪声、源码链、架构枚举和 RPM。删除两个建议字段后所有 V2 字段全等，包含 ID、fact、conclusion 其他字段、occurrences、链/源码 ±20 行上下文、summary 和 diagnostics。V2 HTML 仅建议段落变化；V1 三份 artifact、全部 scan.log 和两份编译器 JSON 字节相等。

[新账本](../../../../tests/fixtures/bilingual-suggestions/report-differential.json) 固化每组 before/after/stripped/log 哈希及编译器哈希，组件测试持续复核。候选样例规范化 V1 哈希仍为 `cb90bf06ce580eff26a51b4fac56120a7c79524f3f61b95fe0e495d0b3c4c0b0`；V2 从 `14a9c04f7031c45f2cb556fa0986f29f8662eb870f01541c47b73a8b6c16f5b5` 变为 `8bdd9fdb0a878a26d69f6c42085f2963010b9b041754ecb98a125e8213fb1c64`，仅获准建议差异造成。旧 golden 未覆盖。

## 可重复执行命令

宿主 PowerShell，工作目录 `D:/projects/RvPort/tools/kb-scanner`；已有镜像直接运行，不安装本机依赖、不构建镜像、不调用 Compose：

```powershell
$kbDocker = @(
  '--rm', '--network', 'none', '--read-only',
  '--tmpfs', '/tmp:size=512m,mode=1777', '--cap-drop', 'ALL',
  '--security-opt', 'no-new-privileges:true',
  '--mount', 'type=bind,source=D:/projects/RvPort/tools/kb-scanner,target=/workspace/tools/kb-scanner,readonly',
  '--mount', 'type=bind,source=D:/projects/RvPort/.codex-tmp/localize-suggestions-20260911,target=/out',
  '--mount', 'type=bind,source=D:/projects/RvPort/backend/runtime/kb-scan-real/avx-avx2-example-code,target=/fixtures/avx-avx2-example-code,readonly',
  '--workdir', '/workspace/tools/kb-scanner',
  '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONPATH=/workspace/tools/kb-scanner'
)
docker run @kbDocker rvport-kb-scanner-test:local tests/run_source_chain_unit_tests.py --output /out/after-unit
docker run @kbDocker rvport-kb-scanner-test:local -m unittest tests.test_bilingual_suggestions tests.test_schema_v2_design_contract
docker run @kbDocker rvport-kb-scanner-test:local tests/run_container_tests.py --schema-v2-projection-unit
docker run @kbDocker rvport-kb-scanner-test:local tests/run_container_tests.py --architecture-enum-unit
docker run @kbDocker rvport-kb-scanner-test:local tests/run_container_tests.py --candidate-semantic-admission-unit
docker run @kbDocker rvport-kb-scanner-test:local tests/run_container_tests.py --regression-only
openspec validate localize-kb-scanner-suggestions --strict
git diff --check -- .
```

本次实际调用使用同一组隔离参数，并将各测试 stdout/stderr 写入上述 `/out/*.log`。冻结/逐字段比较用 `/out/freeze.py /out/before`、`/out/freeze.py /out/after`、`/out/compare.py`；这些一次性审校辅助脚本随本地报告保留，不属于生产代码。

## 范围与交接

消费者升级顺序及历史省略语义见 [迁移说明](../../../../docs/schema-v2-design.md)。本次没有运行被扫描项目的构建或测试，没有修改 backend/frontend、生产容器、Compose 或其他 thread 的文件。实施交付时未同步/归档、commit/push 或部署；归档操作见下方后续记录。

`openspec validate localize-kb-scanner-suggestions --strict`、scanner 范围的 `git diff --check` 及变更 Markdown 本地链接/尾随空白检查均通过。18 项实施任务完成；实施阶段交接指向同步 delta specs 并归档，而不是继续实现或部署。

## 同步与归档记录（2026-09-11）

按用户授权，已将 5 条新增要求和 1 条修订要求同步到 `openspec/specs/kb-scanner-report-schema-v2/spec.md`，其余要求与场景保留。change 与主规范分别通过 OpenSpec 严格验证后，完整移动 6 个文件到本归档目录，移动前后文件哈希一致，并保留 `.openspec.yaml`；随后仅修正本记录的相对链接及归档状态。

本阶段仅同步规范、归档文档并校验格式/链接，没有修改可执行代码，未重跑单测，代码覆盖率不适用于此次文档操作；实施验收结果保留如上。未 commit/push、部署或改动其他 thread 的文件。本 change 的 OpenSpec 流程结束，无待执行下一阶段命令。
