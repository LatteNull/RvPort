# 实施与验证记录

## 2026-09-24：规范同步与归档完成

用户授权后使用 openspec-sync-specs 合并 5 项 capability（新增候选用途规范、更新其余 4 份），共新增 11 条 Requirement、修订 3 条，保留未涉及的旧要求。18 份主规范及归档前 change 的 strict 校验全部通过，25/25 任务完成。归档路径为 `openspec/changes/archive/2026-09-24-implement-kb-scanner-candidate-usage-proofs`；移动时核对全部 10 个文件哈希一致，包含隐藏的 .openspec.yaml，随后仅修正本记录相对链接并追加此状态说明。文档同步更新归档路径，不改变历史测试、失败记录和源码。本轮仅文档/规范操作，代码覆盖率不适用，未重新执行代码测试；既有验证记录保留。未提交、推送或部署，OpenSpec 流程结束。

阅读顺序：本文件保留历次失败与修复记录；以顶部最近轮次为准。下文旧轮的“最新”“待确认”和旧相对门槛是当时状态，不覆盖 2026-09-23 用户已批准候选驱动采集及 2026-09-24 已批准性能验收调整这两项决定。

## 2026-09-24：新增功能成本与同功能回归分开验收

用户确认“新增扫描功能允许合理增加索引时长”，并同意继续按讨论后的验收口径执行：开关 producer 的总耗时差与旧 10% 且 1 秒判定只作诊断，不再单独否决；每个独立扫描仍须在 2 CPU/2 GiB/无额外 swap、300 秒内正常完成，不得 OOM。候选/事实、预算、三工件、功能和 90% 行/分支质量门槛不变。不实施此前待确认的紧凑共享用途表跨模块重构。

本轮 scanner 业务源码未改；仅调整规模验收驱动、补充隔离单测和更新文档。驱动保留 4 组共 8 次独立子进程、总耗时/CPU/RSS/工件大小/所有阶段记录，另记录用途 Analyzer（索引与查询合计）耗时。该值不是纯索引构建时间，也不等于整个 analyzer 或扫描总耗时。验收检查候选总量、用途统计、一次一作用域索引上限、记录/访问预算和工件/计时完整性；子进程失败不被已有 metrics 的成功码覆盖。

round53 使用固定逻辑 CPU 0/1，完整执行新矩阵；只读挂载当前 scanner、写入新目录 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260924/round53-scale/`，不覆盖以前轮次。**四组八次扫描全部通过新验收**，退出码均 0，容器 OOMKilled=false，2 CPU/2 GiB/无 swap；每次扫描 <300 秒。该容器已移除，所有输出保留。

| 引用数/需求 | 关闭（秒） | 开启（秒） | 开启峰值 KiB | 旧相对门槛（仅诊断） |
| --- | ---: | ---: | ---: | --- |
| 10000 稀疏 | 13.218475 | 18.410323 | 271972 | 未通过，+39.28% / +5.19 秒 |
| 10000 密集 | 85.315991 | 60.900881 | 807420 | 通过，-28.62% / -24.42 秒 |
| 20000 稀疏 | 22.412241 | 25.188875 | 357328 | 未通过，+12.39% / +2.78 秒 |
| 20000 密集 | 155.689511 | 203.702571 | 1325760 | 未通过，+30.84% / +48.01 秒 |

不是把旧失败改成成功：原策略下仍有三项不通过，新策略接受功能不同的成本差异，同时独立检查资源和完整性。工作量核查：

- 稀疏 10000→20000：根 96→192、作用域索引 4→8、记录 644→1288、访问 12288→24576；候选数与原始生成规模对应，全部 96/192 个纯局部候选经证明排除，原事实保留。
- 10000 密集：9600 根，400 个作用域索引，64400 条查询记录，访问正好停在 1000000 次上限；7812 个排除、1788 个保留并标截断。
- 20000 密集：19200 个候选全保留，0 排除，14928 根标截断；采集预算不完整的作用域不启动无效闭包，索引/查询记录/访问统计为 0，不代表没有原始 inventory。该轮 frontend/normalizer 仍各有 41422 Evidence/Fact。
- `tests.unit.test_usage_session`、`test_usage_closure`、`test_usage_frontend` 等已有并本轮重跑的单元验证索引复用、同配置精确根、无需求快速路径、预算截断保留事实，以及查询间不共享错误结论。预算没有调整。

分阶段结果：开启组的用途 Analyzer 分别为 0.285387/18.157974/1.053590/2.984942 秒，包含需求、索引、查询及证明处理，不能称为纯索引构建时间。20000 密集组总报告投影 165.138014 秒，其中 Finding 构建 48.025118、引用校验 14.036408、发布 100.633726 秒；JSON 2576262790 字节、HTML 53228159 字节、log 2006058 字节，未减少 Finding、源码 ±20 行或工件内容。嵌套阶段不能重复相加。10000 密集因真实排除使输出更少，而 20000 密集触发采集预算后全量保留，因此两组总时长比不能单独用于推断索引复杂度。

同功能新基线保存于 [usage-scale-baseline-20260924.json](../../../../tests/fixtures/candidate-usage-performance/usage-scale-baseline-20260924.json)，含全部业务源码文件哈希、资源配置、阶段计时、计数、输出大小及开关差值。完整 runtime/summary/metrics/events/三工件在 round53-scale；不是任意输入均在 300 秒内的承诺。旧 822/810 文件清单、审校 ledger、所有失败轮次保留。

业务源码 compact digest 为 `4ffedfca055220bb8d62b3ae515e7a60352687eb86e7bb502a3dad58b94a9692`，与 round51 一致；规模驱动的空格 JSON 编码 digest 为 `93783417800d23afb48cecda97ff96ebaaec230c16ffa3d6c734dba3855c03c2`，两者只因 JSON 编码方式不同。核对运行前文件哈希与运行后工作区全部一致。镜像仍为 `sha256:394ff7dcfb096cb5e9479ff5fd06e10d1c3756b89f302d616decf83819d9ae0c`。因此同业务版本 round50 的 261 项回归、round51 libarchive 两轮及逐字节审校结论仍有效，本轮未声称重新执行它们。两份 compiler facts 哈希与文末冻结值一致。

round54 在规模扫描结束后串行重跑全量隔离单元：**735 项通过，23.192 秒**，174 个自有源码文件（含未加载的 kb_scanner/scripts/tools），整体行 **98.56191341204965%**、分支 **95.29054310672237%**，所有登记模块均 ≥90%/90%，failedCoverage 为空。报告 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260924/round54-unit/{summary.json,coverage.json,html/}`。不部署 archive、第三方、生成规则数据和测试资产不计入业务源码分母，与原 inventory 相同，未缩小统计范围。

round55 单独度量本轮修改的测试基础设施：10 项隔离测试全部通过（2.325 秒），`tests/performance/usage_acceptance.py` 行/分支 **100%/100%**，`tests/run_usage_scale_tests.py` **93.7007874015748%/95.83333333333333%**。两个模块均完整统计，无额外排除；测试正常/阈值边界、旧门槛诊断、缺指标/工件/用途、错误候选数、超预算、子进程失败/超时、完整 8 次运行及 fake 渲染，不执行真实 parser/扫描进程。报告位于 `.../round55-harness-unit/{coverage.json,html/,console.log}`。本组 10 项已包含在 735 项中，不重复累计。

执行命令（工作目录 `D:/projects/RvPort/tools/kb-scanner`；性能复跑必须选新输出目录，本轮容器均单独启动，不与生产服务或本任务其他测试共享）：

```powershell
# round53：先创建独立输出目录，create/start 后检查 State，再只移除本次容器。
docker create --name kb-usage-scale-20260924-r53 --cpus 2 --cpuset-cpus 0,1 --memory 2g --memory-swap 2g --network none --read-only --tmpfs /tmp:size=512m --cap-drop ALL --security-opt no-new-privileges --mount 'type=bind,source=D:/projects/RvPort/tools/kb-scanner,target=/workspace/tools/kb-scanner,readonly' --mount 'type=bind,source=D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260924/round53-scale,target=/output' rvport-kb-scanner-test:local -m tests.run_usage_scale_tests --output /output/benchmark
docker start --attach kb-usage-scale-20260924-r53
docker inspect kb-usage-scale-20260924-r53 --format '{{json .State}}'
docker rm kb-usage-scale-20260924-r53

# round54：全业务源码单元覆盖，输出目录提前创建。
docker run --rm --cpus 2 --memory 2g --memory-swap 2g --network none --read-only --tmpfs /tmp:size=512m --cap-drop ALL --security-opt no-new-privileges --mount 'type=bind,source=D:/projects/RvPort/tools/kb-scanner,target=/workspace/tools/kb-scanner,readonly' --mount 'type=bind,source=D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260924/round54-unit,target=/output' rvport-kb-scanner-test:local tests/run_source_chain_unit_tests.py --output /output

# round55：验收脚本单独完整统计；另逐模块核对行/分支均 >=90%。
docker run --rm --cpus 2 --memory 2g --memory-swap 2g --network none --read-only --tmpfs /tmp:size=512m --cap-drop ALL --security-opt no-new-privileges -e COVERAGE_FILE=/output/.coverage --mount 'type=bind,source=D:/projects/RvPort/tools/kb-scanner,target=/workspace/tools/kb-scanner,readonly' --mount 'type=bind,source=D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260924/round55-harness-unit,target=/output' --entrypoint /bin/sh rvport-kb-scanner-test:local -c 'python -m coverage run --branch --source tests.run_usage_scale_tests,tests.performance.usage_acceptance -m unittest tests.unit.test_usage_scale_acceptance tests.unit.test_usage_scale_runner -v && python -m coverage json -o /output/coverage.json && python -m coverage html -d /output/html && python -m coverage report --fail-under=90'
```

任务 6.3、7.2 已完成，合计 **25/25**。最终执行 `openspec validate implement-kb-scanner-candidate-usage-proofs --strict` 通过；scanner 范围 `git diff --check` 无空白错误（Git 提示未来 LF→CRLF 转换，不是检查失败），新增文本文件独立检查通过，12 个本地 Markdown/JSON 链接及新基线四组结构检查通过。本轮未修改 scanner 业务源码、两份 compiler facts、生产容器或其他任务目录，未在宿主安装依赖；只清理本次创建的临时测试容器，持久报告全部保留。没有执行被扫描项目的命令。

已完成 Apply，下一阶段在 `tools/kb-scanner` 对应聊天上下文执行 `/opsx:sync implement-kb-scanner-candidate-usage-proofs`，同步完成后执行 `/opsx:archive implement-kb-scanner-candidate-usage-proofs`。本轮不自动 sync/archive/commit/push 或重建后端容器。

## 2026-09-23：第三十轮起，最终门禁重验

最新 round48 隔离单元 **725 项通过，14.639 秒**；174 个自有文件，整体行 **98.56191341204965%**、分支 **95.29054310672237%**，全部登记模块 ≥90%/90%，context、用途 proof 为 100%/100%。范围含 kb_scanner/scripts/tools 未加载文件，排除仅为测试资产、不部署 archive、生成数据和第三方；报告 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round48-unit/{summary.json,coverage.json,html/}`。运行下方相同 Docker 单元门禁命令，输出改为 round48-unit。

round50 当前版本完整回归 **261 项通过，371.686 秒**。包含真实 parser/默认 CLI 自动证明正反例、AVX 人工 oracle、CMake/RPM/Autoconf、架构家族/枚举/函数多版本、V1/V2 与三工件差异、安全边界、原生崩溃缩减及三个固定项目。日志 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round50-regression.log`；执行既有 `tests/run_container_tests.py --regression-only` 独立容器命令，同时只读挂载 AVX fixture 到两个正式测试路径。没有项目命令执行；功能回归成功不替代尚未通过的规模性能门槛。

