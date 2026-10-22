# 验证记录

## 验证范围

- 后端 BC capability resolver、创建校验、可选制品物化、运行时二次校验降级、readiness、响应投影和语言上下文摘要。
- 远端 BC producer 与专项分析 adapter 的旧标准、GNU/ISO 方言、compiler default、unsupported TU 和 AST-only/混合输入。
- 浮点精度扫描器的语言标准归一化、请求协议和固定 Clang 集成语料。
- memory-order-analyzer 的语言标准 value object、source profile、external bitcode、AST-only/AST+IR 规则适用性及 Python/C++ 完整单元门禁。

## 已通过验证

### OpenSpec 与 schema

```powershell
openspec validate "allow-ast-only-analysis-and-legacy-language-standards" --type change --strict --json
```

结果：1 个 change 通过严格校验，0 个 issue。

```powershell
docker run --rm --entrypoint python3 -v "D:/projects/RvPort:/workspace" -w /workspace rvport-backend-local:latest -c "import json,pathlib; files=list(pathlib.Path('backend/src/main/resources').rglob('*.json'))+list(pathlib.Path('tools/floating-point-precision-scanner').rglob('*.schema.json'))+list(pathlib.Path('tools/memory-order-analyzer/schemas').glob('*.json'))+[pathlib.Path('tools/memory-order-analyzer/protocols/source-evidence-protocol.json'),pathlib.Path('tools/memory-order-analyzer/protocols/external-bitcode-ingestion-protocol.json'),pathlib.Path('tools/memory-order-analyzer/protocols/unified-project-analysis-protocol.json')]; [json.loads(p.read_text(encoding='utf-8')) for p in files]; print(f'validated {len(files)} JSON files')"
```

结果：42 个 JSON/schema/协议文件均可解析。

### 后端 Python 协议测试

```powershell
docker run --rm --entrypoint /opt/specialized-analysis-venv/bin/python -v "D:/projects/RvPort/backend:/workspace/backend" -v "D:/projects/RvPort/tools/memory-order-analyzer:/workspace/tools/memory-order-analyzer" -w /workspace/backend -e PYTHONPATH=/workspace/tools/memory-order-analyzer/python rvport-backend-local:latest -m unittest src/test/python/test_produce_bitcode.py src/test/python/test_prepare_specialized_analysis.py
```

结果：14 条测试全部通过。新增固定流程使用 C89、C99、C++98、C++03 四个 TU 分别生成 COMPLETE、PARTIAL、MISSING 三类共享 BC 输入，确认四个 TU 始终保留在 AST 分母，source request 均为 v2，真实标准未被升级；external record 的 produced 数分别为 4、2、0。

### 后端 Java 与全量覆盖率门禁

```powershell
docker run --rm --name rvport-backend-full-quality-final --entrypoint sh `
  -e "PATH=/opt/kb-scanner-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" `
  -v "D:/projects/RvPort:/workspace" `
  -v "rvport-maven-cache:/root/.m2" `
  -w /workspace/backend rvport-backend-quality:local `
  -lc "mvn -o -B verify"
