## Context

阶段 1 至阶段 7 已把 KB Scanner 的 C/C++ 静态分析重建为 scanner-owned staged pipeline：工作区、C/C++ 与构建 Frontend、知识加载、归一化、Evidence Graph、构建/测试选择、Detection、Classification 和 Assessment 均已有正式实现，qualification profile 仍使用空 Projector，默认 CLI 则仍调用 `create_legacy_application()`。因此内部结果更完整，但正式 `scan-result.json`、HTML 和日志仍完全来自 Legacy。

本 change 是最后一次架构切换。它必须同时满足两个看似相反的约束：默认运行时彻底退出 Legacy/YAML，又不能改变后端已依赖的 schema 1.0、字段语义、退出码和三个 artifact。现有两份 Clang/GCC compiler facts 与 accepted curated facts 必须由新 Knowledge Provider 直接消费；Legacy YAML 和 `generatedSet` 仅保留为冻结兼容证据。所有实现和测试继续在独立 `kb-scanner-test` 容器中完成，宿主机与生产镜像不安装依赖。

## Goals / Non-Goals

**Goals:**

- 实现正式、确定、可审计的 schema 1.0 兼容 Projector，并让它成为唯一正式 artifact writer。
- 将完整 staged pipeline 设为 `kb-scanner scan` 默认路径，同时保持既有命令参数、结果顶层结构、字段类型、退出码语义及三个 artifact。
- 用版本化差异 oracle 证明高价值 Legacy 行为已被保留，或把有意修正记录成可审计的 approved delta。
- 让新扫描路径只加载 JSON knowledge manifest、原样 Clang/GCC facts、新 generated facts 和 accepted curated facts，不读取 YAML rule。
- 在等价替代、引用审计和回归门禁全部成立后删除活动代码中的重复 Legacy/spike；无法证明替代的内容继续隔离并明确退出条件。
- 为每个新增或修改业务模块建立隔离单元测试映射及逐模块 90% line / 80% branch 门禁。

**Non-Goals:**

- 不创建 schema 2.0、第二个主结果或新 artifact 名称，不要求后端切换解析器。
- 不执行真实 RISC-V 编译、链接、构建或测试，也不把静态 readiness 描述成真实验证结果。
- 不分析操作系统、内核、系统调用、驱动或板级迁移，不在本模块实现 RVWMO 语义。
- 不修改 `backend/Dockerfile`、根 Compose、生产镜像或宿主机依赖。
- 不继续支持通过任意 Legacy YAML 动态注入扫描逻辑；这是旧配置扩展点的有意退出，但不改变正式结果合同。

## Decisions

### 1. 用独立兼容投影层替代 Legacy report/model 复用

新增 `kb_scanner/projection/`，按职责拆成：

- `contract.py`：scanner-owned schema 1.0 输出 DTO、不变量和序列化键；
- `policy.py`：版本化 detector/observation/classification 到现有 rule ID、标题、reason、suggestion、severity、Finding 类型及 blocking/actionable 语义的确定映射；
- `mapper.py`：把 snapshots 转为兼容 payload，不访问文件系统；
- `renderers.py`：从同一个 payload 生成 JSON、HTML 和 log bytes；
- `projector.py`：校验 payload、写入请求的三个既有 artifact，并返回带摘要的 `ArtifactRef`。

新模块不得导入 `kb_scanner.models`、`kb_scanner.report`、`kb_scanner.rules` 或 `kb_scanner.adapters.legacy`。旧 `Finding`/`ProjectFacts` 不是新核心合同的一部分。选择独立投影层而不是包装 `write_reports()`，是为了避免把 Legacy DTO 和 YAML 派生语义继续固化到新管线。

### 2. 兼容字段由显式投影策略维护，知识事实不承载展示决策

每个可发布 Classification 先定位其 Observation，再确定性选择主 Evidence；选择键依次为项目相对路径、line、column、producer、Evidence ID，不能依赖遍历顺序。主 Evidence 投影到现有 `file`、`line`、`column`、`symbol`、`snippet`、`source_kind`、`confidence`；其他 Evidence、KnowledgeEntry、Relation 和 ProofPath 的稳定 ID、种类、端点、状态、完整性及 producer 摘要写入现有对象型 `trace`。

`policy.py` 以 detector ID、observation kind、classification impact 和受限 context 为键，产生旧消费者需要的 `rule_id`、双语展示文本、severity、`finding_type`、`is_actionable`、`is_blocking` 与 `arch_reachability`。同一语义根因只形成一个稳定 Finding，并合并全部 provenance。未知映射或断裂引用必须返回 failed Diagnostic，不能用通用高危 Finding 掩盖缺口。

投影策略属于 code-owned presentation/classification policy，不进入 KnowledgeSnapshot，也不从 YAML 转换。Clang/GCC 和 curated facts 仍只回答“这是什么事实”；是否阻断、如何展示由 Classification 与投影策略回答。

