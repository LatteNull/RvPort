## 1. 环境采集增强

- [x] 1.1 盘点当前 `SshRuntimeService.collectCommand`、`parseCollect` 和 `createCollectedComponents` 的 ELF/so 采集路径
- [x] 1.2 在采集脚本中增加 `readelf -d/-h` 解析 SONAME、NEEDED、machine 和 class
- [x] 1.3 增加 `objdump -p` fallback，并在两个工具都不可用时写入 parse warning
- [x] 1.4 在源 x86 与目标 RISC-V 的 library/native metadata 中写入 `elfSoname`、`elfNeeded`、`elfMachine`、`elfClass`、`elfScanner`
- [x] 1.5 基于 SONAME、文件名和 owner package 生成 `providesCapabilities` 与 `requiredCapabilities`

## 2. Repository provides 查询增强

- [x] 2.1 调整目标 RISC-V repository provides 查询，优先使用 exact SONAME/capability
- [x] 2.2 保留路径、文件名和 normalized library fallback 查询，并标记 fallback 类型
- [x] 2.3 在 `REPOSITORY_PROVIDE` metadata 中写入 `provideKind`、`queryValue`、`packageName`、`scanner`、`queryPattern`
- [x] 2.4 确保 repository provides 查询失败时记录 warning，不阻断基础快照

## 3. SBOM analyzer 匹配

- [x] 3.1 在 analyzer index/lookup 中增加 ELF SONAME 和 capability keys
- [x] 3.2 调整匹配优先级：exact ELF capability > owner package > repository provides > arch-normalized capability > normalized library > weak name
- [x] 3.3 避免 `libfoo.so.1` 与 `libfoo.so.2` 被标记为 exact match
- [x] 3.4 在 candidate metadata 中输出 source/candidate SONAME、ELF machine/class、provideKind、queryValue、confidence 和 fallback 标记
- [x] 3.5 在 ELF evidence 缺失时保留现有 fallback 行为并输出 warning 或 evidence incomplete metadata

## 4. 测试覆盖

- [x] 4.1 补齐 `SshRuntimeServiceTests` 覆盖 readelf 正常解析、objdump fallback 和工具缺失 warning
- [x] 4.2 补齐 analyzer 测试：exact SONAME installed match、exact repository provides match、SONAME version mismatch、normalized fallback
- [x] 4.3 补齐 SBOM runtime 或 E2E fixture，确认 ELF evidence 进入 replacement candidate metadata
- [x] 4.4 确认测试覆盖正常流程、异常流程和 edge case

## 5. 真实验证和文档

- [x] 5.1 使用现有 SBOM validation 记录入口验证 x86/RISC-V 采集记录包含 ELF metadata 或明确 skipped/warning
- [x] 5.2 更新 E2E 或 SBOM 文档，说明 ELF capability matching 的证据优先级和降级规则
- [x] 5.3 运行 `mvn -q test`
- [x] 5.4 运行 `python -m unittest discover -s tests` 于 `tools/sbom-analyzer`
- [x] 5.5 运行 `node --check` 覆盖相关 E2E 脚本
- [x] 5.6 运行 `openspec validate --all`

## 6. package 与 library/native 关联修正

- [x] 6.1 盘点 `tools/sbom-analyzer` 当前 source component 处理顺序，确认 package/library/native candidate 生成路径
- [x] 6.2 在 analyzer 中增加 package-first pass，先生成 package/tool replacement result 并建立 package result index
- [x] 6.3 在 library/native pass 中读取 `ownerPackage`、`normalizedPackage`，当 owner package 已可迁移时标记 `coveredByPackage`
- [x] 6.4 对 package-covered library/native 输出 coverage metadata：`coveredByPackage`、`coveredByPackageName`、`coveredByPackageCandidate`、`coveredByPackageStatus`、`coveredByPackageMatchType`
- [x] 6.5 调整 component result 展示或查询逻辑，确保 covered library/native 不再默认作为独立缺口干扰 package 级结果
- [x] 6.6 移除 source library/native 使用 `elfNeeded`、`requiredCapabilities` 生成 replacement lookup key 的行为，仅保留为 evidence
- [x] 6.7 补充 analyzer 单元测试：package-covered library、owner package 不可迁移时进入 library matching、`elfNeeded` 不生成替代候选
- [x] 6.8 补充 Java SBOM runtime/E2E fixture，确认 coverage metadata 入库并可通过 API 审计
- [x] 6.9 使用真实 x86/RISC-V 环境重新跑全流程，确认 package/library 数量和 covered 结果符合预期
- [x] 6.10 运行 `python -m unittest discover -s tests`、相关 Maven 测试、E2E/真实验证脚本和 `openspec validate --all`

## 7. 真实全量结果缺口修正

- [x] 7.1 更新 proposal/design，记录 package/repository/library/provider 全量采集和 TOOL owner evidence 的设计决策
- [x] 7.2 移除环境采集脚本中的固定 `head` 截断，避免 package、repository package、library/native、provider 被裁掉
- [x] 7.3 移除 Java 解析层 `packages`、`pipeRecords` 的固定 limit，确保全量输出能全量入库
- [x] 7.4 增加 `TOOL_PROVIDER` 采集和解析，将 `java`/`javac` 等工具映射到 owner package/version
- [x] 7.5 在 analyzer candidate metadata 中输出 `sourceOwnerVersion`、`sourceOwnerArch`，便于审计 x86 源侧包版本
- [x] 7.6 补充 analyzer/Java 测试覆盖工具 owner package 匹配、owner version evidence 和全量解析
- [x] 7.7 修正采集策略：源环境不执行无效 repository provides 查询，目标 RISC-V 保留全量 repository evidence
- [x] 7.8 移除逐库 `repoquery --whatprovides` 调用，避免全量采集在真实仓库上长时间卡住
- [x] 7.9 重新运行真实 x86/RISC-V 全流程，确认 `java`、`libdnf.so.2`、`libfuse.so.2.9.9` 映射结果正确

## 8. 元数据与架构专用包误报修正

- [x] 8.1 将 `gpg-pubkey` 识别为 RPM 元数据记录，输出 `METADATA_ONLY` 且风险为 `LOW`
- [x] 8.2 对包名中的 x86 架构 token 增加 RISC-V 目标包名候选，例如 `grub2-efi-x64-modules` -> `grub2-efi-riscv64-modules`
- [x] 8.3 将 `grub2-pc` / `grub2-pc-*` 标记为 `NOT_APPLICABLE_ARCH`，避免误报为源码构建缺口
- [x] 8.4 补充 analyzer 单元测试覆盖 `gpg-pubkey`、`grub2-efi-*` 架构变体和 `grub2-pc*` 架构不适用
- [x] 8.5 更新静态 HTML 报告状态样式，避免 `METADATA_ONLY` / `NOT_APPLICABLE_ARCH` 被显示为高风险红色