```

结果：1701 条测试全部通过，0 失败、0 错误、2 条既有跳过；`mvn verify` 与 JaCoCo check 均成功。

- 后端整体：行 24160/24969，96.76%；分支 8976/9864，91.00%。
- `analysis` 受影响包：行 1054/1091，96.61%；分支 461/512，90.04%。
- `buildvalidation` 受影响包：行 1081/1114，97.04%；分支 442/489，90.39%。
- `workflow` 受影响包：行 239/239，100%；分支 94/104，90.38%。
- 报告：`backend/target/site/jacoco/index.html`、`backend/target/site/jacoco/jacoco.xml`。
- 统计范围：全部编译后的后端项目自有生产类，未加载类按 0 命中计入；仅排除 `src/generated/java/cn/rvport/backend/jooq/**` 的可重复生成 jOOQ 元数据。测试源码、fixture 和第三方依赖不属于生产源码统计范围。

初次失败来自不含生产 Python/工具运行时的临时 Maven 镜像，以及 Linux 容器中使用 Windows 路径字面量的测试 fixture。最终验证改用正式后端运行时派生的质量镜像，外部 service connection 继续由 mock 返回值替代；路径用例改为 Linux 绝对路径与 `../` 越界路径，没有为 Windows 增加生产兼容逻辑。覆盖率补测覆盖了 BC 制品缺失/残缺/零可用、legacy DTO 投影、readiness BC 模式、禁用环境、Git 空 commit 和工具不可执行等正常、边界与异常路径。

### 浮点精度扫描器单元与合同覆盖率

```powershell
docker run --rm -v "D:/projects/RvPort/tools/floating-point-precision-scanner:/workspace" -w /workspace rvport-fp-scanner-dev:latest bash -lc "rm -f .coverage && PYTHONPATH=src python3 -m coverage run --branch --source=src/floating_point_precision_scanner -m pytest -q tests/unit tests/contract && mkdir -p artifacts/coverage && python3 -m coverage json -o artifacts/coverage/coverage.json && python3 -m coverage report --show-missing"
```

结果：237 条测试全部通过；行覆盖率 3346/3447（95.99%），分支覆盖率 1080/1164（92.78%），coverage.py 综合显示为 96%。报告：`tools/floating-point-precision-scanner/artifacts/coverage/coverage.json`。统计范围为 `src/floating_point_precision_scanner` 全部生产模块，未加载模块按 0 命中计入；测试、fixture 和第三方依赖不进入分母。

### memory-order-analyzer 完整单元门禁

```powershell
docker run --rm -v "D:/projects/RvPort/tools/memory-order-analyzer:/workspace" -w /workspace memory-order-analyzer-dev:llvm21 bash -lc "PYTHONPATH=python python3 -m memory_order_analyzer.quality --output /workspace/reports/allow-ast-only-analysis/final-quality-v6"
```

结果：最终门禁 Python 850 条、C++ 118 条测试全部通过。新增覆盖包括 AST-only 空 bitcode 缓存键、物理 TU 稳定排序、source/IR reference 独立排序，以及 C89、C99、C++98/C++03 降级候选校验。

- 整体：行 19624/20022，98.01%；分支 11245/12028，93.49%。
- Python：行 14261/14620，97.54%；分支 7151/7601，94.08%。
- C++：行 5363/5402，99.28%；分支 4094/4427，92.48%。
- 报告：`tools/memory-order-analyzer/reports/allow-ast-only-analysis/final-quality-v6/`。
- 统计范围：全部项目自有生产实现；未被测试加载的生产源码按 0 命中计入分母。排除范围仅包括测试代码与 fixture、第三方 LLVM/GoogleTest/Python 依赖、生成协议头和经 hash 固定的纯声明头；测试代码本身不进入覆盖率分母，未排除项目自有业务实现。

### 浮点固定集成语料

新增的旧标准与 compiler-default 锁定 Clang 用例已单独通过：

```powershell
docker run --rm -v "D:/projects/RvPort/tools/floating-point-precision-scanner:/repo" -w /repo rvport-fp-scanner:validate bash -lc "PYTHONPATH=src:. pytest -q tests/integration/test_clang21.py::test_locked_clang_replays_legacy_and_default_standards"
```

结果：6 条旧标准/default 参数化用例全部通过。

```powershell
docker run --rm -v "D:/projects/RvPort/tools/floating-point-precision-scanner:/repo" -w /repo rvport-fp-scanner:validate bash -lc "PYTHONPATH=src:. FP_SCANNER_IR_WORKER=/workspace/build/fp-ir-worker pytest -q tests/integration"
```

结果：21 条集成测试全部通过。失败根因是 Clang 21 对主源码顶层声明省略 `file` 字段、仅保留 `offset/line/col`，旧映射逻辑把 comparison、reduction、libm 和 FMA 的项目事实错误过滤。修复后，仅对直接位于 `TranslationUnitDecl`、坐标完整且没有 `includedFrom` 的节点继承主源码归属；显式外部路径与头文件仍被排除。对应正常与外部头文件边界单元测试、工具设计文档和 `compilation-context-ingestion` 规格已同步。

### memory-order-analyzer 协议版本边界

语言上下文扩展已经按 kind 建立明确版本边界：`CompilationProfileIdentity`、`SourceSemanticRequest`、`ExternalBitcodeArtifactRecord` 和引用新版 source request 的 `UnifiedMemoryOrderAnalysisRequest` 使用 v2；未改变语义的 kind 继续保持 v1。读取器兼容合法历史 v1，拒绝 v1 携带 v2 字段、v2 缺失上下文、嵌套版本不一致及未知未来版本。

```powershell
docker run --rm -v "D:/projects/RvPort/tools/memory-order-analyzer:/workspace" -w /workspace memory-order-analyzer-dev:llvm21 bash -lc "PYTHONPATH=python pytest -q tests/unit/test_language_standards.py tests/unit/test_source_evidence.py tests/unit/test_external_bitcode_contracts.py tests/unit/test_external_bitcode_ingestion.py tests/unit/test_unified_contracts.py tests/unit/test_unified_adapters.py tests/unit/test_unified_plan.py tests/unit/test_unified_coordinator.py"
```

结果：132 条协议与语言标准边界测试全部通过，覆盖 v1 历史读取、v2 新生产文档、旧标准、compiler-default、未来版本拒绝和嵌套版本不一致。

### 真实 API E2E

使用最终后端镜像、真实 x86 跳板机环境和本地 RISC-V SSH 环境执行：

```powershell
$env:RVPORT_E2E_JUMP_HOST='jump.example.invalid'
$env:RVPORT_E2E_JUMP_PORT='5022'
$env:RVPORT_E2E_JUMP_USERNAME='example-user'
$env:RVPORT_E2E_JUMP_PRIVATE_KEY_FILE='C:\Users\developer\.ssh\example_key'
$env:RVPORT_E2E_X86_HOST='192.0.2.10'
$env:RVPORT_E2E_X86_PORT='22'
$env:RVPORT_E2E_X86_USERNAME='root'
$env:RVPORT_E2E_X86_PRIVATE_KEY_FILE='C:\Users\developer\.ssh\example_key'
$env:RVPORT_E2E_RISCV_HOST='host.docker.internal'
$env:RVPORT_E2E_RISCV_PORT='4004'
$env:RVPORT_E2E_RISCV_USERNAME='root'
$env:RVPORT_E2E_RISCV_PASSWORD='<local-test-password>'
$env:RVPORT_E2E_SPECIALIZED_BUILD_TIMEOUT_MS='1800000'
$env:RVPORT_E2E_SPECIALIZED_ANALYSIS_TIMEOUT_MS='1800000'
node e2e/runner.js run --module=specialized-analysis
```

最终运行 ID：`e2e_20261008_134419_0c72cbe6`。`021-specialized-analysis` 全部通过并自动清理：

- x86 与 RISC-V 连接测试均成功；
- COMPLETE：构建返回 `AST_BC_COMPLETE/READY`，2/2 BC 可用；浮点与内存序分析均成功；
- MIXED：构建返回 `AST_BC_MIXED/PARTIAL`，1/2 BC 可用；两个分析器均成功且保留 1 个 AST-only TU；
- AST_ONLY：构建返回 `AST_ONLY/FAILED`，0/2 BC 可用；两个分析器仍成功执行源码分析；
- 每条流程均校验创建、任务终态、详情、latest、列表、Finding 列表/详情、JSON/HTML 制品下载；内存序额外校验 audit 制品；
- 数据库中的 compile database、manifest、bundle、迁移输入和归档候选数量与 API 结果一致；RabbitMQ ready 消息为 0，清理完成。

E2E 调试过程中发现并修复了 AST-only 空 bitcode 缓存键、源码请求物理 TU 顺序、source/IR reference 独立排序，以及旧标准降级候选仍受 C11/C17 白名单限制的问题。最终通过结果来自重建后的正式 `rvport-backend-1` 与 `rvport-backend-worker-1`，不是容器内临时补丁。
