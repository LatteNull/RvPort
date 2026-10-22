## 1. 冻结兼容基线与清理边界

- [x] 1.1 记录 schema 1.0 七个顶层字段、Finding 必需/兼容字段、summary 计数、退出码及 json/html/log artifact 行为的版本化 baseline。
- [x] 1.2 固化 `clang-x86-entries.json`、`gcc-x86-entries.json` 的原始 bytes、六类计数、source 和 SHA-256，并记录现有 YAML/`generatedSet` 文件清单，禁止本 change 自动改写。
- [x] 1.3 建立高价值 differential fixture matrix，覆盖 generated/curated facts、AVX/x86-only、guarded/inactive、portable/RISC-V alternative、build/test selection、零命中、unknown/冲突和恶意静态输入。
- [x] 1.4 定义版本化 parity/approved-correction/deferred-blocking ledger schema，并以拒绝未知字段、重复条目、无 Evidence/proof 批准和自动重写的测试固定边界。
- [x] 1.5 建立 Legacy/spike cleanup inventory，逐文件记录生产/测试引用、正式替代、对应 fixture、当前处置和删除条件。
- [x] 1.6 创建 `compatible-cutover-test-inventory.json`，列出本 change 每个新增/修改业务模块的隔离 unit suite、fake/mock 边界、高层测试和 90% line / 80% branch 门禁。

## 2. 新规则包描述与 CLI 输入适配

- [x] 2.1 实现无执行语义的 scanner bundle descriptor schema/loader，严格校验兼容 rulePack identity、knowledge manifest 相对路径/摘要和 projection policy identity。
- [x] 2.2 为 bundle descriptor loader 补齐隔离单元测试，fake 文件读取并覆盖路径逃逸、摘要错误、schema 错误、未知字段、排序与稳定 identity，达到逐模块覆盖门槛。
- [x] 2.3 在 RISC-V porting bundle 中提交 `scanner-manifest.json`，引用现有 `knowledge-manifest.json` 且保持 Legacy manifest/YAML、`generatedSet` 和两份 compiler facts 原样不变。
- [x] 2.4 实现不导入 Legacy 的 CLI namespace-to-ScanRequest adapter 和 ScanContext factory，保持现有参数、规范化、compile context、scan mode、rulePack/knowledge identity 与 Diagnostic 语义。
- [x] 2.5 为 CLI adapter/context factory 补齐隔离单元测试，fake bundle/compile-context 边界并覆盖非法路径、语言、format、目标架构、partial/failed status 和确定性，达到逐模块覆盖门槛。
- [x] 2.6 将 `validate-rules` 和 `list-rules` 的内部数据源改为正式 bundle、knowledge、detector 和 projection policy，并保持可兼容命令与退出码表面。
- [x] 2.7 为新 validate/list 服务补齐隔离单元测试，证明它们拒绝任意 YAML 执行语义且不会启动项目命令或网络，达到逐模块覆盖门槛。

## 3. 兼容输出合同与投影策略

- [x] 3.1 实现 scanner-owned schema 1.0 projection contract，固定七个顶层字段、Finding/location/context/trace 结构、summary 计数及可选 readiness 的类型不变量。
- [x] 3.2 为 projection contract 补齐隔离单元测试，覆盖有效 payload、字段缺失/改名/类型错误、可选扩展、冻结数据和确定序列化，达到逐模块覆盖门槛。
- [x] 3.3 实现版本化 code-owned Projection Policy，显式映射 detector/observation/classification 到兼容 rule ID、双语文案、severity、Finding 类型、blocking/actionable 和 reachability。
- [x] 3.4 为 Projection Policy 补齐隔离单元测试，覆盖全部正式 detector/classification 组合、guarded/inactive/hint/unknown、未映射输入和输入乱序，达到逐模块覆盖门槛。
- [x] 3.5 增加 policy completeness gate，要求每个可发布 detector/observation kind 均有唯一投影规则且 rule ID 不冲突，禁止从 Legacy YAML 动态补齐。

## 4. Finding、trace、summary 与 readiness 映射

