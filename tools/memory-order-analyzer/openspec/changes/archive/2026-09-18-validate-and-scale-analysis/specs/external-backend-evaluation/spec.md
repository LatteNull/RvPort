## ADDED Requirements

### Requirement: Isolate external backends from the analyzer runtime

GenMC 与 herdtools7 SHALL 通过独立进程或容器适配器执行，显式指定二进制/镜像 digest、版本、许可证、命令、环境、预算和工作目录；它们 MUST NOT 成为核心安装、P1–P4 执行、单元测试或离线默认验收的依赖。适配器不得修改输入源码、BC triple、P1–P4 产物或生产 Dockerfile。

#### Scenario: An external backend is not installed

- **WHEN** 默认离线单元/语料验证环境没有 GenMC 或 herdtools7
- **THEN** 核心验证仍可完成，未请求后端为 not_run，不将缺少工具当作分析器成功或失败

#### Scenario: A requested backend is unavailable

- **WHEN** request 显式要求某后端但其固定二进制/镜像不可用
- **THEN** backend evaluation 为 partial/unavailable、整体退出 2，并保留其他验证结果

### Requirement: Declare applicability and transformations per backend case

每个 backend case SHALL 声明源语言/模型、线程 API、输入形式、支持特性、转换步骤和与 truth case 的映射。无法表示跨 TU、pthread、fence、RMW、对象生命周期或优化配置时 MUST 标为 not_applicable/unsupported，不得删减关键语义后仍称为等价验证。

#### Scenario: A herd litmus cannot represent the source case

- **WHEN** C/C++ case 的控制流、对象生命周期或线程库语义不能忠实映射到 herd 输入
- **THEN** 记录 not_applicable 和缺失关系，不用近似 litmus 的结果替代源码 truth

#### Scenario: A supported subset is transformed

- **WHEN** case 可按版本化规则转换为后端输入
- **THEN** bundle 保存转换器版本、原/目标 hash、映射表和限制，使结果可复核

### Requirement: Preserve raw and normalized backend evidence

系统 SHALL 生成严格 `BackendEvidenceBundle v1`，包含 backend 身份、输入/转换/命令 hash、退出状态、stdout/stderr 或报告 hash、资源计数、原始类别、规范化 observation、诊断和完整性。解析失败、未知版本或损坏输出 MUST 被拒绝或标为 failed，不得转成“无风险”。

#### Scenario: A backend returns exit zero with no parseable result

- **WHEN** 进程成功退出但预期报告缺失、为空或不符合锁定版本格式
- **THEN** bundle 为 failed/partial 并保留原始证据，不生成同意 P4 的 observation

#### Scenario: Recorded output is replayed in unit tests

- **WHEN** 单元测试读取固定的成功、差异、超时和损坏输出夹具
- **THEN** 适配器确定地产生相同规范化 bundle，无需启动第三方工具

### Requirement: Treat backend comparison as evidence rather than oracle

comparison SHALL 并列展示人工 truth、P4 observation 和各后端 observation，保存 agree/disagree/not_applicable/inconclusive 及原因。外部工具一致、零建议或更多建议 MUST NOT 自动改变 truth、P4 verdict、safety 或准确率分母；只有人工复核后的 truth 新版本可改变期望。

#### Scenario: Both backends agree with P4

- **WHEN** GenMC、herdtools7 和 P4 在适用 case 上给出相同类别
- **THEN** 记录 agreement 及各自模型边界，不将其表述为已证明全程序安全或检测完备

#### Scenario: A backend contradicts P4

- **WHEN** 某后端 observation 与 P4 或 truth 不同
- **THEN** 发布输入映射、模型/版本和差异供人工裁决，不按预设优先级自动判任一方正确

### Requirement: Import ARM DevKit evidence without SSH execution

P5 SHALL 只导入用户显式提供或仓库已有的 ARM DevKit 证据，验证工具/LLVM 版本、采集日期、源/BC/命令/报告 hash 和证据包完整性；MUST 保留 2026-09-10 SSH 失败和 2026-09-11 DevKit 25.3.0/LLVM 16.0.4 历史原义，不提供自动 SSH runner 或以当前网络状态作为验收前提。

#### Scenario: Historical DevKit evidence is imported

- **WHEN** 导入仓库中 2026-09-11 的代表报告和矩阵
- **THEN** bundle 标记 historical/imported、版本和已知缺口，47 份 success 不计为 truth 准确率或本次重新执行

#### Scenario: A new DevKit package is incomplete

- **WHEN** 新证据缺少输入 hash、原始报告、版本或计划分母
- **THEN** 导入为 partial 或拒绝，不因扫描退出零而声明完整

### Requirement: Bound external execution and preserve failures

外部适配器 SHALL 应用 request 的 wall、memory、output-size 和 case 预算，禁止网络访问并限制写入专用临时/输出目录；超时、崩溃、非零退出和截断输出 SHALL 形成可引用诊断及 frontier。清理只能针对已验证的专用临时目录，不得删除用户源码、artifact store 或历史证据。

#### Scenario: A backend exceeds its time budget

- **WHEN** 后端在限定时间内未完成
- **THEN** 终止该隔离进程，保存 timeout、已知输出 hash 和未完成 case，其他 case/核心报告继续可用