round51 当前版本固定 libarchive 两轮通过：**136.829571 / 142.178400 秒**，峰值 **671100 / 671456 KiB**，822 文件，2 CPU/2 GiB/无额外 swap，各轮 <300 秒，容器正常退出且 OOMKilled=false。两轮 JSON/HTML/log SHA-256 均与 round33 完全相同（见该轮列出的三份哈希），因此既有逐项审校账本可原样复用，没有重新更新 golden。64 Findings、26 项数据用途 unknown、0 新排除、全部源码链及未知原因均未改变。完整记录 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round51-libarchive/`，生产源码 digest 为 `4ffedfca055220bb8d62b3ae515e7a60352687eb86e7bb502a3dad58b94a9692`。

该轮执行命令（工作目录 `D:/projects/RvPort/tools/kb-scanner`；复跑必须使用新输出目录）：

```powershell
./tests/run-performance-container.ps1 -Source 'D:/projects/RvPort/.codex-tmp/kbscanner-sources-clean-20260909/libarchive' -Output 'D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round51-libarchive' -FixtureDir tests/fixtures/candidate-usage-performance
```

round52 重新扫描临时目录/文件名架构家族 CMake 项目并运行 4 项组件断言，全部通过（0.021 秒）：目录与文件名形成 3 家族，RISC-V/generic 选择与 x86 未选中路径可追溯到 CMake 第 5/6、14/15 行；强制包含 x86 的第 21 行仍 high/blocking，不因存在 generic 同伴降级。仍为 9 文件、23 Findings、14 inactive、7 blocking，±20 行和高亮不变。新报告保存在 `D:/projects/RvPort/.codex-tmp/kbscanner-path-selection-demo/report-round52/`，旧报告未覆盖，整个临时项目继续被 gitignore 忽略；未编译或执行项目。

当前可确认功能/单元/真实项目和文档完成；**6.3 相对规模性能、7.2 全部门禁验收仍未完成**。紧凑共享表方案需要跨模块内部合同确认，未获确认前不实施；不进入 sync/archive/commit/push 或生产部署。

round49 固定逻辑 CPU 0/1、相同原始门槛的独立子进程稀疏诊断仍失败：10000 引用 **10.751805→11.992610 秒（+11.54%、+1.24 秒）**，20000 引用 **21.855105→25.631388 秒（+17.28%、+3.78 秒）**。即使每次均成功产出工件且无 OOM，也不能勾选 6.3。此轮未运行密集组，不以旧成功替代本轮未执行项；最后完整矩阵为 round45。

2026-09-23 提出待确认的下一步：先验证紧凑共享用途记录表，减少嵌套 Mapping/tuple 在多阶段快照中的对象规模；可能需要调整前端、Normalizer、Analyzer 的内部数据合同，属于跨模块设计变更。此方案尚未批准、尚未实施，也不承诺未经测量即可达标。V2 对外 schema、原始事实保留、两个 compiler facts 和全部原性能门槛不变。当前继续验证已批准版本，不因性能失败悄悄放宽门槛或标记完成。

round40 四组仍未全部通过：10000 稀疏通过，10000 密集 77.320926→67.082518 秒通过；20000 稀疏 21.578016→约 25.76 秒未通过，20000 密集 161.192126→196.289632 秒未通过。精确结果保留于 round40-scale/benchmark/summary.json，所有子扫描正常结束。round41 对同输入 Analyzer 独立剖析：关闭/开启墙钟 14.237536/19.679460 秒，CPU 13.053211/18.042152 秒；额外 gen2 GC CPU 约 1.32 秒。剖析不作为性能验收。

据此局部复用规范用途边和已深冻结的作用域：不改 GC、预算、事实、公开 schema 或任何阈值。round42 隔离单元 **723 项通过，15.901 秒**，174 个自有文件，整体行 **98.56093312126032%**、分支 **95.28696313188901%**；所有登记模块达标，新增 core/metadata 行 98.305085%、分支 95.454545%。新增深层隔离、非法 JSON、外部代理/子类不可信、不可变、DTO 同一子树、稳定 ID/字节、跨根规范边复用和预算独立测试。报告位于 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round42-unit/`。

round43 为同一进程连续调用 child 的诊断（21.407140→24.987381 秒），存在进程存活状态影响，**不作为验收**；后续恢复独立子进程执行。此前失败记录全部保留。

round44 恢复独立子进程的 20000 稀疏诊断为 27.952626→23.975522 秒，通过该项。round45 完整矩阵仍失败：10000 稀疏 12.647400→16.988325 秒；10000 密集 83.385603→65.405453 秒通过；20000 稀疏 23.222430→41.125654 秒失败；20000 密集 165.181769→215.765233 秒失败。各子扫描均正常且小于 300 秒，无 OOM；不能选取 round44 的成功替代完整矩阵失败。密集开启峰值分别 885020/1364392 KiB，原始事实、预算状态和报告体积保持。

检测到明显测量波动（20000 稀疏同版开启 23.98→41.13 秒，知识加载 0.48→1.33 秒；宿主可读采样负载 57%，其后 37%）。未停止其他线程或生产服务。round46 仅将本次测试容器固定到逻辑 CPU 0/1，原 2 CPU 配额/2 GiB/无 swap 不变，驱动附加 cpuAffinity 记录；结果 21.152498→25.350219 秒，仍不通过。因此不能把缺口全部归因于环境，继续针对映射/额外对象分配剖析，不放宽原门槛。

round47 对 20000 密集输入的前 2000 个 Finding 映射做有界诊断，不发布报告、不当作验收：15.319814 秒（profiler 开启），其中原 chain.build 13.037 秒、SourceContext 6.318 秒、路径规范化 2.390 秒，新增用途 _view 约 0.49 秒，gen2 GC CPU 2.690 秒。日志及 pstats 在 round47-mapper-profile。随后局部复用扫描内规范路径/只读 ContextBudget，并让角色边和审计目录共享已冻结用途 summary；保持所有数据、ID、引用与序列化合同。所有普通失败继续保留，未放宽性能门槛。

round39 隔离单元 **719 项通过，18.583 秒**；174 个自有文件，整体行 **98.55006452592424%**、分支 **95.26435907189045%**，全部登记模块 ≥90%/90%，source_positions、用途需求/冲突索引均 100%/100%。命令沿用本文隔离单元 Docker 命令，输出挂载替换为 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round39-unit`，该目录含 summary.json、coverage.json、html/。最新局部优化后，规模、真实项目和完整回归继续重验；round31/32/33 的成功仅说明其当时版本，不替代最新代码验证。

round36 再验仍未通过全部相对门槛：10000 稀疏 10.271092→11.571175 秒失败，10000 密集 77.678607→72.003094 秒通过，20000 稀疏 24.776529→28.865338 秒失败，20000 密集 156.845259→207.093469 秒失败；所有子扫描均正常完成，未 OOM/超时。单元/真实项目的成功不覆盖这些失败。

根据剖析继续局部优化知识索引：CandidateUsageDemand 仅索引当前候选输入的全部匹配器需要的知识种类，ExecutionConflictIndex 仅索引同配置的实际依赖事实。默认/自定义 matcher 与完整知识索引的结果等价，18 项定向测试通过。round37 的 10000 稀疏诊断为墙钟 11.464369→11.861526 秒，CPU 10.239936→10.497749 秒，满足该对照门槛；精确值在 `round37-sparse-check/{disabled,enabled}/metrics.json`，不是四组最终验收。后续测量附加 cpuSeconds，仅用于诊断，不替代原墙钟门槛。

round38 针对 20000 密集仅剖析 frontend/normalizer，不发布报告、不作为验收：前端 47.826、归一化 16.864 秒（含 profiler 开销）；SourceByteIndex location/span 累计约 20.5 秒，其中路径规范化 18.6 秒。用途记录本身只保存数字 span，却每行构造并校验同一路径 DTO。改为校验偏移后直接计算行列值，公开 Evidence 仍完整验证路径和端点；26 项定向测试通过，穷举小输入全部合法范围并覆盖 UTF-8、CRLF、EOF、非法偏移及不构造 DTO 断言。source_positions 已登记为受影响模块，不缩小覆盖统计。

round35 临时路径/CMake 项目复扫成功，新报告 `D:/projects/RvPort/.codex-tmp/kbscanner-path-selection-demo/report-round35/`，不覆盖初次报告。仍 9 文件、3 家族、23 Findings，14 inactive、7 blocking、2 medium/unknown；4 项组件断言（0.063 秒）验证目录/文件名角色、CMake 第 5/6、14/15、21 行来源、intrinsic 风险、上下 20 行与引用完整性。源码仅静态扫描，不运行项目；资产已被 `.codex-tmp/` 忽略，不计作 scanner 隔离单元。

round33 固定 libarchive 两轮均通过：**142.338391 / 136.147315 秒**，峰值 **655164 / 658680 KiB**。固定 822 文件、清单 digest `f52edca120bdcd98d6c3316a2c5a42c09e38a99fc2189fa07b33cd3eb85fd67c`，2 CPU/2 GiB/无额外 swap、每轮 300 秒门槛不变；container-state 退出正常。两轮 JSON/HTML/log 哈希分别相同：`9c2a6093518106dfb069a13e5ccd74adb31ab16d923438f5a3a016c4c47f9d26` / `dfa851efcc82a14763acf45348f0d8add70e27632b815cd11e2c2326b6f997e5` / `7303d82e732c74ec431eecf13dc17803668bda33278bfdb922f1e3311d3bba23`。

审计 `round33-libarchive/audit.json` 已人工核对，新增版本化账本 `tests/fixtures/candidate-usage-performance/review-round33.json`，不覆盖旧 review.json 或 55 项记录。64 Findings（53 issues、11 hints）及全部核心字段不变；历史 54 项保留、1 项沿用既有去重、10 项基线已有新增全部对齐。26 项数据用途仍 unknown、0 排除；30 根、11 个作用域索引、7133 条查询记录、22578 次访问、0 精确根缓存命中。此前 8 根 scan-record-budget 原因及 truncated 已消除，现能给出实际调用/字段/返回/预处理 owner 等未知断点；不把“采集到了”夸大为“已证明无风险”。未执行项目命令，任务 6.2 完成。原始工件在 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round33-libarchive/`。

round34 重新生成四个固定样例 × V1/V2 × producer 开关工件，全部成功。四个 V1 三工件不变；V2 仅 source-evidence-chain 和 architecture-enum 新增用途 namespace，原结论/ID/源码主链保持，其他两个样例三工件不变；所有 log 字节不变。既有审校 golden 摘要完全复现，无需更新 golden。工件及逐字段路径在 `.../round34-fixed-reports/audit.json`。