- [x] 4.1 实现 snapshot reference index 和确定性主 Evidence 选择，验证 Classification→Observation→Evidence/Knowledge/Relation/ProofPath 闭包。
- [x] 4.2 为 reference index/主 Evidence 选择补齐隔离单元测试，覆盖断裂引用、多 producer、多位置、空证据、项目相对路径和乱序等价输入，达到逐模块覆盖门槛。
- [x] 4.3 实现兼容 Finding mapper，按语义根因合并 provenance，并将主证据写入既有字段、其余稳定引用和完整性写入对象型 `trace`。
- [x] 4.4 为 Finding mapper 补齐隔离单元测试，覆盖 blocking、actionable non-blocking、guarded/inactive、hint、unknown、去重、排序及兼容字段值，达到逐模块覆盖门槛。
- [x] 4.5 实现 project/summary/diagnostics mapper，使既有计数仅从最终 Finding 计算，并将唯一有效项目 Assessment 投影到可选 `summary.readiness`。
- [x] 4.6 为 project/summary/readiness mapper 补齐隔离单元测试，覆盖全部项目状态、维度、unknown/provisional、零 Finding、冲突 Assessment 和静态范围标志，达到逐模块覆盖门槛。
- [x] 4.7 增加 readiness 文案与结构门禁，禁止输出真实编译成功、测试通过或由缺少命中推导 `riscv_ready`。

## 5. Artifact renderer 与正式 Projector

- [x] 5.1 实现仅消费同一兼容 payload 的确定性 JSON、HTML 和 log renderer，保持现有编码、转义、字段展示和请求 format 行为。
- [x] 5.2 为三个 renderer 补齐隔离单元测试，覆盖中文/英文、HTML 转义、空结果、readiness、diagnostics、格式选择和字节级确定性，达到逐模块覆盖门槛。
- [x] 5.3 实现 `CompatibleReportProjector` 的 payload 校验、临时 staging、受控发布、SHA-256 ArtifactRef 和失败 Diagnostic，确保它是正式路径唯一 writer。
- [x] 5.4 为 Projector 补齐隔离单元测试，使用 temporary/fake writer 注入每个映射、序列化、写入和发布失败点，验证不报告半成品且达到逐模块覆盖门槛。
- [x] 5.5 增加 artifact lifecycle contract test，验证成功、覆盖已有输出、自定义 format、失败清理和默认三文件行为与兼容 baseline 一致。

## 6. 完整 default staged profile 与 CLI 切换准备

- [x] 6.1 审计正式 composite Workspace/Knowledge/Frontend/Normalizer/Analyzer/Detector/Classifier/Assessor 的 default 输入和 completeness，列出并修复会让默认扫描空跑或无证据降级的接线缺口。
- [x] 6.2 对 6.1 中每个实质修改业务模块同步增加隔离 unit mapping、fake/mock 测试和逐模块 90% line / 80% branch 门禁，禁止用集成回归替代。
- [x] 6.3 实现 `create_default_application()`，装配新 Context Factory、全部正式 staged components 和 Compatible Report Projector，且不导入 Legacy/YAML。
- [x] 6.4 为 default factory/profile 补齐隔离单元测试，记录阶段类型与顺序，验证无 no-op、无 Legacy import、无隐藏 service locator 和失败不回退，达到逐模块覆盖门槛。
- [x] 6.5 保持 qualification factory 使用同一正式分析阶段和 recording/no-op Projector，并补充 default/qualification 仅在投影副作用不同的 component test。
- [x] 6.6 在切换前新增 CLI staged-path contract test，覆盖现有 scan 参数、context、退出码、format、compile_commands、排除路径、comment hints 和 target arch，但暂不删除 Legacy oracle。

## 7. Differential oracle 与兼容闭合

