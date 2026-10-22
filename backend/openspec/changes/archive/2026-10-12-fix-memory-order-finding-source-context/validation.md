# 验证记录（2026-10-12）

## 范围和诊断

用户已授权修改 `tools/memory-order-analyzer`，本次未修改前端或浮点工具。工作区同时存在
其他线程的浮点证据修复与共享 BC 改动，未撤销、提交或混入本次已验证 JAR。

本地开始排查时没有 MEMORY_ORDER Finding，不能声称复现了用户原始记录。本次建立了独立
源码 fixture，并由正式 API 创建项目、环境配置、上传、x86 构建及内存序扫描。

确认的断点：

1. 正式 publication / advanced-atomic / discharged 投影没有沿事件引用提供位置。
2. 源码候选使用主 TU 文件替代实际头文件；AST 绝对路径与快照相对路径未对应。
3. 后端适配器把主源码副本重命名，AST 却仍指向原工作副本。通过 profile.path_map
   声明本地和远端根后，工具按唯一且含已验证主源码的本地根捕获快照，输出原始相对路径。
4. Clang 为宏参数返回起止相同的可信点，被错误丢弃。现按单字符范围高亮。

## 独立单测

全部测试在 Linux Docker 中运行，不依赖真实 SSH、数据库、消息队列或模型服务。

| 范围 | 结果 | 行覆盖率 | 分支覆盖率 |
|---|---|---|---|
| 后端 Java | 1721 项，0 失败，2 跳过；Maven verify 成功 | 96.75%（24216/25029） | 90.99%（9012/9904） |
| 后端 analysis 包 | 上述全量测试包含 | 96.61%（1112/1151） | 90.22%（498/552） |
| SpecializedAnalysisService | 上述全量测试包含 | 98.84%（170/172） | 96.15%（75/78） |
| 后端 Python 全部资源脚本 | 17 项通过 | 62.75%（411/655） | 57.31%（145/253） |
| 本次适配器 prepare_specialized_analysis.py | 包含正常、错误、边界的独立测试 | 94.52%（293/310） | 90.98%（111/122） |
| 后端 Java + Python 项目整体 | 合并自有代码计数，不排除历史低覆盖脚本 | 95.88%（24627/25684） | 90.15%（9157/10157） |
| 内存序工具 Python | 857 项通过，含未加载模块与 doc/experiments | 97.57%（14396/14754） | 94.13%（7238/7689） |
| 内存序工具 C++ | 118 项通过 | 99.28%（5363/5402） | 92.48%（4094/4427） |
| 内存序工具整体 | 全部模块质量门禁通过 | 98.03%（19759/20156） | 93.53%（11332/12116） |

工具受影响模块分别为：finding_locations 100%/100%，finding_projection 99.19%/92.31%，
source_context 94.55%/93.75%，unified_coordinator 97.49%/90.59%（行/分支）。

历史缺口透明记录：未修改的 `produce_bitcode.py` 为 34.20% 行、25.95% 分支；它已计入
后端整体，未排除或降低门槛。本次改动的适配器和 Java 模块均超过 90%。不能将此记录
表述为“后端每个历史文件都超过 90%”。工具的既有更严格逐模块、逐语言门禁仍完整通过。

统计排除：Java 仅既有自动生成 jOOQ；工具排除第三方、纯测试/实验输入、生成协议元数据
和经内容哈希校验的声明头文件。未排除项目业务实现，具体列表见工具 coverage-summary.json。

实际执行命令（仓库根运行 Docker，容器中切到对应目录）：