round32 完整回归 **261 项通过，359.980 秒**，日志 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round32-regression.log`。真实 grammar/CLI 自动正例、逃逸/宏/模板/配置/混合用途反例、无候选字节对照和旧报告摘要均通过，原生崩溃缩减及三个固定项目回归通过。没有手工注入 producer role，未执行项目命令。两份 generated compiler facts 的 SHA-256 与文末冻结值一致。任务 6.1、6.5 完成；真实项目规模及相对性能仍单独验收，不由回归总耗时推导性能通过。

round30 使用固定代码、2 CPU/2 GiB/无额外 swap，全部 8 个子扫描均成功且各自少于 300 秒，无 OOM，但相对耗时门槛仍有两项失败：

| 引用数/需求 | producer 关闭（秒） | 开启（秒） | 门槛 |
| --- | ---: | ---: | --- |
| 10000 稀疏 | 16.133921 | 15.225275 | 通过 |
| 10000 密集 | 81.340237 | 80.466615 | 通过 |
| 20000 稀疏 | 21.985380 | 25.924980 | 未通过 |
| 20000 密集 | 169.473703 | 189.637557 | 未通过 |

原始结果及精确值以 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round30-scale/benchmark/summary.json` 为准。20000 密集开启峰值 1474380 KiB，19200 Findings 全部保留，14928 个根明确预算截断，其余未采集作用域为 unknown；scopeIndexes/recordCount/visits=0 表示未运行闭包查询，不表示原始 inventory 为空。失败未勾选为通过。

针对额外开销继续局部优化：文件遍历结束并确定预算状态后才构造、冻结用途 Evidence，避免先冻结全部记录再因文件预算重新冻结；尚未发布的暂存结构只有标量，不保存原生对象。HTML 单次用途审计渲染复用同一个源码对象的已转义片段，每次调用重建缓存。记录、未知原因、上下文、命中高亮和输出字节保持；21 项定向测试通过，新增一次冻结、不可变性、重复源码字节等价、转义及跨调用失效断言。

round31 全量隔离 **716 项通过，15.829 秒**；174 个自有文件，整体行 **98.54092256250475%**、分支 **95.24172059383326%**，全部登记模块均达到 90%/90%。报告位于 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round31-unit/{summary.json,coverage.json,html/}`。范围仍为 kb_scanner/scripts/tools 全部自有源码（含未加载），排除理由与本文原命令不变，输出目录替换为 round31-unit。此轮单元通过不能替代尚待执行的完整回归及项目/规模性能重验。

## 2026-09-23：第二十二轮，报告对象复用

round21 的 10000 稀疏为 24.801869→22.075872 秒，通过；10000 密集关闭组仍退出 -9，且尚未进入文件发布。分块 JSON 只能避免序列化时的整份复制，不能独自解决报告对象构建占用。保留失败现场后停止本轮测试容器。

新增扫描内缓存：相邻源码上下文复用同一路径/行的不可变 ContextLine，证据步骤与 source-chain Arc 对应边复用，incoming 扩展按原步骤与 Arc 组合复制并复用。不得改变独立 Finding 的完整内容、代码上下各 20 行、命中高亮、稳定 ID 或核心 schema。单测验证重叠上下文共享但高亮/文件/快照隔离，以及 incoming 不污染基础步骤或其他查询。

round22 首次隔离单测暴露新测试错误：直接修改只读 SnapshotIndex.evidence。已修正为构造独立测试快照，5 项链测试通过；失败记录保留，完整门禁另行重跑，不据失败轮声称通过。

round22 的 10000 密集关闭诊断成功：9600 Findings，228.3688 秒、峰值 614320 KiB，JSON 1243254174 字节，三个工件成功发布；证明报告对象共享解决该诊断中的 OOM，但不代表四组最终性能通过。round23 对 1000 密集关闭组进行 cProfile，校验 29.862 秒，其中 `_extensions` 28.729 秒、约 517 万次调用，原缺失 extensions 属性查询还触发大量 Pydantic `__getattr__`。因此增加本次递归 visited，并在 model_fields 确有 extensions 时读取；不跨校验调用复用。24 项源码/链/验证边界定向测试通过。

round24 重新固定生产代码运行全部四组开关对照，测试驱动新增构建 Finding、校验、发布分段计时。性能运行期间不修改生产代码，也不并行启动本任务其他测试负载。输出目录 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round24-scale/benchmark/`；结论以全部完成后的 summary 为准。

round24 全部结果：10000 稀疏 13.7728→14.1598 秒通过；10000 密集 95.5874→110.4504 秒未通过；20000 稀疏 36.6262→56.9470 秒未通过；20000 密集关闭组 236.0934 秒、峰值 1173488 KiB、JSON 2505471776 字节成功，但开启组在 Finding 投影阶段退出 -9。总体失败。后半程有其他任务/业务负载并发，未停止它们，也不因环境波动将失败改成通过。

10000 密集开启组 visits=1000000、7812 个排除、1788 个预算截断后 unknown；20000 密集触发文件采集预算，所有 19200 个候选保留，不生成完整排除 proof。后者暴露用途 namespace 的源码 JSON 重复复制：即使共享了 Source 模型，`_sources` 仍为每个根 model_dump 相同窗口。新增单次 CandidateUsageProjection 的 SourceSpan→JSON 与源码行→JSON 缓存，投影期间只读，不改变输出字节、来源预算或完整性。8 项用途投影单测通过，覆盖原序列化等价、重叠行共享、快照隔离、缺文件及高亮。

round25 对 1000 密集开启组剖析：新增 Analyzer 7.596 秒（其中物化 4.457 秒），分类/投影两次证明复核合计 5.614 秒；没有删除独立消费验证。补充相同闭包的物化缓存，缓存键包含配置、节点/边/uses 与状态/截断，根身份及预算仍独立；20 项物化/会话/冲突/证明校验定向测试通过。另将大报告 HTML 改为逐 Finding 分块，22 项序列化/发布/用途投影测试通过；空/单/三 Finding 的 HTML SHA-256 在修改前固定，修改后完全一致。未缩减来源或代码上下文。

round26 重新执行全部隔离单元覆盖门禁；此次以后不引用 round22 失败轮或更早旧代码的单元结果作为新实现验收。

round26 结果：**712 项全部通过，47.700 秒**；174 个自有可执行文件，整体行 **98.53591581515937%**、分支 **95.2253628724217%**，全部登记模块 ≥90%/90%。统计范围为全部 kb_scanner/scripts/tools（含未加载模块）；tests、archive、规则数据和第三方排除原因见 inventory，未缩小业务代码分母。源码 JSON 投影与闭包物化均 100%/100%；报告验证 98.23%/97.50%。持久报告 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round26-unit/{summary.json,coverage.json,html/}`。命令为本文完整 Docker 隔离单元命令，输出挂载替换为 round26-unit。

round27 结果：10000 稀疏 11.1935→13.6506 秒未通过；10000 密集 76.6227→102.2280 秒未通过；20000 稀疏 28.8971→31.2055 秒通过；20000 密集关闭组 190.8163 秒通过，开启组峰值 1938120 KiB、已通过 Finding 构建与引用校验，但发布超时 124（300 秒）。10k 稀疏/密集开启的三工件与 round24 对应工件哈希完全一致；OOM 修复不能替代性能验收。

进一步局部优化：对采集预算已耗尽的 partial scope 直接保留 unknown，不构造注定不能准入的用途图，保留原快照记录与命中、截断原因；非预算 partial 不短路。33 项会话/物化/发布/用途投影测试通过。支持图消费校验在各自快照内缓存相同图的必需来源及连通分量，根身份和来源继续逐次校验；已有变异反例和新增缓存污染/跨配置/来源缺失/绑定错位测试通过，未删除独立验证。publisher 写缓冲固定 1 MiB。round28 重新执行全量隔离门禁，旧轮结果不替代新代码验收。

round28 全量隔离 **714 项通过，16.159 秒**，174 文件，整体行 **98.53981291352954%** / 分支 **95.23809523809524%**，所有登记模块达标；usage_proof 99.00%/96.55%。报告 `.../round28-unit/{summary.json,coverage.json,html/}`，完整运行命令同上、输出替换为 round28-unit。round29 剖析 10000 稀疏开启组：候选预选择 0.281 秒、采集 0.182 秒、入口知识索引 0.028 秒；前端总 9.62 秒中原枚举事实采集占 8.15 秒。因此不能把不同轮前端总耗时差直接全部归为新增 producer。证明复核 192 次仅 0.094 秒，支持图实际复核 8 次（分类/报告各 4），每根身份仍独立校验。

## 2026-09-23：用户确认后的候选驱动采集（第十七轮起）

用户通过 `/opsx:apply implement-kb-scanner-candidate-usage-proofs 可以，同意你的修改` 明确批准阶段协作调整。新增扫描内 UsageAnchorSelector，默认管线将本次已加载知识传入 frontend；使用正式归一化和同一候选 matcher 选出锚点，在当前 native tree 内提取作用域记录，不重复读取文件。预选择共享同 kind/value 引用代表，保留声明供引用校验，命中后展开全部 occurrence；最终事实与精确根仍由原正式阶段生成，不把采集需求当证明。无候选函数不消耗用途记录预算。

- 稀疏样本 400 个函数现在只生成 4 个 usage_scope，旧 Evidence/Fact 保留；96 个根、644 条使用记录，96 个局部纯数据候选均完成自动证明。
- 新增纯 DTO/fake adapter 单元覆盖需求预选择、重复值不合并身份、failed/unavailable/partial、扫描内索引复用、阶段知识传递和每阶段停止边界；真实 grammar 组件对照原始 Evidence/Fact 字节语义、需求身份及作用域数量。
- round17 单元 697 项通过，但新登记 orchestrator 分支只有 70.83%，未通过质量门禁；已补每阶段异常/不可用与带知识入口断言，不降低门槛。
- round19 单元 **700 项通过，16.151 秒**，174 个自有文件，整体行 **98.52523235271526%**、分支 **95.18675394686176%**，全部登记模块达标。UsageAnchorSelector 和 orchestrator 均 100%/100%。报告位于 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round19-unit/`，命令同此前完整 Docker 命令，输出改为 round19-unit。统计范围/排除理由不变。
- round17/18 稀疏分别 19.3903→24.2782 秒、18.4195→22.1720 秒，均未达标。剖析显示重复值匹配可复用，已优化；预归一化仍用正式逻辑，仅减少同值引用代表和非需求输入。
- round19 稀疏 18.4450→24.4025 秒，测试期间与本轮覆盖率进程重叠，保留原失败但不作为干净性能结论。round20 将单独依次执行四组规模，测试驱动不再遇首组失败就隐藏其余组，最终退出码仍要求所有组通过。

设计改变后重新打开相关验收项，并新增 2.4；之前 21/24 不表示新实现已完成。当前仍在 apply，不具归档条件，不提交/推送/部署，也不操作其他任务文件。

### 密集场景诊断与局部优化

round20 的 10000 密集关闭/开启组均在 report_projector 阶段退出 -9，未生成完整工件；20000 密集关闭组同样 -9。基线也失败，因此不把这一点归因为用途证明错误。原 JSON serializer 一次性 model_dump 整份自包含报告，随后再复制 JSON 字符串和字节，导致严重内存放大。改为逐 Finding 编码并在大报告中分块写入原子 publisher，哈希边写边计算；单测对照旧 serializer 字节完全相同，覆盖空/单项/多项、中文、扩展内 null、流生成失败回滚和 256 项实际投影入口。

