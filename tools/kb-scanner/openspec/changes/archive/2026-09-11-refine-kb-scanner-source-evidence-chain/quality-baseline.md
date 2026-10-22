# 实施前覆盖率基线与历史暂停记录（2026-09-11）

> 此处以下保留首次暂停时的审计原文，不代表当前状态。用户随后以 `/opsx:apply refine-kb-scanner-source-evidence-chain 可以补齐` 授权必要的 scanner 历史单测补齐，实施已经完成，2026-09-11 经用户授权同步并归档。

## 当前状态

change: refine-kb-scanner-source-evidence-chain。apply 已开始，30 项实施任务仍全部未完成；本次仅完成质量基线审计和门槛文档更新，尚未改动 scanner 业务代码。任务 1.1 的完整报告/性能基线尚未冻结，1.3 的正式自动化门禁尚未接入，因此不能勾选完成或提示归档。

用户最新要求是项目整体及受影响模块行/分支均至少 90%，此前 proposal 的 80% branch 已同步改为 90%。发现历史覆盖缺口跨越本 change 之外的旧兼容层与维护脚本；按用户要求先报告并请求范围授权，不擅自补改无关模块，也不删除/排除旧业务实现规避指标。

## 实际执行

- 基线 HEAD：7ac4273（feat: 补齐知识库扫描器的 RPM 架构规则与证据链）。
- 独立镜像：rvport-kb-scanner-test:local，image ID sha256:6239c14ed91b006edb5e6298348deb19cd60f87aa9b3bb85043db35767e5e05a。
- 镜像不重建；源目录只读、无网络、无特权，仅诊断输出目录可写；没有本机依赖安装或生产服务更新。
- 复用现有隔离门禁选择方式，运行 tests/unit 中去重后的隔离测试，并加入 tests.test_core_pipeline 的 fake stage 单元测试。已确认混有真实 parser/完整 pipeline 的 9 个唯一测试方法未计为单测，逐条列表位于 summary.json。
- 最终 **404 项测试通过，0 failure / 0 error**，unittest 运行 9.370 秒（不含容器启动及报告生成）。
- 这是本次已执行隔离测试集合的源码覆盖基线，不是把全部 root test_*.py 的集成/端到端结果当单元覆盖。正式项目门禁仍须审计其余测试分层；当前审计入口仅为临时诊断，不算已交付自动化门禁。

## 统计范围及结果

Coverage branch=true、config_file=false、report:exclude_lines=[]，没有源码 omit；显式按目录计入未被测试加载的 Python 文件，包含 __init__.py、旧兼容代码及维护脚本，不依赖 inventory 缩小范围。

| 统计范围 | 文件数 | 行覆盖率 | 分支覆盖率 |
| --- | ---: | ---: | ---: |
| kb_scanner + scripts + tools 全部 Python 自有实现 | 125 | 82.14% | 76.44% |
| 仅 kb_scanner 包（诊断分项，不作为缩小门禁范围） | — | 84.46% | 77.87% |

总体 9,204 个可执行行中 1,644 未覆盖；3,392 个分支中 799 未覆盖。35 个文件至少有一项低于 90%，不代表要求所有无关模块本轮均逐一改造；但整体仍未达标，不能仅补本次变更行后声称项目整体达标。

未计入生产源码分母的内容：第三方依赖；JSON/YAML 知识数据及 fixture（非 Python 实现）；tests 下测试/测试辅助代码；archive 下历史封存且不部署的快照。未因此排除 kb_scanner 中仍保留的 legacy 实现。这里的“项目”限 tools/kb-scanner，不将 frontend/backend 或其他工具目录强行并入当前 change。

代表性缺口：

| 模块 | 行 | 分支 | 性质 |
| --- | ---: | ---: | --- |
| kb_scanner/rules.py | 0% | 0% | 旧 YAML evaluator，未被本次隔离套件执行；有旧高层扫描测试，不等于隔离单测 |
| kb_scanner/cpp_frontend.py | 0% | 0% | 旧 frontend，不在本次链路改造计划 |
| kb_scanner/adapters/legacy.py | 0% | 0% | 旧兼容 adapter |
| scripts/refresh_knowledge_sources.py | 0% | 0% | 维护脚本 |
| kb_scanner/frontends/cpp/clang_adapter.py | 86.41% | 76.14% | 当前解析模块，需核对既有隔离边界及补测 |
| kb_scanner/frontends/build/make.py | 94.44% | 85.71% | 本次计划影响模块 |
| kb_scanner/analyzers/build_selection.py | 94.14% | 84.78% | 本次计划影响模块 |
| kb_scanner/analyzers/evidence_graph.py | 95.77% | 88.29% | 本次计划影响模块 |
| kb_scanner/projection/v2/validation.py | 90.91% | 86.76% | 本次计划影响模块 |

没有据此声称整个 scanner 有运行错误；这是新的整体单测覆盖要求与历史分层门禁之间的差距。不能使用集成测试的已通过计数补齐上述覆盖率。

## 可重复命令与报告

从 D:/projects/RvPort 终端执行（诊断脚本和 results 目录已存在）：

```powershell
docker run --rm --network none --read-only --tmpfs /tmp:size=512m,mode=1777 --cap-drop ALL --security-opt no-new-privileges:true --mount "type=bind,source=D:/projects/RvPort/tools/kb-scanner,target=/workspace/tools/kb-scanner,readonly" --mount "type=bind,source=D:/projects/RvPort/.codex-tmp/source-chain-baseline-20260911/audit_coverage.py,target=/audit_coverage.py,readonly" --mount "type=bind,source=D:/projects/RvPort/.codex-tmp/source-chain-baseline-20260911/results,target=/out" --workdir /workspace/tools/kb-scanner --env PYTHONDONTWRITEBYTECODE=1 --env PYTHONPATH=/workspace/tools/kb-scanner rvport-kb-scanner-test:local /audit_coverage.py
```

诊断脚本退出码仅表示测试成功与否，**不代表 90% 质量门禁通过**。该脚本是临时审计，不计入已完成实施交付；正式自动化阈值仍在任务 1.3 待实现。

以上为本地未跟踪的审计产物，仓库外消费者不应假定这些相对链接可用。本记录保留了范围、命令与结果，正式交付需按任务固化可重复门禁。

两份 compiler JSON 哈希核对未变：
- clang: adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7
- gcc: 89775341ee880b13ac4f10a30558ff5d52875b25a3233114a5765601f0a9dad9

## 需要用户决定

是否将“KB Scanner 历史隔离单测与整体覆盖率补齐”纳入本 change，允许在 tools/kb-scanner 内补齐本次功能之外的必要测试/可测试性边界；或者先单独规划质量 change，再继续源码链改造。不得自动降低 90% 门槛，也不得自行排除仍在生产包中的旧代码。其他任务目录继续保持不动。

得到范围决定后，继续当前 change 的聊天命令是：

```text
/opsx:apply refine-kb-scanner-source-evidence-chain
```

OpenSpec 终端操作工作目录必须为 D:/projects/RvPort/tools/kb-scanner。当前不能 sync/archive 或标记 apply 完成。
