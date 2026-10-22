# 原始测试内容分析实施审校（已完成）

apply 的实现与验收已完成，已于 2026-09-28 同步主规格并归档。工作目录为 `D:/projects/RvPort/tools/kb-scanner`；尚未提交、推送或部署。全部临时报告根目录为 `D:/projects/RvPort/.codex-tmp/test-content-20260924`，下文短路径均相对此根目录。

## 固定边界

- 只修改 Scanner 与本 change 的文档/测试；其他任务的 floating-point-precision-scanner、memory-order-analyzer 修改不纳入。
- 独立 `rvport-kb-scanner-test:local` 镜像；不在宿主机安装依赖，不执行原始项目命令，不修改生产服务。
- 手写 oracle：`tests/fixtures/test-content/oracle.md`；两份 generated facts 与 libarchive 822 文件 manifest 的固定摘要均记录于其中。旧 810 文件不改。
- 基线报告：仓库 `.codex-tmp/test-content-20260924/{before-v1,before-v2}`；实现中的报告为 `after-first`，不是最终验收结果。

## 局部设计落实

- CMake `enable_testing` / 新式 `add_test` / 字面 `DISABLED` 形成独立注册记录，不修改既有 source 编译选择。
- `test_inventory` 在原生树有效期内复制标量；`test_content_structure` 建立一次函数/局部用途索引；`test_content` 以既有知识事实查询并复用宏事件索引。
- 函数同名不能证明跨 TU、声明/重载、包含文件中的重载或递归；这些边界明确 unknown。Make/RPM/CTest 已确认的源成员关系可提供语境，不补造入口注册。
- 标准 assert 首版来源确认采用已有 Clang 的宏实例→定义引用和**系统头+精确 glibc token profile**。只记录当前观测 TU 的 enabled/disabled/unknown；不把 x86 compile database 的 NDEBUG 借给目标 RISC-V。其他 libc/profile、缺少编译上下文及未知覆盖均 unknown。无需执行预处理器命令或新增完整预处理系统。
- 两份编译器知识不改；新数据只进入可选 `org.rvport.kb-scanner.test-content` namespace，不改 V2 核心或后端接口。V1 仍显式兼容。

## 已执行记录

| 执行 | 结果/处置 |
|---|---|
| unit-01 | 795 项，旧 selector Mock 缺少新接口，已修正 fake 边界；未当作通过 |
| unit-02 | 802 项，旧测试把同文件事实直接当测试 exercises；按需求修正 oracle，保留 fact 断言 |
| unit-03 | 821 项通过；188 文件整体行 98.719%、分支 95.779%，登记模块全部至少 90%/90%；后续新增内容仍需终验 |
| 新真实组件首轮 | 8 项中 7 项通过，1 项测试误用 `source.span.start.path` 而非既有 `source.file`；已修正测试，不改核心 schema |
| 全回归首次命令 | 挂载 `/scanner` 但直接脚本入口加载镜像内旧包，且未挂 AVX fixture；已停止该错误环境运行，不据此重写历史期望 |
| 全回归环境修复 | 使用 `PYTHONPATH=/scanner`、`-m tests.run_container_tests` 及只读 AVX fixture；结果待收集 |
| 正确包路径的回归轮次 | 277 项，10 failures/1 error；新增结构计数/专项 inventory 已修正，非测试清单 partial 不再外溢成项目告警。最终需改用原容器根路径以保持 V1 absolute project.root 的历史哈希 |
| unit-04 | 830 项通过但新规模入口分支只有 80%，质量门禁失败；补充无 catalog/非 catalog 返回分支，不降低阈值 |
| unit-05 | 830 项通过，190 文件整体行 98.704%、分支 95.787%，全部登记模块至少 90%/90%；之后增加的回归/边界仍需终验 |
| 最小真实组件定向轮次 | 当时的 8 项全部通过：直接/局部绑定、未调用/一跳/重载/runtime、重写/逃逸/lambda、NDEBUG/覆盖、V1、20/20 与来源闭合 |
| 无关 zlib-shape 结构审校 | 30→35 Evidence/Fact，仅增加 4 个真实函数结构和 1 个内容清单；Observation/Classification 仍为 3/3，不改知识或风险 |
| noise-diff-02 | 关闭/开启内容清单的 V1/V2 JSON 分别完全相同。V1 与旧哈希不同是 `/scanner` 与原 `/workspace/tools/kb-scanner` 的 project.root 差异；不批准替换历史哈希 |
| libarchive-01 | manifest 822 文件通过，2 CPU/2 GiB/无 swap；第一进程 300.252 秒 timeout、exit 124，未发布完整报告。收集 18.143 秒、知识 1.852 秒、前端 220.520 秒；止于归一化。不得算通过，第二轮未执行 |