此外，TestSelectionDetector 原来每个实体扫描全部 proof，密集开启组 Detector 达 46.194 秒；改为目标索引，单测以遍历计数验证新增 200 个无关实体不会增加 proof 全量遍历次数且结果完全相同。Classifier 改为 relation→proof 索引并避免对每个 observation 把整个字典隐式转换为集合；测试校验保留全部且仅保留相交 proof。原枚举语法包含检查存在节点×声明区间扫描，替换为起点二分/前缀最大终点，原半开区间语义保留。

round20 在诊断过程中发生了实现迭代，不作为统一代码版本的最终验收。已核对容器挂载后只停止本轮规模测试容器，保留所有失败现场，未停止其他任务或业务容器。最终需固定代码版本重新运行四组规模。

round21 在上述优化后重新运行隔离门禁：**706 项通过，23.598 秒**，整体行 **98.52952439304588%**、分支 **95.2033768227168%**，174 个源码文件；新增登记的 publisher（96.23%/94.44%）和 TestSelectionDetector（94.44%/97.22%）均达标，其余登记模块亦通过。持久目录 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round21-unit/`。测试驱动的报告统计从实际序列化边界提取，仍要求 main 返回 0、三工件成功发布及根数一致，不在 CLI 返回后重复把 GB 级 JSON 加载到内存；未删除生产端引用校验。

固定代码的 round21 规模测试使用独立容器 `kb-usage-round21-scale`，目录 `.../round21-scale/benchmark/`；runtime.json 保存自有源码逐文件哈希和整体 digest，以及实际 cgroup 2 CPU/2 GiB/无额外 swap。此轮完成前不修改生产源码。

## 2026-09-23：第十六轮预算摘要修正

发现并修复一个审计缺口：scope 已被前端记录预算裁剪为空时，根绑定失败可能绕过 query，遗漏原 scope 的预算原因。UsageSession 现在在绑定前保留 scope.reasonCodes/partial，`analysisTruncated` 因而正确为 true；保留 unknown，不生成排除。新增隔离反例确认零记录/缺根时仍保留 `usage-scan-record-budget`，12 项定向测试通过。

最新隔离单元 **692 项通过，18.694 秒**，173 个自有源码文件，整体行 **98.4668721109399%**、分支 **95.04052489386338%**，全部登记模块通过；报告在 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round16-unit/`。使用下方完整 Docker 命令，仅将挂载输出目录替换为 round16-unit，统计范围/排除理由不变。

round15 完整回归 260 项通过（430.773 秒）；libarchive 两轮为 214.6887 / 250.78 秒，峰值 933596 / 936572 KiB，均通过 300 秒门槛。round15 的 JSON/HTML/log 与已审校 round9 对应工件 SHA-256 完全相同，证明索引/缓存优化没有改变报告。

上述 round15 结果在预算摘要修正前完成，不作为新修正的验收替代。round16 已重新验证：完整回归 **260 项通过，397.044 秒**，日志 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round16-regression.log`；固定 822 文件 libarchive 两轮 **220.5966 / 212.4707 秒**、峰值 **935412 / 935028 KiB**，2 CPU/2 GiB/无额外 swap，每轮 300 秒门槛通过。输出在 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round16-libarchive/`。

两轮 JSON/HTML/log 字节一致；移除用途 namespace 后，与修改前 822 文件基线逐字段无差异。64 findings（53 issues、11 hints）、历史 55 项对齐及既有去重关系保留。历史 26 项数据用途仍全部 unknown，没有自动排除。版本化 review.json 已人工审校后刷新预算原因，round9 原始审计不删除。

预算修正使 **8 个根**明确暴露 `usage-scan-record-budget` / `usage-scope-incomplete` 和 `analysisTruncated=true`：CKSUM_SHA512 5 项、CRC32 2 项、BOOT_PLATFORM_X86 字段写入 1 项。不能把它们的 unknown 全归因于语法不支持；提前采集无关函数已经消耗全扫描 inventory 额度，也是证明无法完成的原因。这进一步支持下面待确认的候选驱动设计调整。

本轮完成任务 6.1、6.2、7.1，进度 **21/24**；6.3 规模性能仍失败，6.5 的综合质量条件及 7.2 最终交付条件未满足。strict、链接和格式检查不替代性能验收。

候选驱动提取的阶段调整仍待用户确认，性能任务 6.3 未通过，不能归档。

## 2026-09-23：第十五轮局部性能优化与设计决策边界

- 新增源码区间索引 `span_lookup.py`，替换原枚举条件/后继依赖的逐引用全文件遍历；原包含语义、输入顺序和关系身份保留。隔离单测对照原 `_contains`，覆盖嵌套/相邻/重叠/无位置/跨文件/输入反转，模块 100%/100%。
- UsageSession 缓存不可变用途节点/关系及稳定 ID，按配置隔离；并验证重复 materialize 的 ID、对象和值一致，另一个配置不复用原节点。查询计数/预算不因物化缓存而放宽。
- SourceContextProjector 在本次快照内缓存已校验路径，仍拒绝出界文件；源码上下文、命中、裁剪与中文展示不变。正常路径和拒绝路径都不重复 resolve/读取。
- 最新隔离单元 **691 项通过，18.228 秒**；173 个自有源码文件，整体行 **98.46651768513524%**、分支 **95.03861003861005%**，所有登记模块通过，排除/统计范围与下节一致。持久报告在 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round15-unit/`，执行命令同 round13，将输出目录改为 round15-unit。
- 上一份完整回归（round13）**260 项通过，396.189 秒**；局部索引/缓存修改后的 round15 完整回归另行重跑，不拿旧轮结果替代新验收。
- 两份 compiler facts SHA-256 再次核对不变。`git diff --check -- .`（工作目录 tools/kb-scanner）和 OpenSpec strict 通过；Git 仅提示 LF/CRLF 配置转换，没有空白错误。

### 性能证据与待确认变更

保持同一有效的一万引用稀疏样本、2 CPU/2 GiB、默认三工件，当前关闭新增 producer **17.1804 秒**、开启 **30.7751 秒**，相对门槛失败。原枚举 Analyzer 基线由约 202 秒降至约 3.34 秒，不再掩盖新增能力的开销。阶段数据保存在 `.../round15-scale/benchmark/summary.json` 和各组 `events.jsonl`。

400 个函数中只有 4 个有候选；当前 upfront collector 却生成 400 份 scope inventory（额外 400 个 Evidence），规范化后真正进入用途查询的只有 4 个 scope/644 条记录/96 个根。前端 8.78 → 16.71 秒、规范化 1.07 → 4.11 秒、Analyzer 3.34 → 5.03 秒。下一步应考虑先以已有 fact 确认候选作用域，再提取、绑定和规范化需要的使用记录，不是提高门槛或删除事实。

该建议涉及前端/规范化/需求选择阶段协作顺序，属于需要确认的设计调整；已向用户提出，**尚未授权时不直接实施**。现有 V2 schema、候选身份、compiler facts 和安全/性能门槛均拟保持。6.3 保持未完成，10000 密集及 20000 场景不能凭稀疏单组结果标记通过；早先匿名枚举空样本和超时结果均保留。

round15 固定 libarchive 两轮与完整回归正在收尾；尚无归档授权，不提交、推送或部署，也不纳入其他任务的修改。

## 2026-09-23：继续 apply（第九至十四轮验证，尚未全量验收）

本节为最新进展，下方历次错误现场仅作历史记录。普通测试失败已在授权范围内直接诊断修复，不再要求用户重新执行 apply。

### 完成功能及边界

- 补齐已知执行冲突：复用正式 matcher 与 compiler facts，匹配同文件/配置、实际查询闭包中的执行 Evidence；摘要给出 conflictCount 与 `usage-known-execution-conflict`。普通未知调用保持 unknown，不凭名称猜安全。
- 保留原 high/blocker、实体/关系/证明和 Observation；候选只有完整局部非执行闭包才省略 Classification，不能据此使项目 ready。
- 覆盖后续写入不能隐藏早先逃逸、同名遮蔽、定义/使用责任、跨文件预算、根间扫描访问预算；预算、引用不完整和冲突均 fail-closed。
- 修复编译数据库配置边界：未配置的 Tree-sitter inventory 不可代表某一编译配置。真实默认 CLI 与显式 Clang enrichment 的双配置测试均保留 unknown；不重写旧 fact/configuration 身份。
- 模板/取址/volatile/错误语法/局部宏反例改成具名枚举，并要求实际存在用途查询根，避免匿名枚举尚未采集导致反例空通过。新增跨 TU 反例，禁止借用另一文件的纯数据证明。
- Detector 从逐候选扫描全关系改为 Evidence/Relation/Proof 反向索引与分支缓存；非执行边不进入原执行关联，原引用校验保留。

### 最新单元覆盖率（round13）

独立镜像 `rvport-kb-scanner-test:local`，只读代码挂载、输出单独挂载、无网络、2 CPU/2 GiB/无额外 swap。没有在宿主安装依赖、执行项目命令或重建生产容器。

```powershell
docker run --rm --cpus 2 --memory 2g --memory-swap 2g --network none --read-only --tmpfs /tmp:size=512m --cap-drop ALL --security-opt no-new-privileges --mount 'type=bind,source=D:/projects/RvPort/tools/kb-scanner,target=/workspace/tools/kb-scanner,readonly' --mount 'type=bind,source=D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round13-unit,target=/output' -w /workspace/tools/kb-scanner rvport-kb-scanner-test:local tests/run_source_chain_unit_tests.py --output /output
```

688 项通过，16.681 秒；整体行 **98.44367015098723%**、分支 **94.97282608695652%**，全部登记受影响模块 ≥90%/90%，失败模块集合为空。`analysis.py`、`conflicts.py` 均 100%/100%，`detectors/local.py` 100%/96.15384615384616%。172 个源码文件，统计全部 `kb_scanner/scripts/tools`，纳入未加载源码；测试资产、非部署 archive、生成规则数据和第三方依赖排除理由与 inventory 一致，无分支文件的分支指标不适用。真实 parser/CLI 测试不计入此单元覆盖。

持久报告：`D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round13-unit/summary.json`、`coverage.json`、`html/`。旧 round9 的 687 项通过记录保留，不覆盖。

### 真实项目与兼容性审校

- round9 四个固定样例审计在 `.../round9-audit/reports/audit.json`。全部 V1 工件不变，日志不变；两个 V2 样例仅新增用途 namespace。architecture-enum 一个 `Backend::avx2` 根记录 4 个已确认冲突，原结论和源码主链不变；审校后才更新新增差异账本，历史账本保留。
- round9 固定 822 文件 libarchive 两个独立扫描进程：**234.3993 / 227.19 秒**，峰值 **931192 / 938144 KiB**，2 CPU/2 GiB/无额外 swap、每轮 300 秒门槛通过。报告均 64 findings、53 issues、11 hints、0 blocker。
- 逐字段移除新增 namespace 后，与修改前 822 文件当前基线 **无差异**。30 个候选根、11 个作用域索引、4738 条使用记录、19164 次访问、0 缓存命中、0 自动排除。
- `tests/fixtures/candidate-usage-performance/review.json` 追加 64 项审校记录并对齐旧 55 项：54 项仍有对应，1 项是旧能力已经去重而不是本轮消除；当前较旧账本增加的 10 项在本 change 开始前即存在。历史 26 项数据用途全部 unknown。
- `_7Z_X86`/`_7Z_X86_BCJ2` 的闭包涉及复杂控制、调用、字段/指针/返回等；`BOOT_PLATFORM_X86` 定义未解析为使用根，字段写入仍无完整绑定；`CKSUM_SHA512` 与 CRC32 当前根绑定不完整，不能凭算法名或格式标志排除。代表源码已人工核对，不声称已证明具体编解码实现兼容。
- 可重复审计入口：容器内 `python -m tests.audit_candidate_usage_libarchive <旧报告> <新报告> <新审计输出>`；工具只收集差异，历史已知去重须保留同位置 confirmed finding 才算对齐。

### 规模测试尚未通过全部门槛

`tests/run_usage_scale_tests.py` 使用同输入开关新增 inventory/Analyzer，完整运行默认 CLI 的 JSON/HTML/log，记录时间/RSS/统计/阶段耗时；要求实际候选数匹配预期，不能接受零候选空跑。无项目执行。

- round9/10 的匿名枚举样本没有产生候选，已明确判为无效结果；原文件保留，不列为性能通过。
- round11 有效一万引用稀疏样本 221.449 → 255.605 秒，不通过相对 10% 且 1 秒门槛；未调整门槛。
- 优化 Detector 后 round12 同样本 220.583 → 220.250 秒，通过；96 个候选全部是自动闭合的局部非执行数据用途，审计上限未溢出。
- round12 一万引用密集样本关闭新增 producer 的基线在报告投影阶段超过脚本 300 秒超时；开启组和更大规模仍需诊断。此结果不能视作新增能力验收通过，也不能把关闭 producer 的瓶颈伪称为新增用途缺陷。
- round14 对缩小的密集输入进行 cProfile 定位，仅作诊断，不替代 10000/20000 正式验收。

完整回归本轮重新运行中，日志 `.../round13-regression.log`；`openspec validate implement-kb-scanner-candidate-usage-proofs --strict` 已通过。任务 6.2/6.3/6.5/7.2 尚未全部关闭，不具归档条件。后续修改生产源码必须重跑受影响门禁。

## 2026-09-23：第八轮 apply 暂停，8/24 项完整完成

### 上轮问题处理与本轮进展

- `usage_scope` 补齐既有 `metadata.identityVersion=1` 合同，使用 `IDENTITY_VERSION` 常量，保留原 scope 稳定 ID；新增隔离断言直接核对 ID 和元数据。
- 显式 vocabulary 测试登记 usage_scope；前端模块数量从 10 更新为 12，仍保留实际源码集合与 inventory 双向相等断言，不缩小统计范围。
- 前端及合同定向测试 **23 项通过，0.648 秒**。结合已有 fake grammar 声明/读写、遮蔽、控制闭包、UTF-8/CRLF 及旧锚点不变测试，任务 2.1 完成。
- 任务 5.3 完成：新增固定样例差异账本与可重复的容器审校脚本，保留历史账本；默认/显式 V2、V1、无候选三工件由已有真实 CLI 组件断言覆盖。未改核心 schema、后端或前端。

```powershell
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_usage_inventory tests.test_formal_cpp_frontend tests.test_frontend_test_quality -v
docker exec kb-scanner-cmake-verify python -m unittest tests.test_bilingual_suggestions -v
```

第二条 **6 项通过，22.155 秒**，包含本轮新增“只移除新 namespace 后，历史所有字段及其他扩展摘要完全恢复”的回归断言。

### 固定报告差异已审校

新增 `tests/audit_candidate_usage_reports.py`，使用正式 CLI 对四个固定样例分别关闭/开启 collect_usage 和 CandidateUsageAnalyzer，执行 V1/V2 并保存完整工件。它不自动批准或更新 golden，运行时禁止通过 subprocess.run 执行项目命令。实际命令（宿主根 `tools/kb-scanner`，输出挂载目录预先新建）：

```powershell
docker run --rm --cpus 2 --memory 2g --memory-swap 2g --network none --read-only --tmpfs /tmp:size=512m --cap-drop ALL --security-opt no-new-privileges --mount 'type=bind,source=D:/projects/RvPort/tools/kb-scanner,target=/workspace/tools/kb-scanner,readonly' --mount 'type=bind,source=D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round8,target=/output' -w /workspace/tools/kb-scanner -e PYTHONPATH=/workspace/tools/kb-scanner rvport-kb-scanner-test:local tests/audit_candidate_usage_reports.py /output/report-audit
```

退出 0，16 次扫描均成功。全部工件及递归字段差异保存在 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round8/report-audit/`，总账为 `audit.json`。关闭 producer 后的 JSON/log 摘要均重现历史账本：