备选方案是把 YAML 消息和 severity 读入新 Projector。该方案会让默认管线继续依赖已决定淘汰的规则结构，因此不采用。

### 3. 保持 schema 1.0 外形并只增加可选信息

JSON 继续精确包含 `schemaVersion`、`tool`、`rulePack`、`project`、`summary`、`findings`、`diagnostics` 七个顶层字段，`schemaVersion` 固定为字符串 `1.0`。既有 summary 计数从最终兼容 Finding 计算，不能从内部 Observation 数量推算；`location`、`context` 和 Finding 既有字段保持名称、类型和语义。

项目级 Assessment 只投影到可选 `summary.readiness`，内容包括 state、confidence、dimensions、blockingDimensions、completeness、`staticScopeOnly=true`、`compiled=false`、`testsExecuted=false` 和稳定引用摘要。unknown/provisional 必须原样表达；缺少命中、测试或机器产物不能产生 `riscv_ready`。不能安全放入现有字段的信息留在内部或 diagnostics。

新增严格、无执行语义的 `scanner-manifest.json` 作为 bundle descriptor，只声明兼容 `rulePack.id/version`、`knowledge-manifest.json` 的相对路径/摘要及 projection policy identity；它不包含 matcher、正则、severity 或 message。这样 `rulePack.id/version` 无需硬编码，也无需在扫描时读取 `manifest.yaml`。`--rules` 参数继续表示规则/知识包根目录，新路径先校验 bundle descriptor，再由 Knowledge Provider 读取其显式 knowledge manifest/source。默认格式下仍生成 `scan-result.json`、`scan-report.html`、`scan.log`；自定义 `--format` 的既有行为由差异 oracle 固化。

### 4. Projector 是唯一写入者，并使用受控提交避免伪完整产物

Mapper 和 renderer 均为纯函数；只有 `CompatibleReportProjector` 可以写 output directory。Projector 先在 output directory 内的专用临时 staging 位置生成和校验全部请求 artifact，再以确定顺序发布到最终文件名。映射、序列化或写入失败时返回 failed Diagnostic 和非零退出码，不能留下被误认为成功结果的新文件；已存在文件的覆盖行为必须与当前 CLI baseline 一致。

该层不执行项目代码、compiler、build tool、test runner、YAML 扩展、plugin、response file 或网络访问。文件系统、原子替换和失败注入在单元测试中使用临时目录/fake writer，不依赖真实外部进程。

### 5. 差异 oracle 分为“切换前双跑”和“切换后冻结基线”

在删除 Legacy 之前，容器内 differential harness 对同一只读 fixture 分别运行 Legacy 与新 staged profile，规范化 checkout/output 根等机器差异后逐字段比较：退出码、artifact 集、schema、rule ID、Finding 类型、severity、blocking/actionable、位置、reason/suggestion、trace、summary 和 diagnostics。fixture 至少覆盖：

- Clang/GCC generated facts、accepted curated facts及代表性源码命中；
- AVX/x86-only 项目与阶段 5/6/7 人工 baseline；
- guarded、inactive、generic/portable/RISC-V alternative；
- build/test selection、缺失或冲突输入、零命中项目；
- 恶意 recipe、shell、RPM `%check`、plugin/response-file 文本和 workspace escape。

差异分三类：`parity-required`、`approved-correction`、`deferred-blocking`。只有前两类可进入切换；approved correction 必须记录 fixture、字段、Legacy 值、新值、Evidence/proof、理由和稳定 ID，scanner 不得自动重写 ledger。任何未登记差异、重复/过期条目或 `deferred-blocking` 都使门禁失败。

切换通过后，把规范化 Legacy 期望结果固化成版本化 golden oracle，再删除活动 Legacy 实现；后续回归比较新结果与 golden，不要求保留可执行 Legacy。这样既能清理双轨代码，也保留可复核的历史行为。

### 6. 默认切换通过单一 factory 完成，不保留隐式生产回退

新增不依赖 Legacy 的 `adapters/cli.py` 和正式 `create_default_application()`：前者把现有 argparse namespace 转成 ScanRequest，并由严格 bundle/context factory 构造 ScanContext；后者装配完整 composite stages 和 `CompatibleReportProjector`。CLI `scan` 只调用该 factory。qualification factory 继续允许 no-op Projector，用于内部组件验收；它不写正式 artifact。生产 scan 不提供“出错自动回退 Legacy”的路径，因为回退会造成同一输入的语义不可预测。

`validate-rules` 与 `list-rules` 保留命令表面和退出码，但改为验证/列出新 knowledge bundle、detector 和 projection policy；它们不加载或执行 YAML。任意自定义 YAML 规则扩展不再进入扫描，这是从数据驱动执行规则向 code-owned detector 的有意配置迁移。CLI 帮助、README 和 diagnostics 必须明确 `--rules` 现在指向包含 `knowledge-manifest.json` 的 bundle。

