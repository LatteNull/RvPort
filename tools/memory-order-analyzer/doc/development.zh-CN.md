# 内存序分析器开发与验证

[English](development.md) | 简体中文

## 开发容器

在仓库根目录的 Windows PowerShell 中执行；首条命令进入本工具目录：

```powershell
Set-Location tools/memory-order-analyzer
$moaSource = (Get-Location).Path
docker build -f Dockerfile.dev -t memory-order-analyzer-dev:llvm21 .
docker run --rm --memory=8g --cpus=2 --network none --mount "type=bind,source=$moaSource,target=/workspace,readonly" --mount "type=volume,source=moa-dev-output,target=/output" memory-order-analyzer-dev:llvm21 sh -c 'cmake -S /workspace -B /output/build -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ && cmake --build /output/build --parallel 2'
docker run --rm --memory=8g --cpus=2 --network none --mount "type=bind,source=$moaSource,target=/workspace,readonly" --mount "type=volume,source=moa-dev-output,target=/output" memory-order-analyzer-dev:llvm21 python3 -m memory_order_analyzer doctor --worker /output/build/moa-worker
```

构建阶段需要访问 Ubuntu 与 apt.llvm.org；运行和测试阶段禁用网络，无 SSH、DevKit、Docker socket 或特权要求。镜像默认 UID/GID 10001，只读源码挂载与独立可写 `/output` 分离。不运行被分析程序。首次命名卷从镜像 `/output` 初始化权限；若使用宿主 bind 输出目录，应先保证 UID 10001 可写。

`Dockerfile.dev` 是本工具独立开发入口；根目录 `backend/Dockerfile` 已包含生产分析器构建与后端集成，两者分别验证。锁定文件为 [config/toolchain.lock.json](../config/toolchain.lock.json) 与 [development-packages.lock](../development-packages.lock)：基础镜像 digest、LLVM 精确发行、全部安装包版本、签名密钥 SHA256、官方来源及许可证入口。apt 验证签名索引及包 SHA256；最终安装集合逐项比较锁文件。仓库若撤下已锁包，构建失败而非悄悄升级；要保存字节一致环境，保留验收镜像 ID。完整包版本及许可证分别位于镜像 `/opt/development-packages.tsv`、`/usr/share/doc/<package>/copyright`。

## 当前运行边界

生产入口只读上游生成的 raw BC，不执行 compiler、dependency generator、linker、构建脚本、网络或 SSH。可选 source worker 在受限参数和锁定工具链下补充 AST 证据。

`compile_commands.json` 不是完整 scope；上游 bundle 的计划记录、source digest、physical TU 和显式 scope 才能定义输入分母。失败项不得消失。语言/平台和降级限制见 [降级分析](DEGRADED_SOURCE_ANALYSIS.zh-CN.md)。

## 完整质量门槛

在上文已经进入工具目录并设置 `$moaSource` 后执行：

```powershell
docker run --rm --memory=8g --cpus=2 --network none --mount "type=bind,source=$moaSource,target=/workspace,readonly" --mount "type=volume,source=moa-dev-output,target=/output" memory-order-analyzer-dev:llvm21 python3 -m memory_order_analyzer.quality --output /output/quality-001 --integration
```

每次使用新的输出目录。质量入口构建 C++、执行 GoogleTest 和 Python 单元测试，再生成 llvm-cov/coverage.py 报告；集成检查与单元 profile 分离。所有自有 Python/C++ 源码，包括未加载模块，均计入统计；整体、每种语言及受影响模块行/分支至少 90%。第三方、测试框架、纯输入夹具和无执行定义的头文件不计入；无分支指标用 null 表示。

输出含 `python.json`、`cpp.json`、`coverage-summary.json` 及对应 HTML。文档契约检查为 `python3 -m pytest tests/integration/test_documentation.py`，只证明文档与离线证据一致，不能代替单元覆盖或真实 worker 验证。

历史场景映射及被文档测试消费的接受记录集中于 `tests/fixtures/documentation/`，不作为新运行结果。