| 样例 | V1 JSON/HTML/log | V2 变化 | 日志 |
| --- | --- | --- | --- |
| source-evidence-chain | 全部不变 | 顶层用途审计、1 个宏候选 fact 扩展 | 不变 |
| architecture-enum | 全部不变 | 顶层用途审计、5 个枚举候选 fact 扩展 | 不变 |
| architecture-candidate-noise | 全部不变 | 三工件不变 | 不变 |
| rpm-architecture | 全部不变 | 三工件不变 | 不变 |

前两项排除数均为 0，保留 unknown/原结论；原 Finding ID、fact 非新增扩展字段、occurrence、conclusion、evidenceChain、summary 和静态声明未变。HTML 在仅关闭 render_usage_summary 后与原 HTML 字节完全一致，独立容器只读对照两项均为 True，说明没有夹带其他展示变化。

审校后新增 `tests/fixtures/candidate-usage-report-differential.json`，未覆盖 CMake/函数多版本历史 ledger。该批准仅涉及上述固定样例的本轮用途扩展，不代表 libarchive 或后续性能验收。

### 新增单元测试错误：暂停原因

```powershell
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_usage_analysis tests.unit.test_usage_projection tests.unit.test_usage_bindings tests.unit.test_usage_inventory -v
```

26 项中 25 项通过、1 error，0.047 秒。通过的新断言确认：排除后项目仍 provisional，input_completeness/target_reachability/riscv_or_generic_alternative 均 unknown；来源命中第 25 行时提供第 5–45 行及精确高亮；源码不可用时保留 context_unavailable。

错误位于 `tests/unit/test_usage_analysis.py` 的 `test_original_high_blocker_and_execution_proof_survive_candidate_exclusion`：测试访问 `after.classifications[0].severity`，但 Classification DTO 没有该字段，风险由 `classifiers.risk.present_risk(classification, observation)` 投影。之前“旧 Entity/Relation/ProofPath 原样保留”“排除前后原 Classification 完全相等”“impact=blocking_issue”的断言均已通过；之后 observation 保留断言尚未执行。

下一轮应使用真实 `present_risk(after.classifications[0], confirmed)` 核验 severity=high/blocking=true，保留其余断言，不向 DTO 添加无关字段，也不删除风险断言凑通过。按 openspec-apply-change 错误暂停要求，本轮保留现场，没有继续修改实现。

### 完整隔离单元覆盖：指标达标，但测试门禁未通过

```powershell
docker run --rm --cpus 2 --memory 2g --memory-swap 2g --network none --read-only --tmpfs /tmp:size=512m --cap-drop ALL --security-opt no-new-privileges --mount 'type=bind,source=D:/projects/RvPort/tools/kb-scanner,target=/workspace/tools/kb-scanner,readonly' --mount 'type=bind,source=D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round8/unit,target=/output' -w /workspace/tools/kb-scanner rvport-kb-scanner-test:local tests/run_source_chain_unit_tests.py --output /output
```

**680 项：679 通过、1 error，19.319 秒，退出 1。** 错误仍为上述测试字段访问。整体行覆盖率 **98.43287073132699%**、分支 **94.92952231793265%**；登记受影响模块均达到 90/90，failedCoverage 为空，但 passed=false。usage_inventory 为 **98.01980198019803% / 95.23809523809524%**，usage analysis 与 projection 均 **100% / 100%**。无分支模块指标不适用。

完整统计 kb_scanner/scripts/tools 的 171 个自有源码文件，包括未加载文件；仅排除第三方、规则数据、测试资产和非部署 archive。新增审校脚本位于 tests，是非部署测试工具，不把它计作产品模块以改变门禁分母。组件/真实 parser 没有混入单元覆盖。

报告持久保存：

- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round8/unit/summary.json`
- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round8/unit/coverage.json`
- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round8/unit/html/index.html`

### 完整回归与收尾

恢复 AVX 的两个只读读取路径，使用独立容器：

```powershell
docker run --rm --cpus 2 --memory 2g --memory-swap 2g --network none --read-only --tmpfs /tmp:size=1g --cap-drop ALL --security-opt no-new-privileges --mount 'type=bind,source=D:/projects/RvPort/tools/kb-scanner,target=/workspace/tools/kb-scanner,readonly' --mount 'type=bind,source=D:/projects/RvPort/backend/runtime/kb-scan-real/avx-avx2-example-code,target=/fixtures/avx-avx2-example-code,readonly' --mount 'type=bind,source=D:/projects/RvPort/backend/runtime/kb-scan-real/avx-avx2-example-code,target=/workspace/backend/runtime/kb-scan-real/avx-avx2-example-code,readonly' -w /workspace/tools/kb-scanner rvport-kb-scanner-test:local tests/run_container_tests.py --regression-only
```

完整回归 **258 项全部通过，425.046 秒，退出 0**。AVX 样本挂载、正式前端元数据/vocabulary/inventory、固定报告摘要等上轮错误均已消除；包括三个固定项目 V1/V2 正常退出与原生崩溃缩减回归。完整输出保存于 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round8/regression.log`。回归期间未修改业务代码。此时单元门禁仍有上述 1 error，不能把回归通过解释为整体质量验收通过，也不将任务 6.5 标为最终完成。全回归耗时不是单轮 libarchive 扫描耗时，不据此判定其 300 秒性能门槛。

OpenSpec strict 通过；已跟踪 scanner 文件 git diff --check 无空白错误（只有 CRLF 提示），两份 compiler facts SHA-256 与首轮记录一致。未安装宿主依赖、修改生产容器、操作其他 scanner，也未同步、归档、提交或推送。

最终质量验收继续未完成。已知执行冲突摘要、更多配置/闭包边界、接入后的 libarchive 两轮与规模性能仍待实施；本轮回归不替代这些任务。下一步仍为 apply，OpenSpec 根 `tools/kb-scanner`：

```text
/opsx:apply implement-kb-scanner-candidate-usage-proofs
```

## 2026-09-23：第七轮 apply 暂停，6/24 项完整完成

### 本轮完成

- 修复第六轮两个测试构造/比较问题，未放松 DTO 和准入合同；相关 22 项测试通过。
- 完成任务 5.1：V2 用途扩展、排除审计和多个 namespace 共存；同一 Finding 的所有候选根共享 64 个来源额度，不按根重复放大。新增来源预算和确定性测试。
- 补齐查询、扫描及前端预算硬上限校验；scope membership 关系计入 proof 关系额度，全局/聚合预算超限也标记 truncated 并保持 unknown，输出预算摘要。相关 32 项隔离单测通过。
- 新增 `tests/test_candidate_usage_cli.py`，真实默认 CLI 的 4 项组件测试均通过：闭合局部数据自动生成并消费 proof；调用/return 逃逸、模板、取址别名、volatile、错误语法、宏重定义不自动排除；已确认 intrinsic 结论不变；默认/显式 V2 一致，显式 V1 保持原结构；无候选时启用/关闭用途 Analyzer 的三个工件逐字节一致。未执行被扫描项目的构建命令，没有手工注入 role。
- 新增 `docs/candidate-usage-proofs.md`，明确当前支持范围、预算、V2 扩展及仍未完成部分；没有把实施中文档当作整体完成声明。

