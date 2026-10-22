## 1. 动态库解析事实采集

- [x] 1.1 扩展 `BUILD_VALIDATION` wrapper，对 ELF `NEEDED` 库名执行安全 resolver，输出 `resolvedNeededLibrary` 结构化观测。
- [x] 1.2 为 resolver 增加 owner package/version 查询，优先支持 rpm/dpkg，并记录 resolver 来源和 warning。
- [x] 1.3 确保 resolver 失败、多候选或工具缺失时只降级记录 evidence，不影响构建任务成功状态。

## 2. 依赖分析 source owner 补全

- [x] 2.1 在 `DependencyFactExtractor` 中解析 `resolvedNeededLibrary` 观测，建立 SONAME/引用 ELF 到 source owner package 的索引。
- [x] 2.2 调整 ELF `NEEDED` / `SONAME` provider 匹配优先级，优先使用 resolved source owner，再降级到现有 source owner 和版本证据。
- [x] 2.3 在结果 evidence 中返回 source library path、source owner、resolver、解析失败 warning 和候选摘要。

## 3. 目标 provider fallback

- [x] 3.1 在目标匹配逻辑中增加 `source-owner-package-fallback`，当 SO/provides 未命中但 source owner package 已确认时匹配目标同名 installed/repository package。
- [x] 3.2 fallback 命中后复用现有 major version 比较和风险等级映射。
- [x] 3.3 明确禁止跨发行版 alias 推断，确保 `glibc` 不会自动等价为 `libc6`。

## 4. 测试与验证

- [x] 4.1 补充单元测试：`libc.so.6` resolved owner 后生成 source provider package/version。
- [x] 4.2 补充单元测试：目标 SO/provides 缺失但同名 package 存在时使用 fallback，并标记 `matchedBy=source-owner-package-fallback`。
- [x] 4.3 补充 edge case 测试：resolver 失败、多候选、target package 版本缺失、跨发行版 alias 不匹配。
- [x] 4.4 运行 Maven 测试。
- [x] 4.5 使用真实 x86/target 环境重新跑依赖分析，确认 `libc.so.6`、`ld-linux*.so*` 等基础动态库有明确 source/target provider 证据。

验证记录：

- `mvn -Dtest=DependencyFactExtractorTests test` 通过：26 个测试，0 失败，0 跳过。
- `mvn test` 通过：472 个测试，0 失败，2 个按设计跳过。
- `node e2e/runner.js run --case=015-dependency-analysis` 已尝试，因当前 shell 未配置 `RVPORT_E2E_X86_*` / `RVPORT_E2E_RISCV_*` 真实 SSH 环境而失败，runner 已清理测试数据。
- `node runtime/run-real-build-system-repos.js` 已尝试，Git 同步成功，source x86 部署成功，但 target 环境部署失败，错误为 `TASK_CREDENTIAL_INVALID`，因此依赖分析阶段被脚本跳过；记录目录：`runtime/real-build-system-results/real_build_systems_20260827015444`。
- 使用 `test` 项目运行真实验证：project `3ee36413-4e4f-40c3-b6ad-cad14f54d99d`，source env `fbed0ac7-3467-4a64-9bf3-58b29e88207f`，target env `efa8ee01-5f3c-4b2e-ba1a-7d36489fb8a3`。
- `node runtime/run-real-build-system-repos.js` 真实验证通过 make/cmake/ninja 三个项目，Git、双环境源码部署、source-only 构建和依赖分析均成功；rpmbuild case 构建失败后跳过依赖分析。记录目录：`runtime/real-build-system-results/real_build_systems_20260827023405`。
- 抽查 `make-zlib` 结果：构建日志包含 `RVPORT_OBSERVATION resolvedNeededLibrary ... soname=libc.so.6 ... path=/lib64/libc.so.6 ... ownerPackage=glibc-2.38-84.oe2403sp3.x86_64 ... resolver=ldconfig`；依赖结果包含 `RUNTIME_LIBRARY glibc`，source provider `glibc 2.38-84.oe2403sp3`，target provider `glibc 2.38-34.oe2409`，状态 `SAME_MAJOR`，风险 `INFO`。