```sh
# rvport-backend-quality:local，工作目录 /workspace/backend
mvn -B -o verify

# memory-order-analyzer-dev:llvm21，工作目录 /workspace/tools/memory-order-analyzer
PYTHONPATH=python python3 -m memory_order_analyzer.quality --output reports/mo-source-context-final
PYTHONPATH=python python3 -m coverage run --branch --source=python/memory_order_analyzer,doc/experiments -m pytest -q tests/unit
python3 -m coverage json -o reports/mo-source-context-final/python.json

# 同一 Linux 工具镜像，以仓库挂载到 /workspace
PYTHONPATH=python python3 -m coverage run --branch --source=/workspace/backend/src/main/resources/analysis,/workspace/backend/src/main/resources/bitcode -m pytest -q /workspace/backend/src/test/python
python3 -m coverage json -o /workspace/backend/runtime/mo-source-context-validation/backend-python-coverage.json
```

完整工具入口已执行 C++ 和 Python 单测；最后一次单点修复后重新执行了全部 Python 单测，
使用同轮未修改 C++ 的单测报告重新 evaluate，`passed=true`。没有将集成覆盖混入单测。
复跑 quality 时须使用新的输出目录，不能混入旧的 profile。

报告位置：
- `backend/runtime/mo-source-context-validation/maven-verify.log`
- `backend/runtime/mo-source-context-validation/backend-python-coverage.json`
- `tools/memory-order-analyzer/reports/mo-source-context-final/coverage-summary.json`
- `tools/memory-order-analyzer/reports/mo-source-context-final/python.json`、`cpp.json`
- `tools/memory-order-analyzer/reports/source-context-final-unit.log`

Java XML 的上述计数在本轮 verify 后读取；随后其他线程构建清理了共享 target，故该 XML
路径不保证仍存在。本轮成功日志和此处已读取计数保留；后续全量构建可重新生成 XML。

## 真实编译器和 API

真实 Clang 集成用例 2 项通过：项目头文件/宏的 AST 绝对路径映射，带调试信息 BC
的真实事件引用映射。命令：

```sh
PYTHONPATH=python MOA_WORKER=/output/build/moa-worker python3 -m pytest -q tests/integration/test_finding_source_context.py
```

正式 API 使用独立项目 `5ca08ec7-39f6-413d-8b5d-26222cc89cd6`；不修改 demo-test1。
x86 经跳板 SSH 完成真实 gcc 构建，任务 `2611f0c1-e32d-4f68-83b4-109fea9d2644` 成功。
目标环境仅配置，没有执行 RISC-V 构建，也不声称目标连接通过。

本次远端 BC 状态为 FAILED / TRANSLATION_UNIT_FAILED，扫描按既有逻辑使用 AST_ONLY。
不把这次 API 运行描述成 AST+BC 成功；BC 位置解析由上述真实 Clang fixture 以及正式风险、
advanced-atomic 引用和 discharged 的独立投影测试验证。

最终扫描：
- runId：`940ecff4-10cc-42aa-b622-58430316af55`
- taskId：`7dd74eaa-bdf6-4c74-ace3-9b1a9f842946`
- 7 条源码候选，全部 7 条落库位置非空，覆盖 `main.c` 和 `shared.h`。
- 7 个详情全部有 codeContext；逐行文本与上传源码一致，高亮非空。
- 下载 JSON 与详情 detail 深比较完全一致；列表不展开源码。
- 同一映射下，从 5 条可显示修至 7 条可显示，没有改变 Finding 身份集合。

审计输入、结果、每条详情、原始审计包和复测脚本保留在
`backend/runtime/mo-source-context-validation/`。此前两次运行分别为 0/7、5/7 有位置，
用于证明复现和修复，不覆盖历史结果。正式风险的实际用户扫描样本仍未提供。

## 部署与契约

本次已验证 JAR 与工具 Python 代码以增量镜像更新 API 和 worker；原生 worker 未修改。
镜像 ID：`52e1f25ffdb64844e1d1908d6e0e7fe0a0aee1f9224698eb47efe0ddd11161f3`。
API healthy，worker 已启动。未把其他线程正在编辑的 Java/浮点文件重新编译入该镜像。

继续使用既有详情 API、权限校验、版本绑定、报告制品和归档登记。旧记录不回填。
backend change 与工具两个受影响 spec 均通过 strict 校验；Git diff --check 通过。