### 隔离单元与覆盖率：通过

宿主工作目录 `D:/projects/RvPort/tools/kb-scanner`，输出目录预先新建：

```powershell
docker run --rm --cpus 2 --memory 2g --memory-swap 2g --network none --read-only --tmpfs /tmp:size=512m --cap-drop ALL --security-opt no-new-privileges --mount 'type=bind,source=D:/projects/RvPort/tools/kb-scanner,target=/workspace/tools/kb-scanner,readonly' --mount 'type=bind,source=D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round7-unit,target=/output' -w /workspace/tools/kb-scanner rvport-kb-scanner-test:local tests/run_source_chain_unit_tests.py --output /output
```

677 项单测全部通过，14.888 秒，退出 0；整体行覆盖率 **98.4327485380117%**，分支覆盖率 **94.92952231793265%**，`failedCoverage={}`，`passed=true`。所有登记受影响模块均达到行/分支 90% 门禁；无分支模块为不适用。

| 本轮重点模块 | 行覆盖率 | 分支覆盖率 |
| --- | ---: | ---: |
| projection/v2/candidate_usage.py | 100% | 100% |
| analyzers/candidate_usage/proofs.py | 100% | 100% |
| analyzers/candidate_usage/closure.py | 97.83% | 95.45% |
| analyzers/candidate_usage/session.py | 99.02% | 97.73% |
| frontends/cpp/usage_inventory.py | 98% | 95.24% |
| projection/v2/mapper.py | 96.91% | 100% |

统计范围为完整 `kb_scanner`、`scripts`、`tools` 的 171 个自有源码文件，包含未加载源码。排除第三方依赖、测试资产、规则数据和非部署 archive；未排除自有业务逻辑。真实 parser/CLI 组件测试不计作隔离单元覆盖率。

持久报告：

- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round7-unit/summary.json`
- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round7-unit/coverage.json`
- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round7-unit/html/index.html`

### 完整回归：未通过，按技能暂停

实际执行命令如下（此命令遗漏 AVX 样本挂载，不作为推荐复跑命令）：

```powershell
docker run --rm --cpus 2 --memory 2g --memory-swap 2g --network none --read-only --tmpfs /tmp:size=1g --cap-drop ALL --security-opt no-new-privileges --mount 'type=bind,source=D:/projects/RvPort/tools/kb-scanner,target=/workspace/tools/kb-scanner,readonly' -w /workspace/tools/kb-scanner rvport-kb-scanner-test:local tests/run_container_tests.py --regression-only
```

运行 241 项，325.630 秒，**6 failures、6 errors，退出 1**；计数包含子测试失败及类初始化错误，不直接相减成通过数。全部输出持久保存于 `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round7-regression.log`。

失败分为三类，不能全部归因于容器：

1. **测试容器漏挂 AVX 样本**：4 个 setUpClass 错误、1 个读取历史源码的 FileNotFoundError、2 个 AVX 断言失败。旧独立容器确认样本宿主目录为 `D:/projects/RvPort/backend/runtime/kb-scan-real/avx-avx2-example-code`。下一轮必须恢复只读挂载 `/fixtures/avx-avx2-example-code`，并满足历史合同测试对 `/workspace/backend/runtime/kb-scan-real/avx-avx2-example-code` 的路径要求；不要修改生产容器。
2. **前端合同尚未补齐**：新增 usage_scope Evidence 缺少既有 `metadata.identityVersion`，导致正式前端测试 KeyError；不能仅删除断言绕过。显式 vocabulary 测试未加入 usage_scope，module inventory 数量仍断言 10，而正式模块现为 12。需修复实现元数据并同步维护准确的合同测试。
3. **固定报告对照不一致**：source-evidence-chain 与 architecture-enum 的 V2 JSON 摘要不同。前者期望 `e5eb460edb18bface416b8b2e5ba81f66aaec41f040a72d6fbc4591fa36f66b2`、实际 `439837776b1aeacd869aaee9f3d69088f9689fe5e8fc1c2b73d5d212bb875786`；后者期望 `b771e955fef9922e2be58e665cf021cbc058863c2731946a0b80c1c4a2ae4aa6`、实际 `8169e783d11b1f07eea38bf0e22f1389e745f3cb53bf941b8db8aa3b89c04020`。尚未做逐字段差异审校，不能假定都是允许的新扩展变化，也未更新 golden 或摘要。失败后的 log/HTML 断言未被执行，不能宣称这两个 fixture 的三工件验收通过。

本轮真实用途 CLI 4 项、原生崩溃缩减反例及三个固定项目正常退出测试均在回归中通过，但不替代完整回归与性能验收。未执行接入后的 libarchive 两轮性能和 10000/20000 引用规模测试；不得拿修改前基线替代。任务 6.4/6.5 保持未完成，最终质量验收不通过。

OpenSpec strict 通过；已跟踪 scanner 文件 `git diff --check` 无空白错误（只有 CRLF 提示）；两份 compiler facts SHA-256 与首轮记录一致。未安装宿主依赖、修改生产容器或其他 scanner，未同步、归档、提交或推送。临时路径选择项目报告未重生成。

根据 `openspec-apply-change` 技能，遇到回归错误暂停实现并保留现场。下一步继续 apply，优先修复上述合同和测试环境、审校报告差异，再完成剩余证明边界及性能验收；OpenSpec 根仍是 `tools/kb-scanner`：

```text
/opsx:apply implement-kb-scanner-candidate-usage-proofs
```

## 2026-09-23：第六轮 apply 暂停，仍为 5/24 项完整完成

### 已修复与验证

- 投影读取正式 DTO 的 `canonical_value`，不再访问不存在的 `value`；新增断言验证输出的 symbol 为原候选值 X86。
- 没有 candidate usage catalog 时不初始化 SemanticAdmissionIndex，也不访问 relations/proofs/classifications；新增最小替身单测核查该快速路径。旧 mapper 和 Autoconf 隔离单测恢复通过，未放松生产合同。
- 真实语法组件与用途 analyzer 5 项通过（0.122 秒）。它们不是默认 CLI 全链路验收，不替代剩余组件/回归任务。

```powershell
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_usage_projection tests.unit.schema_v2_projection.test_projector tests.unit.schema_v2_projection.test_finding_mapper tests.unit.schema_v2_projection.test_renderers tests.unit.autoconf.test_projection -v
docker exec kb-scanner-cmake-verify python -m unittest tests.test_candidate_usage_frontend tests.unit.test_usage_analysis -v
```

第一条 22 项测试中 20 项通过、1 failure、1 error，耗时 0.558 秒。第二条 5 项通过。

### 本轮暂停原因：两个先前被字段错误遮挡的测试问题

1. `tests/unit/test_usage_projection.py:55` 已取出 namespace 内层的 report，却与再次调用得到的外层字典比较。应比较 `projection.report()[NAMESPACE]`，保留重复调用确定性的断言。
2. 同文件第 66 行 `replace(proof, truncated=True)` 保留了原 status=complete，触发 ProofPath 构造器禁止完整证明截断的 ValueError。测试意图是验证部分证明不被排除，应构造 `status="partial", truncated=True`；若专测不合法 DTO，使用明确的替身，不修改 DTO 保护规则。本次该异常之后的准入断言尚未运行。

按 openspec-apply-change 的错误暂停要求，保留现场，未继续修复。此前实际投影字段访问错误已修正，但不能据此宣称所有投影行为通过；任务 5.1/5.2/6.4 保持未完成，当前仍不具备归档条件。

### 完整隔离覆盖率

工作目录为 `D:/projects/RvPort/tools/kb-scanner`，输出目录预先新建：

```powershell
docker run --rm --cpus 2 --memory 2g --memory-swap 2g --network none --read-only --tmpfs /tmp:size=512m --cap-drop ALL --security-opt no-new-privileges --mount 'type=bind,source=D:/projects/RvPort/tools/kb-scanner,target=/workspace/tools/kb-scanner,readonly' --mount 'type=bind,source=D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round6-unit,target=/output' -w /workspace/tools/kb-scanner rvport-kb-scanner-test:local tests/run_source_chain_unit_tests.py --output /output
```

675 项单测，673 项通过、1 failure、1 error，16.927 秒，退出 1。整体行覆盖率 98.43103582858481%，分支覆盖率 94.91957630443311%；本轮修改的 `projection/v2/candidate_usage.py` 行/分支均为 100%。登记模块覆盖率失败集合为空，但因测试失败 `passed=false`，质量验收未通过。

统计 171 个完整 kb_scanner/scripts/tools 自有源码文件，含未加载源码；仅排除第三方、规则数据、测试资产及非部署 archive，不缩小业务代码范围。全部逐模块数据和可浏览报告分别持久保存于：

- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round6-unit/summary.json`
- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round6-unit/coverage.json`
- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round6-unit/html/index.html`

OpenSpec strict 通过；已跟踪 scanner 文件 diff --check 无空白错误（仅 CRLF 提示）；两份 compiler facts 哈希不变。未部署、同步、归档、提交或推送，没有安装宿主依赖。没有重新生成临时路径选择项目报告。

下一阶段仍为继续 apply，先修复上述测试，再验证默认 CLI 的正反例和剩余设计边界。聊天命令（OpenSpec 根 tools/kb-scanner）：

```text
/opsx:apply implement-kb-scanner-candidate-usage-proofs
```

## 2026-09-23：第五轮 apply 暂停，5/24 项完整完成

### 本轮完成

- 修复第四轮 Entity 集合断言，按 ID 查找并比较完整实体，验证已有实体内容保留；原先因错误提前中断的 Observation 不变、Classification 省略及乱序稳定性断言均已运行通过。
- 更新函数多版本阶段单测，为新增 usage stage 注入独立替身，验证失败/不可用时不继续调用；用途 stage 单测补充 UNAVAILABLE。没有为了测试接受生产 knowledge=None。
- 真实 grammar 组件移除额外 parser 和手工 collect，直接使用默认 TreeSitterCppAdapter 生成的 usage_scope，避免重复注入。该组件仍不是完整默认 CLI 验收。
- 完成任务 4.1、4.2：严格 role/闭包消费者及默认 composite 接入已有相应纯快照单测；本轮全量检查中这些测试通过，semantic_admission 和 composite 均为 100% 行/分支覆盖。

```powershell
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_usage_analysis tests.unit.test_function_multiversion_pipeline tests.test_candidate_usage_frontend -v
```

18 项全部通过，0.211 秒。包含真实 parser 组件，不能全部计为隔离单测覆盖。

### 新增投影草稿及失败现场

新增 `projection/v2/candidate_usage.py`，接入 mapper/projector/renderers。草稿为保留项生成 Finding 内用途来源，为实际通过准入且未分类的候选生成顶层 excludedCandidates；设计包含双语说明、来源裁剪、复用 SourceContextProjector 的上下 20 行和 HTML 转义。新模块已登记覆盖 inventory，新增纯快照单测，**但实现尚未通过测试，任务 5.1/5.2 不勾选**。