`libarchive-01` 是中间诊断运行，源码在此阶段仍补边界，不能作为最终源码验收。失败工件/事件保留。正在测量新增内容提取 CPU/墙钟成本与前端总成本，区分算法和运行环境因素；尚未放宽门槛。

单元结果目录：`.codex-tmp/test-content-20260924/unit-03/{summary.json,coverage.json,html}`。隔离运行禁止真实 parser，组件运行单独统计。

### 最终候选代码的阶段验证

- `unit-07`：833 项全部通过；统计全部 190 个自有生产文件（包括未加载源码），整体行覆盖率 **98.697738%**、分支覆盖率 **95.760135%**，登记模块全部达到 90%/90%。新规模入口为 90.32258%/90%，不降低门槛。完整报告在 `unit-07/{summary.json,coverage.json,html/}`。
- `regression-03`：279 项，2 failures/1 error。结构记录缺少 identityVersion 已补齐并经上述单元覆盖；两项报告签名差异已逐字段审校。未将该轮算作通过。
- 报告差异基线是 Git `9d331c6622a21cad13bb1c6ed4c69a127deb558c` 的只读归档，当前和基线使用相同 canonical fixture 路径。build-selection / workspace-escape 仍是 8 Findings、1 blocking、1 high/7 medium；删除的是编译数据库参数因为文件共现而生成的测试 occurrence/exercises，独立编译参数 Finding 和 Makefile 构建来源保留。追加 `tests/fixtures/test-content-report-differential.json`，不覆盖历史 ledger。
- `frontend-diagnostic.log`：822 文件下新清单提取墙钟 16.995 秒、CPU 16.209 秒，总前端墙钟 163.043 秒；这是诊断而非最终性能验收。随后把全扫描剩余记录预算传入原生树提取前，避免先构造再丢弃超额记录；事实采集不裁剪。
- 定向验证：报告差异 4 项均通过；新反例最初错误地禁止所有同名 -march 来源，已改为禁止 compile_argument 的错误内容关联，允许原有 Makefile 构建选择。一次定向命令误写不存在的 test_cpp_frontend 模块，后续完整回归使用真实 test_formal_cpp_frontend；不忽略错误或算作通过。

## 最终门禁与审校

### 原始内容配对审校

`component-final.log`：11 项真实组件测试全部通过（18.108 秒），真实 Tree-sitter 与 Clang 分开于隔离单元统计。

| 手写输入/反例 | 实际语义与判断 |
|---|---|
| main 直接 assert intrinsic | 原始 intrinsic 保留，关联 assert-argument；没有标准头和目标宏证明时 assertion unknown，不声称执行成功 |
| scalar 单次初始化后 assert | local-value-to-assert；重赋值、取地址传出、条件写入分别转 unknown，不能向被调函数传播断言结果 |
| 唯一同文件直接一跳 | 入口关系 complete；未调用、额外声明/重载、runtime if、lambda、框架 TEST 保留具体断点 |
| DISABLED TRUE | registration not_selected，source build selected；独立 intrinsic 仍 high/blocking |
| 仅 x86_64 CMake 分支 | intrinsic inactive、非 blocking；不是凭测试禁用降低风险 |
| NDEBUG / 本地 assert 覆盖 / 部分语法 | 原事实保留，proof unknown；真实 Clang C/C++ glibc profile 能分别观测 enabled/disabled，原生 TU 销毁后标量数据可用 |
| debug/release 同位置 | 隔离单元构造两个 producer/configuration，分别保存 enabled/disabled，目标 assertion 仍 unknown，不借用另一配置 |
| 数值 42 / sizeof(long)==8 | 没有架构来源时无 Finding |
| Codec X86_FILTER 数据 | 原候选保留；未生成 blocking 或虚构完整执行证明，继续沿用用途准入 |
| CTest source 与 -march 编译参数共现 | 测试 occurrence 2→1；独立编译参数保留合法 adds_argument，移除无依据的测试用途关系 |
| 来源与展示 | 新用途不重复计数 intrinsic；Finding 内引用闭合、每个源码位置上下 20 行、默认中文/配对英文、显式 V1 和 HTML 正常 |

