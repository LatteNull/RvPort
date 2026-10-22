# Memory Order Analyzer development and validation

English | [简体中文](development.zh-CN.md)

## Development container

Run in Windows PowerShell from the repository root; the first command enters this tool's directory:

```powershell
Set-Location tools/memory-order-analyzer
$moaSource = (Get-Location).Path
docker build -f Dockerfile.dev -t memory-order-analyzer-dev:llvm21 .
docker run --rm --memory=8g --cpus=2 --network none --mount "type=bind,source=$moaSource,target=/workspace,readonly" --mount "type=volume,source=moa-dev-output,target=/output" memory-order-analyzer-dev:llvm21 sh -c 'cmake -S /workspace -B /output/build -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ && cmake --build /output/build --parallel 2'
docker run --rm --memory=8g --cpus=2 --network none --mount "type=bind,source=$moaSource,target=/workspace,readonly" --mount "type=volume,source=moa-dev-output,target=/output" memory-order-analyzer-dev:llvm21 python3 -m memory_order_analyzer doctor --worker /output/build/moa-worker
```

Building requires Ubuntu and apt.llvm.org access. Running/tests disable networking and require no SSH, DevKit, Docker socket, or privileges. The image defaults to UID/GID 10001 and separates read-only source from writable `/output`. Analyzed programs are not executed. New named volumes inherit `/output` permissions from the image; host bind-output directories must already be writable by UID 10001.

`Dockerfile.dev` is the standalone development entry point. The repository's `backend/Dockerfile` builds the production analyzer and integrates it with the backend; validate them separately. [config/toolchain.lock.json](../config/toolchain.lock.json) and [development-packages.lock](../development-packages.lock) pin base-image digest, exact LLVM release, all installed package versions, signing-key SHA256, official sources, and license locations. apt verifies signed indexes and package SHA256, then installed packages are compared individually with the lock. Removed upstream packages cause build failure rather than silent upgrades. Retain accepted image IDs for byte-identical environments. Full package versions and licenses are in `/opt/development-packages.tsv` and `/usr/share/doc/<package>/copyright` inside the image.

## Current runtime boundaries

The production entry reads upstream raw BC without running compilers, dependency generators, linkers, build scripts, network access, or SSH. An optional source worker adds AST evidence using constrained arguments and the pinned toolchain.

`compile_commands.json` is not a complete scope. Upstream bundle plans, source digests, physical TUs, and explicit scopes define denominators. Failed entries cannot disappear. See [degraded analysis](DEGRADED_SOURCE_ANALYSIS.md) for language/platform and fallback limits.

## Complete quality gate

After entering the tool directory and setting `$moaSource` above, run:

```powershell
docker run --rm --memory=8g --cpus=2 --network none --mount "type=bind,source=$moaSource,target=/workspace,readonly" --mount "type=volume,source=moa-dev-output,target=/output" memory-order-analyzer-dev:llvm21 python3 -m memory_order_analyzer.quality --output /output/quality-001 --integration
```

Use a fresh output directory each time. The quality entry builds C++, runs GoogleTest and Python unit tests, then generates llvm-cov/coverage.py reports. Integration profiles remain separate from unit profiles. Include all project-owned Python/C++ source, including unloaded modules. Overall, per-language, and affected-module line/branch coverage must each reach 90%. Exclude third-party code, test frameworks, input-only fixtures, and headers without executable definitions. Unsupported branch metrics are null.

Outputs include `python.json`, `cpp.json`, `coverage-summary.json`, and HTML reports. Run documentation contracts with `python3 -m pytest tests/integration/test_documentation.py`. These prove agreement between documents and offline evidence only, not unit coverage or real-worker correctness.

Historical scenario mappings and accepted records consumed by documentation tests are in `tests/fixtures/documentation/`; they are not new run results.