定向命令：

```powershell
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_usage_projection tests.unit.schema_v2_projection.test_projector tests.unit.schema_v2_projection.test_finding_mapper tests.unit.schema_v2_projection.test_renderers -v
```

21 项测试，1 failure、15 errors（包含子测试），0.369 秒，退出 1。随后完整检查发现同类 Autoconf 测试替身错误。

明确问题：

1. 新投影 `_view` 错误访问 `NormalizedFact.value`；实际 DTO 定义为 `canonical_value`（core/facts.py）。这是实现缺陷，不是纯测试问题；带用途项的 V2 投影会因此失败。下一轮应正确读取 canonical_value，保留正常和缺失 Fact 的断言。
2. 新投影构造时立即索引所有 relations/proofs/classifications，旧 mapper 与 Autoconf 隔离测试的 SimpleNamespace 只有历史依赖，因此出现 AttributeError。应按真实合同补齐测试替身或显式注入用途投影；同时实现无 catalog 快速路径，避免无需求也重新索引整图，不要静默吞掉正常数据的缺失。
3. mapper 的 chain.build 未调用断言失败是前述构造失败的下游结果，不能删除断言绕过。

按 openspec-apply-change 错误暂停规则保留失败现场，本轮未继续修复新错误。当前工作树不具备发布条件。之前临时路径选择项目的 HTML/JSON 来自本轮投影修改之前，未重写，不能用它声称新投影已通过。

### 完整隔离单元与覆盖率（未通过）

工作目录 `D:/projects/RvPort/tools/kb-scanner`，输出目录预先新建：

```powershell
docker run --rm --cpus 2 --memory 2g --memory-swap 2g --network none --read-only --tmpfs /tmp:size=512m --cap-drop ALL --security-opt no-new-privileges --mount 'type=bind,source=D:/projects/RvPort/tools/kb-scanner,target=/workspace/tools/kb-scanner,readonly' --mount 'type=bind,source=D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round5-unit,target=/output' -w /workspace/tools/kb-scanner rvport-kb-scanner-test:local tests/run_source_chain_unit_tests.py --output /output
```

675 项测试，1 failure、16 errors（错误含子测试，不能直接从 testsRun 相减计算通过用例数），单测耗时 17.394 秒，退出 1。整体行覆盖率 98.27465063627137%，分支覆盖率 94.72135007849293%；171 个自有源码文件，包含未加载源码。

| 本轮新增/接入或验收模块 | 行覆盖率 | 分支覆盖率 |
| --- | ---: | ---: |
| projection/v2/candidate_usage.py | 80.65% | 75.00% |
| projection/v2/mapper.py | 95.88% | 93.75% |
| projection/v2/projector.py | 100% | 100% |
| projection/v2/renderers.py | 100% | 100% |
| classifiers/semantic_admission.py | 100% | 100% |
| classifiers/usage_proof.py | 98.57% | 95.65% |
| pipeline/composite.py | 100% | 100% |
| detectors/local.py | 100% | 95.31% |

唯一低于覆盖率门槛的登记模块为新 candidate_usage 投影；单测也失败，因此 passed=false。完整 scope 仍为 kb_scanner/scripts/tools，不因失败缩小范围；排除第三方、规则数据、测试资产和非部署 archive，不排除业务代码。

持久报告：

- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round5-unit/summary.json`
- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round5-unit/coverage.json`
- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round5-unit/html/index.html`

两份 compiler facts 哈希未变。OpenSpec strict 通过，已跟踪文件 git diff --check 无空白错误（仅 CRLF 提示）。没有新增宿主依赖，没有修改其他 scanner 或生产容器，没有提交、推送、同步或归档。完整回归、修改后 libarchive/规模性能、V1/V2/HTML 差异及排除审计仍待执行。

下一阶段仍为继续 apply，先修复投影，不具备归档条件（聊天命令，OpenSpec 根 tools/kb-scanner）：

```text
/opsx:apply implement-kb-scanner-candidate-usage-proofs
```

## 2026-09-23：第四轮 apply 暂停，3/24 项完整完成

### 经用户确认的新基线

用户同意新增 822 文件基线，保留旧 810 文件清单及审校记录。新增 `tests/fixtures/candidate-usage-performance/`，通过引用旧清单并追加 12 个 CMake 文件固定输入；合并时拒绝覆盖旧条目。资源门槛仍为 2 CPU / 2 GiB / 无额外 swap / 每轮 300 秒。设计与 delta spec 已同步这一批准，不改旧 golden。

终端工作目录为 `D:/projects/RvPort/tools/kb-scanner`：

```powershell
./tests/run-performance-container.ps1 -Source 'D:/projects/RvPort/.codex-tmp/kbscanner-sources-clean-20260909/libarchive' -Output 'D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/baseline-libarchive-822' -FixtureDir tests/fixtures/candidate-usage-performance
```

两轮正常退出 0，分别耗时 177.443 / 190.565 秒，峰值 RSS 为 726616 / 725068 KiB。每轮 822 文件、80 Observation、64 finding（53 issues、11 hints），semanticDigest 一致。这是**接入默认用途 producer 之前**的默认行为基线，不是接入后性能验收；运行期间新模块尚未被默认管线使用，不宣称整个工作树冻结不变。报告持久保存在上述输出目录的 `benchmark/performance.json` 和 `benchmark/{1,2}/report/`。

两份 compiler facts 的 SHA-256 与首轮记录一致。新输入清单 digest 为 `f52edca120bdcd98d6c3316a2c5a42c09e38a99fc2189fa07b33cd3eb85fd67c`。

### 本轮实现和定向验证

- 修复字段表达式绑定：区分对象参数与成员名，对未消解的潜在使用保留 unknown，字段逃逸反例不再被判为完整闭包。
- 规范化重新核查绑定合同与引用关系，完成任务 2.3。当前勾选为 1.2、2.3、3.1。
- 新增共享查询 session、作用域缓存、局部及扫描预算、proof 生成和严格消费者校验；完整记录、使用计数、源码引用与依赖连通性均须成立才能采用 non_execution_data。
- 默认 Tree-sitter frontend / CompositeAnalyzer 已接入新阶段，Detector 排除用途专用非执行关联。接入后的完整默认管线验收仍未完成。
- 真实 Tree-sitter 组件的 2 项测试通过，覆盖纯局部数据和调用/return/字段写入等未知边界；该测试当时手工拼接 usage inventory，不是默认 CLI 验收。默认接入后须移除重复拼接并重新验证。
- proof producer、validator 与旧语义准入合跑 13 项通过。最后一组 frontend / analyzer 定向测试 35 项中 34 项通过、1 error。

### 暂停原因及后续修复

1. `tests/unit/test_usage_analysis.py:34` 使用 `set(base.entities)`，Entity 的字典属性不可哈希，触发 `TypeError: unhashable type: 'dict'`。应改用实体 ID 集合或逐实体比较，保留实体内容未丢失的有效断言。该测试后续的 Observation 不变、Classification 省略与稳定性断言尚未执行，不得声称已通过。
2. 完整单元检查还发现旧 `test_function_multiversion_pipeline.py:278` 阶段顺序测试仅替换旧阶段，新增默认 usage 阶段收到 `knowledge=None`，触发 AttributeError。应更新该隔离测试的阶段依赖与有效输入，并验证新增阶段的失败/部分完成传播；不要为测试盲目放宽生产知识库合同。

按 openspec-apply-change 技能的错误暂停规则，本轮保留失败现场，没有继续修改这两处错误。报告投影、顶层排除审计、真实默认 CLI、完整回归、接入后的两轮 libarchive 和规模性能测试均未完成；不能归档。

### 本轮完整单元覆盖率（质量验收未通过）

```powershell
docker run --rm --cpus 2 --memory 2g --memory-swap 2g --network none --read-only --tmpfs /tmp:size=512m --cap-drop ALL --security-opt no-new-privileges --mount 'type=bind,source=D:/projects/RvPort/tools/kb-scanner,target=/workspace/tools/kb-scanner,readonly' --mount 'type=bind,source=D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round4-unit,target=/output' -w /workspace/tools/kb-scanner rvport-kb-scanner-test:local tests/run_source_chain_unit_tests.py --output /output
```

670 项测试，668 项通过、2 error、0 assertion failure；单测耗时 15.941 秒，进程退出 1。统计 170 个自有源码文件，整体行覆盖率 98.40295806781528%，分支覆盖率 94.84597156398104%。登记模块覆盖率失败集合为空，但 `passed=false`，不能用覆盖率替代单测通过。

| 本次受影响模块（相对 kb_scanner） | 行覆盖率 | 分支覆盖率 |
| --- | ---: | ---: |
| analyzers/candidate_usage/analysis.py | 100% | 100% |
| analyzers/candidate_usage/proofs.py | 100% | 100% |
| analyzers/candidate_usage/session.py | 99% | 97.62% |
| analyzers/candidate_usage/index.py | 98.59% | 94.44% |
| analyzers/candidate_usage/closure.py | 97.73% | 95% |
| analyzers/candidate_usage/demand.py | 100% | 100% |
| classifiers/usage_proof.py | 98.57% | 95.65% |
| classifiers/semantic_admission.py | 100% | 100% |
| frontends/cpp/usage_bindings.py | 100% | 97.50% |
| frontends/cpp/usage_inventory.py | 97.96% | 95% |
| frontends/cpp/frontend.py | 98.39% | 96.43% |
| frontends/cpp/tree_sitter_adapter.py | 96.56% | 90.24% |
| frontends/cpp/vocabulary.py | 100% | 100% |
| normalization/usage.py | 98.77% | 98.15% |
| normalization/cpp.py | 95.45% | 95.45% |
| pipeline/composite.py | 98.43% | 93.33% |
| detectors/local.py | 100% | 95.31% |

candidate_usage/__init__.py 无可执行语句，分支指标不适用。统计范围仍为完整 `kb_scanner`、`scripts`、`tools`，包含未加载源码；排除测试资产、非部署 archive、规则数据和第三方依赖，不排除自有业务逻辑。下一轮还须检查专用 frontend 门禁能加载新根目录单元测试，以及受影响模块自动门禁登记完整性。

持久报告：

- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round4-unit/summary.json`
- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round4-unit/coverage.json`
- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round4-unit/html/index.html`

OpenSpec strict 校验通过；已跟踪 scanner 文件的 `git diff --check` 无空白错误（仅 CRLF 提示）。本轮未同步、归档、提交、推送或部署，没有安装本机依赖或变更生产容器。

下一阶段仍为继续当前 apply（聊天命令；OpenSpec 根为 `tools/kb-scanner`）：

```text
/opsx:apply implement-kb-scanner-candidate-usage-proofs
```

## 2026-09-23：第三轮 apply 暂停，仍有 2/24 项完整完成

### 本轮实现