`regression-04.log`：280 项，279 通过、1 个新增测试断言错误；误要求独立编译参数无任何关系，已改为仅允许合法 adds_argument，并由上述组件复跑通过。生产实现未因此变更；完整回归最终仍需整轮通过。

### 新测试内容规模矩阵

独立容器逐组运行，2 CPU/2 GiB/无额外 swap、每组 300 秒 timeout；六组均 exit 0、passed=true，三个合法工件齐全。目录为根输出下的 `scale-{10000,20000}-{plain,sparse,dense}`，各自保留 metrics.json（包含输入/源码哈希、每阶段、工件字节、访问计数与资源配置）及完整日志。

| 断言数/密度 | 秒 | RSS KiB | 内容记录 | 查询 | partial 清单 |
|---|---:|---:|---:|---:|---:|
| 10000/plain | 10.61 | 153864 | 0 | 0 | 0 |
| 10000/sparse | 11.50 | 155440 | 1223 | 3 | 0 |
| 10000/dense | 12.37 | 184300 | 10000 | 300 | 1 |
| 20000/plain | 30.64 | 244624 | 0 | 0 | 0 |
| 20000/sparse | 21.98 | 248180 | 1723 | 3 | 0 |
| 20000/dense | 24.25 | 280320 | 10000 | 600 | 1 |

普通断言不制造架构内容查询；稀疏查询不随普通 assert 数翻倍；密集内容记录命中既定上限并保留 partial/unknown，原始事实仍被采集。这不是完整测试覆盖或 RISC-V 执行成功证明。

### libarchive 语义抽查

当前首轮报告与上一已验收宏作用版本逐 ID 比较：822 文件、64 Findings、53 issues、11 hints、0 blocking 完全不变；全部结论与 evidenceChain 相同，没有新增或消失的 Finding。仅 `libarchive/test/test_read_format_rar5.c:406–408` 的注释 hint 增加可选测试语境，仍为 info/comment-only-hint、非 blocking；`DEFINE_TEST` 自定义框架不推断为普通 main，一跳/注册未证明时显示 file/candidate/unknown。保留 test-owner-not-found、test-registration-missing 和真实 20/20 来源。清单 partial 单独报告，不以该注释证明测试覆盖。

最终 `libarchive-02/benchmark/performance.json`：两轮 **270.0616 / 254.9901 秒**、exit 0，峰值 **1410852 / 1410300 KiB**；2 CPU/2 GiB/无额外 swap/300 秒门槛不变，容器 OOMKilled=false。每轮都完成三个合法工件发布，semanticDigest 同为 `f19ef24dad86cd727dc501266e0456aad1e760bc938c8d297e26cda4a746831a`。源码摘要为 `b0eddbcce8d4f8ab58db994dd5e840b90b20ace3d9287926df55066393ee5f84`，追加 `tests/fixtures/test-content/libarchive-review.json`，保留失败的 libarchive-01。旧诊断 652、新 654，新增构建解析 partial 和相关测试清单 partial；没有消除历史 unknown。

### 既有用途规模矩阵

`usage-scale-final/summary.json`：4 组/8 次全部完成，passed=true；每个子进程沿用 2 CPU/2 GiB/无 swap/300 秒门槛，所有三工件正常发布，候选根数量和既有预算断言通过。源码清单在 runtime.json，使用旧驱动的非紧凑 JSON 摘要为 `bdf4ab61707551e1c48c3988c49b54aa26dcfb8893840c323f5eea366ee40dff`；与性能工具紧凑 JSON 摘要格式不同，不直接比较两种字符串。

| 引用数/密度 | 关闭/开启秒 | 开启 RSS KiB | 开启截断根 |
|---|---:|---:|---:|
| 10000 稀疏 | 12.02 / 11.31 | 278520 | 0 |
| 10000 密集 | 68.04 / 59.19 | 823060 | 1788 |
| 20000 稀疏 | 24.16 / 25.64 | 368040 | 0 |
| 20000 密集 | 141.32 / 177.51 | 1347320 | 14928 |

密集用途截断是原有全扫描访问预算，原候选根全部保留为可审计的 unknown；不能把未完成的用途当成纯数据排除。此矩阵是回归验收，不替代隔离单元测试。

### 既有宏/TU 与最终单元