备选方案是长期暴露 `--legacy` 或环境变量。该方案会维持两套生产行为并延长清理，因此不采用；回滚通过版本/提交回退完成。

### 7. Legacy 清理以运行时引用图和能力矩阵为准

清理前生成机器可读 inventory，逐个列出 `adapters/legacy.py`、`rules.py`、`cpp_frontend.py`、`compile_commands.py`、`models.py`、`report.py` 和 `technology/` 文件的生产引用、测试引用、正式替代模块、差异 fixture 与处置。只有满足以下条件才可删除：默认 factory 无引用、正式替代存在、对应 unit/component/differential gate 通过、golden 已冻结。

Legacy YAML 和全部 `generatedSet` 引用保持原文件不变，作为冻结 oracle/审计资产；默认和 qualification 新管线均不得读取它们。已有 `archive/2026-09-04-pre-rewrite` 继续作为历史源码参考，不自动导入或执行。若某项能力没有等价替代，inventory 必须标为 retained/deferred，给出隔离边界与后续删除条件，不能通过静默删测完成清理。

### 8. 单元门禁按业务模块逐项计算

新增 `tests/compatible-cutover-test-inventory.json`，至少映射 bundle descriptor/context factory、`adapters/cli.py`、`projection/contract.py`、`projection/policy.py`、`projection/mapper.py`、`projection/renderers.py`、`projection/projector.py`、默认 profile factory、differential comparator/ledger validator 和 cleanup inventory validator。每个业务模块必须有隔离 unit suite，逐模块至少 90% line / 80% branch；真实 parser、真实知识包、双跑、后端契约、artifact E2E 和 full regression 不计入这些单元覆盖数字。

单元边界使用内存 snapshots、fake/temporary writer、固定 knowledge/evidence/proof、fake stage 和受控故障；不得启动 compiler、构建工具、测试目标或网络。高层门禁另外覆盖真实 JSON knowledge、AVX baseline、三 artifact 字节/语义、旧消费者 JSON schema、无副作用与全量回归。所有命令只在独立 `kb-scanner-test` 容器运行。

## Risks / Trade-offs

- [新检测能力使 Finding 数量与 Legacy 不完全相同] → 使用 approved-correction ledger 逐条解释新增/修正，未登记差异阻断切换。
- [强行保持旧 rule ID/文案可能限制内部模型] → 兼容限制只存在于 projection policy；内部 Evidence/Classification/Assessment 保持独立。
- [主 Evidence 选择不稳定导致结果漂移] → 使用项目相对位置和稳定 ID 排序，并用输入乱序测试验证字节级确定性。
- [Projector 失败留下半套 artifact] → staging 后统一发布并注入每个写入失败点测试；失败不得报告成功 ArtifactRef。
- [删除 Legacy 后难以现场回退] → 删除前冻结 golden 与 inventory，源码仍可从 Git 和已有 archive 恢复；生产不维护隐藏双轨。
- [YAML 扩展退出影响旧的自定义规则使用者] → 保留 CLI 参数形状并提供明确诊断/README 迁移说明；正式能力改由 knowledge source、detector 和 projection policy 受测接入。
- [静态结果被误读为真实 RISC-V 验证] → readiness 强制带 scope/compiled/testsExecuted 标志，HTML 与 diagnostics 使用静态限定文案。

## Migration Plan

1. 冻结现有输出 schema、关键 fixture、compiler-fact hashes 与 Legacy normalized golden；建立严格 bundle descriptor、差异分类 ledger 和 cleanup inventory。
2. 实现纯 projection contract/policy/mapper 及隔离单元测试，再实现 renderer/projector 的 staging 写入与故障测试。
3. 建立正式 default staged profile；先在测试中显式调用，与 Legacy 双跑并关闭所有未登记差异。
4. 验证后端兼容 schema、CLI 参数/退出码、三个 artifact、AVX/x86-only、guarded/inactive/alternative、unknown 和恶意输入。
5. 将 `kb-scanner scan` 切换到 `create_default_application()`；确认扫描路径不导入 Legacy/YAML，并保持 qualification no-op 路径。
6. 固化切换后的 golden，按 inventory 删除已替代 Legacy/spike，重新运行 import boundary、逐模块覆盖和完整回归。
7. 仅在所有门禁通过后更新文档并完成 change；回滚时恢复切换前提交，而不是运行时静默回退。

## Open Questions

- apply 阶段需要根据真实双跑结果确定具体 approved-correction 条目；设计不预先批准任何差异。
- 若 `validate-rules`/`list-rules` 的历史文本输出存在外部脚本依赖，优先保持行格式并只替换数据来源；无法兼容的差异必须进入同一 ledger 后再决定。