- 修复第二轮诊断优先级问题：先检查父引用存在性，再检查子端点和反向成员关系。重跑原 16 项单测通过。
- `CppEvidenceNormalizer` 已接入 usage_scope 记录验证和合并；无效记录不生成用途 Fact，但保留原 Evidence 和其他原有 Fact。多配置作用域分离，多 producer 冲突保留 partial，原有 Fact 身份保持不变。相关 23 项定向测试通过。
- 新增 `usage_bindings.py`，在纯标量树上记录块级声明绑定、读写、遮蔽和深度限制；采集函数调用此绑定模块，未接入默认 Tree-sitter adapter。新增绑定测试 6 项通过，与现有用途测试合跑共 25 项通过。
- 新增 `candidate_usage/index.py` 和 `closure.py` 草稿，构建局部数据/控制关联并按节点、边、深度预算查询。尚无 proof producer、默认 Analyzer 接入或报告投影。
- 所有新增业务模块均登记隔离覆盖 inventory。任务 2.3 的基础结构已通过，但新增 binding 引用仍需一致性校验，因此重新保留为未完成；任务 2.1/2.2/3.2 也未勾选。

### 阻塞 1：字段访问可能漏掉候选用途

首次闭包测试为 5 项中 4 项通过、1 项失败：`test_controlled_call_and_value_escape_keep_unknown` 预期 unknown，字段访问分支实际返回 complete。

只读复核发现 call、return、取址、循环均返回 unknown，唯独 field_expression 返回 complete。当前绑定模块对字段访问的 identifier 一律取消局部绑定，导致索引无法将潜在相关使用连接回候选根。下一轮应区分字段表达式的对象参数与成员名，并对无法消解的潜在引用保持 unknown；必须保留此负例，不得删除断言或用名称白名单绕过。

这是新增未接入模块的实质性错误。默认 frontend、Analyzer、Detector、Classifier 和 projector 均未切换到新用途分析，现有默认结果不受此草稿错误影响。按 apply 技能要求暂停，不将质量验收标为通过。

### 阻塞 2：固定 libarchive 输入清单已落后于当前采集能力

执行原有性能容器脚本：

```powershell
./tests/run-performance-container.ps1 -Source 'D:/projects/RvPort/.codex-tmp/kbscanner-sources-clean-20260909/libarchive' -Output 'D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/baseline-libarchive'
```

独立容器使用 2 CPU / 2 GiB / 无额外 swap，预检报 `fixture input set mismatch` 后退出 1，未进入有效扫描性能验收；OOMKilled=false。该一次性容器已由原脚本清理，不影响旧独立单测容器或生产容器。

后续只读核对确认：原 `input-manifest.json` 的 810 个文件全部存在且 SHA-256 一致，无缺失、无内容变化。当前采集为 822 个文件，新增输入恰为以下 12 个 CMake 文件：

```text
CMakeLists.txt
CTestConfig.cmake
cat/CMakeLists.txt
cat/test/CMakeLists.txt
cpio/CMakeLists.txt
cpio/test/CMakeLists.txt
libarchive/CMakeLists.txt
libarchive/test/CMakeLists.txt
tar/CMakeLists.txt
tar/test/CMakeLists.txt
unzip/CMakeLists.txt
unzip/test/CMakeLists.txt
```

这不是源码副本损坏，而是早期 810 文件清单没有包含后续已支持的 CMake 输入。建议经确认后保留旧清单与旧审校账本，新增当前 822 文件验收基线，并相应修订本 change 的固定数量；继续保留资源和单轮 300 秒门槛。本轮未更改 golden、旧 manifest、性能门槛或扫描排除项。

### 完整隔离单元与覆盖率（未通过质量验收）

```powershell
docker run --rm --cpus 2 --memory 2g --memory-swap 2g --network none --read-only --tmpfs /tmp:size=512m --cap-drop ALL --security-opt no-new-privileges --mount 'type=bind,source=D:/projects/RvPort/tools/kb-scanner,target=/workspace/tools/kb-scanner,readonly' --mount 'type=bind,source=D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round3-unit,target=/output' -w /workspace/tools/kb-scanner rvport-kb-scanner-test:local tests/run_source_chain_unit_tests.py --output /output
```

651 项测试，650 项通过、1 项失败、0 error，15.697 秒。失败仍为上述字段访问反例。整体行覆盖率 98.42792647533054%，分支覆盖率 94.90458790093382%；覆盖统计 166 个自有源码文件，含未加载文件，覆盖率失败集合为空，但 `passed=false`，因为单测失败。

| 本次受影响模块 | 行覆盖率 | 分支覆盖率 |
| --- | ---: | ---: |
| frontends/cpp/usage_inventory.py | 98.84% | 97.06% |
| frontends/cpp/usage_bindings.py | 100% | 97.22% |
| normalization/usage.py | 100% | 100% |
| normalization/cpp.py | 95.45% | 95.45% |
| analyzers/candidate_usage/demand.py | 100% | 100% |
| analyzers/candidate_usage/index.py | 98.53% | 96.88% |
| analyzers/candidate_usage/closure.py | 100% | 100% |
| analyzers/candidate_usage/__init__.py | 无可执行语句 | 不适用 |

统计范围仍为完整 `kb_scanner`、`scripts`、`tools`；排除第三方依赖、自动生成规则数据、测试资产、非部署 archive，未排除自有业务逻辑。报告本轮已通过可写输出挂载持久保存：

- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round3-unit/summary.json`
- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round3-unit/coverage.json`
- `D:/projects/RvPort/.codex-tmp/kbscanner-candidate-usage-20260923/round3-unit/html/index.html`

两份 compiler facts 内容与此前记录哈希不变。本轮未跑修改后的完整回归，也未通过真实 parser、V1/V2/HTML 对照或性能验收；不得引用第一轮的 251 项基线回归冒充本轮通过。未提交、推送、同步、归档或部署。

## 2026-09-23：第二轮 apply 暂停，2/24 项完成

已修复首轮 `Evidence` 位置参数错误，改为显式 `metadata=`；文件预算现已累计候选函数内部访问记录，新增预算边界单测。使用采集模块 6 项单测通过，但尚未实现词法绑定或接入默认前端，任务 2.1/2.2 继续未完成。

已实现任务 3.1 的 `CandidateUsageDemand`：复用现有 KnowledgeIndex、match_fact 和候选覆盖判断；按 Detector 原有约定生成 fact/subject/configuration/matchedEvidenceIds，已被枚举引用覆盖的声明不生成额外需求，多配置未消解时不宣称完整。5 项隔离单测通过，其中包含与现有 Detector 输出逐字段对照。尚未接入默认 Analyzer。

新增 `normalization/usage.py` 草稿用于标量记录形状、父子端点、源码范围、计数和 producer/配置冲突校验；新增模块已登记 `tests/source-chain-test-inventory.json`，没有缩小整体覆盖统计范围。规范化尚未接入 `CppEvidenceNormalizer`，任务 2.3 未完成。

容器执行命令：

```powershell
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_usage_inventory tests.unit.test_usage_normalization tests.unit.test_usage_demand -v
```

结果：16 项，15 项通过、1 项断言失败。失败位于 `UsageNormalizationTests.test_references_and_partial_endpoint`：测试把子记录 parent 改为无效值后，预期 `usage-invalid-parent`，但校验按父记录先行的顺序返回 `usage-conflicting-parent`。输入仍被拒绝，没有被错误接受为完整证明。下一轮需明确两类诊断的优先级、修正对应测试或实现并重跑；本轮按 apply 技能的错误暂停规则未继续修复。

此次未执行新增代码整体/受影响模块覆盖率或完整回归；首轮基线数字不代表本轮达标。没有默认输出变更，没有修改生产容器或其他 scanner，未同步、归档、提交或推送。当前不能进入归档阶段，仍需继续 apply。

## 2026-09-23：首轮 apply 暂停，1/24 项完成

本轮仅完成任务 1.2 的人工用途 oracle。新增 usage inventory 和对应单元测试仍为未接入默认管线的草稿，首次测试失败；不得将基线通过解释为本 change 验收通过。未修改生产容器、后端、前端或本机依赖，未提交、推送、同步或归档。

### 修改前基线

复用独立容器 `kb-scanner-cmake-verify`，镜像 `rvport-kb-scanner-test:local`。以下为终端命令，宿主工作目录为 `D:/projects/RvPort/tools/kb-scanner`。

```powershell
docker exec kb-scanner-cmake-verify python tests/run_source_chain_unit_tests.py --output /tmp/candidate-usage-baseline-unit
docker exec kb-scanner-cmake-verify cp -a /workspace/tools/kb-scanner /tmp/candidate-usage-baseline-code
docker exec -w /tmp/candidate-usage-baseline-code kb-scanner-cmake-verify python tests/run_container_tests.py --regression-only
```

- 隔离单元：621 项通过，耗时 36.350 秒；整体行覆盖率 98.39474340846711%，分支覆盖率 94.77013918177984%，模块门禁失败集合为空。
- 统计范围：159 个自有源码文件，覆盖 `kb_scanner`、`scripts`、`tools`，含未被加载的源码。测试资产、非部署 archive、自动生成规则数据与第三方依赖不属于自有可执行业务代码统计范围。
- 修改前冻结副本的完整回归：251 项通过，耗时 293.410 秒。该回归不是新增模块验收。
- 覆盖率原始报告在容器 `/tmp/candidate-usage-baseline-unit/summary.json`、`coverage.json` 和 `html/`。尝试 `docker cp` 导出失败，但随后容器内确认文件仍存在。**尚无成功导出的持久报告；容器 `/tmp` 为临时存储，停止容器可能丢失。** 本文件只持久记录摘要，不替代完整报告。
- 本容器未设置本 change 要求的 2 CPU/2 GiB 限制；以上不构成真实项目性能验收。

两份保留事实数据的 SHA-256 未改变：

| 文件 | SHA-256 |
| --- | --- |
| `clang-x86-entries.json` | `adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7` |
| `gcc-x86-entries.json` | `89775341ee880b13ac4f10a30558ff5d52875b25a3233114a5765601f0a9dad9` |

任务 1.1 尚未完成：仍需固定报告对照、无候选工件和本次真实项目扫描配置等内容。

### 人工 oracle

`tests/fixtures/candidate-usage-oracle.json` 已通过 JSON 结构校验，包含 12 个独立人工案例及必要变体要求。覆盖闭合局部数据、未知调用、return、控制 intrinsic、字段逃逸、开放定义、遮蔽、混合用途、宏重定义、不支持循环和注释边界。历史 libarchive 26 项仅为人工审校对象，不作为生产规则。

### 新增模块失败现场

```powershell
docker exec kb-scanner-cmake-verify python -m unittest tests.unit.test_usage_inventory -v
```

结果：5 项测试中 1 项通过、4 项错误，均出现 `KeyError: 'usageScope'`。

原因：`kb_scanner/frontends/cpp/usage_inventory.py` 构造 `Evidence` 时将 `{"usageScope": ...}` 作为第 9 个位置参数传入，而该字段实际为 `knowledge_sources`；因此 `metadata` 为空。下一次 apply 应改为显式 `metadata=`，重新执行测试。此次按 apply 技能的错误暂停规则保留现场，未继续修复。

还需检查并补齐文件节点总预算：外围遍历在函数节点处跳过子树，当前函数内部采集尚未计入文件级累计预算。新模块未登记完整 unit inventory，也未接入前端、规范化、分析器和默认管线。不得勾选任务 2.1、2.2 或质量验收。

新增代码整体及受影响模块覆盖率尚未执行，不能沿用修改前的 98.39%/94.77% 声称本次达标。

### 后续阶段

继续当前 apply，修复上述错误后执行剩余任务；目前不具备同步归档条件。聊天命令：

```text
/opsx:apply implement-kb-scanner-candidate-usage-proofs
```