复用原 `macro-build-effects-20260924/macro-scale-inputs/{16,32}`，独立容器、2 CPU/2 GiB/无额外 swap，使用 `timeout 300 python -m tests.performance.child /fixtures/16 /output/macro-16`（32 同理）。两组 exit 0，分别 1024/2048 Findings，峰值 201456/344360 KiB；报告发布阶段 6.446/16.129 秒。每条 Findings 都核对原始 `_mm256_add_epi32` 列切片、位置唯一、high、源码链 complete、primaryPath 起于 Makefile、相邻节点确有边，所有 source 只来自当前 TU/shared.h/Makefile。没有只用数量冒充语义审校；日志和三工件位于 `macro-{16,32}` 及同名 `.log`。

最终 `unit-final` 再次 **833 项全部通过**，190 个自有生产文件（`kb_scanner`、`scripts`、`tools`，含未加载文件）整体行 **98.697738%**、分支 **95.760135%**，所有登记模块均 ≥90%/90%，failedCoverage={}、passed=true。无分支模块按无分支记为不适用，不降低总体门槛。排除仅为测试/fixtures、未部署 archive、rulesets 生成/规则数据、第三方容器依赖；不排除自有业务逻辑。`unit-final/{summary.json,coverage.json,html/}` 和 `unit-final.log` 保留全部命令结果。

### 最终完整回归与交付

`regression-05.log`：**280 项全部通过，457.198 秒**，覆盖 AVX、架构目录/Make/CMake 配对项目、三个固定上游原生崩溃样本、V1/V2/HTML/log 合同及全部新测试内容组件。这是整套测试耗时，不是单项目 300 秒性能验收。历史失败轮次均保留；没有跳过失败项或自动覆盖历史 oracle。

最小手写 fixture 用最终默认 CLI 重新生成三工件于 `demo-final-v2/`：direct 的 intrinsic 为 high/blocking 并显示 assert 参数关系；helper 未调用/注册禁用不取消编译风险；guarded 的 x86_64 分支保持 inactive。真实项目 CMake/Make/测试命令均未执行。

最终执行命令使用能力文档列出的完整 Docker 启动方式，核心入口为：

```text
python -m tests.run_source_chain_unit_tests --output /output/unit-final
python -m tests.run_container_tests --regression-only
python -m unittest tests.test_test_content_component -v
python -m tools.test_content_scale --assertions 10000 --density sparse --output /output/scale-10000-sparse
python -m tests.run_usage_scale_tests --output /output/usage-scale-final
```

规模入口实际执行全部六种组合，libarchive 使用已记录的 PowerShell 包装器两进程验收；非宿主 Python 命令。逐模块覆盖详情见 `unit-final/summary.json`，源码覆盖 HTML 见 `unit-final/html/`。

最终两份 generated facts SHA-256 与手写 oracle 完全一致。184 个 Scanner 包 Python 文件逐文件与性能 runtime.json 核对，未变化；覆盖范围还包含维护脚本/工具，共 190 个自有生产文件。OpenSpec strict、文档相对链接、新文件末尾空行及 Scanner 范围 `git diff --check` 通过。其他任务目录的修改未纳入，本机未安装依赖、生产容器未更新。

## 同步与归档（2026-09-28）

按用户授权先同步 4 份主规格：分类评估、CMake 源码分析、V2 报告各新增 2 条要求，新建测试内容分析规格含 5 条，共 11 条。逐份核对 delta 正文完全一致、原有正文保留且无重复；`openspec validate --specs --strict --no-interactive` 为 19 passed / 0 failed，当前 change strict 通过，任务 27/27 完成。

随后在 Scanner 工作目录执行 `openspec archive implement-kb-scanner-test-content-analysis --skip-specs --yes`。此处 `--skip-specs` 仅避免重复应用已经完成并校验的同步，不是省略主规格同步。CLI 对超过 10 条 delta 的拆分提示为非阻断建议。

归档到 `openspec/changes/archive/2026-09-28-implement-kb-scanner-test-content-analysis/`，移动后先核对原 9 个 artifact（包括 `.openspec.yaml`）哈希全部一致，再追加本节。开发计划与能力文档的链接同步到归档路径；本阶段只有规格及文档操作，未改实现/测试、未重跑代码覆盖率，保留前述实际验收记录。

当前 change 的 OpenSpec 流程结束。未自动提交、推送或部署，无后续必需的 OpenSpec 命令。