- [x] 7.1 实现测试专用结果 normalizer/comparator，消除 checkout/output 根等机器差异并逐字段输出可定位 diff。
- [x] 7.2 为 normalizer/comparator 补齐隔离单元测试，覆盖路径、排序、optional 字段、缺失 artifact、类型变化和恶意 ledger，达到逐模块覆盖门槛。
- [x] 7.3 实现切换前 test-only Legacy/new dual-run harness，确保两个 runner 使用同一只读 fixture/options 且不会执行项目命令、网络或写入 fixture。
- [x] 7.4 对全部 fixture matrix 运行双跑，逐项关闭 parity-required 差异，并将真实、新实现证据充分的修正写入人工 approved-correction ledger。
- [x] 7.5 对未能证明等价或修正合理的差异标为 deferred-blocking 并阻止后续默认切换，不得删除 fixture、降级断言或批量批准。
- [x] 7.6 增加 schema 1.0 旧消费者/后端导入边界 contract test，验证新增 optional readiness/trace 不影响既有反序列化、Finding、summary 和 artifact 保存。
- [x] 7.7 增加 compiler facts、accepted curated facts、rule ID、guarded/inactive/alternative 和 AVX 人工 baseline 的兼容门禁。
- [x] 7.8 增加恶意 recipe/shell/RPM `%check`/plugin/response-file/workspace-escape 的无副作用 differential gate。

## 8. 默认切换与 Legacy 清理

- [x] 8.1 在全部 differential blocker 关闭后，将 CLI `scan` 切换为 `create_default_application()`，移除生产 scan 对 `create_legacy_application()` 和 Legacy namespace adapter 的引用。
- [x] 8.2 更新 CLI/入口集成测试，证明默认 scan 只运行完整 staged profile，必需阶段失败时返回兼容非零结果且不静默回退。
- [x] 8.3 从通过门禁的 Legacy 输出生成并人工审核版本化 normalized golden，记录生成版本和 fixture identity，后续测试不再需要可执行 Legacy。
- [x] 8.4 按 cleanup inventory 删除已有正式替代且 golden 闭合的 Legacy parser/evaluator/model/report bridge、重复正则和无用 `technology/` spike。
- [x] 8.5 对未能删除的旧能力记录 retained/deferred 原因、隔离边界、唯一 fixture 和后续退出条件，不允许其进入默认或 qualification 新管线。
- [x] 8.6 迁移仍有价值的测试去消费新模块或 frozen golden；只删除针对已移除实现细节的测试，不得删除行为/兼容断言。
- [x] 8.7 增加活动包 import/runtime boundary test，禁止 default/qualification/projection 模块引用 Legacy DTO、YAML loader、旧 report 或已删除 technology spike。
- [x] 8.8 审计并最小化 PyYAML/Legacy 专用依赖的运行时用途；仅测试冻结资产仍需要的依赖 SHALL 留在独立测试容器，宿主机和生产文件不得变更。

## 9. 文档与迁移说明

- [x] 9.1 更新 README 的 `--rules` bundle 语义、scanner manifest、默认 staged pipeline、validate/list 行为、schema 1.0、readiness 静态范围和 YAML 扩展退出说明。
- [x] 9.2 更新开发计划、行为验收矩阵和各阶段支持矩阵，将兼容投影、默认切换、Legacy cleanup 标为真实 gate 结果而非预先完成。
- [x] 9.3 记录最终 approved corrections、保留/deferred 能力、golden 版本、cleanup inventory 处置和基于 Git/archive 的回滚步骤。
- [x] 9.4 核对所有文档继续排除 OS/内核/系统调用/驱动/板级迁移，并明确 KB Scanner 没有执行真实 RISC-V 编译或测试。

## 10. 独立容器验收与 OpenSpec 完成

- [x] 10.1 在唯一 `kb-scanner-test` 容器中校验 test inventory 完整性，并逐模块运行新增/修改业务模块 unit suite，分别达到至少 90% line / 80% branch。
- [x] 10.2 在独立测试容器中运行 projection/component/differential/schema/backend-consumer/artifact/no-side-effect/AVX 与关键 fixture 门禁，确认没有 deferred-blocking 或未登记差异。
- [x] 10.3 在独立测试容器中运行完整回归，确认默认 CLI、validate/list、退出码和三个 artifact 无非预期退化。
- [x] 10.4 复核两份 compiler facts、Legacy YAML/`generatedSet`、生产镜像、`backend/Dockerfile` 和根 Compose 未被修改，并清理测试容器资源。
- [x] 10.5 运行 `openspec validate cut-over-kb-scanner-compatible-pipeline --strict`，修复所有 proposal/design/spec/task 一致性问题并确认 apply-ready。
