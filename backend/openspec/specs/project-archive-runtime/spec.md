## Purpose

定义项目归档节点的运行时能力。项目归档用于在任意阶段将当前源码版本下已经产生的报告、摘要和可下载制品固化成归档记录，并生成可下载归档包。
## Requirements
### Requirement: 项目归档必须基于当前源码版本的待归档候选
系统 SHALL 使用待归档候选作为项目归档的数据来源，并 SHALL 只归档当前 active 源码版本下的 active 候选内容。

#### Scenario: 归档当前状态
- **WHEN** 用户点击归档节点页的“归档当前状态”按钮
- **THEN** 后端 SHALL 创建项目归档任务
- **AND** 归档任务 SHALL 读取该项目当前 active `source_revision_id` 下 `status=ACTIVE` 的归档候选
- **AND** 归档任务 MUST NOT 读取其他源码版本的归档候选

#### Scenario: 新源码版本未产生候选
- **WHEN** 项目激活新的源码版本且该版本尚未产生任何归档候选
- **THEN** 归档当前状态 MUST NOT 展示或打包上一源码版本的候选内容
- **AND** 后端 SHALL 返回明确业务错误或生成不包含业务报告的受控空归档

#### Scenario: 任意阶段归档
- **WHEN** 用户在 KB、SBOM、报告、构建、测试或比较等任意阶段之后执行归档
- **THEN** 归档 SHALL 只包含当时已经登记的候选内容
- **AND** 未执行或未登记候选的阶段 MUST NOT 出现在归档详情或归档包中

### Requirement: 归档候选必须由业务节点可插拔登记
各业务节点 SHALL 在成功产生可归档报告、摘要或制品后登记归档候选，使归档运行时不需要硬编码每个节点的查询逻辑。

#### Scenario: 节点登记归档候选
- **WHEN** 业务节点成功生成可归档内容
- **THEN** 该节点 SHALL upsert 当前项目和源码版本下的归档候选
- **AND** 候选 SHALL 包含 `nodeType`、`candidateType`、`candidateKey`、真实资源引用、安全摘要和 artifact 引用

#### Scenario: 候选展示类型
- **WHEN** 前端查询归档候选或归档详情
- **THEN** 响应 SHALL 同时返回 `nodeType` 和 `candidateType`
- **AND** `nodeType` SHALL 表达来源节点
- **AND** `candidateType` SHALL 表达前端展示方式

#### Scenario: 节点新增不修改归档核心
- **WHEN** 后续新增业务节点并需要纳入归档
- **THEN** 该节点 SHALL 通过登记归档候选接入归档流程
- **AND** 归档打包核心 MUST NOT 为该节点新增硬编码的最新结果查询分支

### Requirement: 归档记录必须固化候选快照
归档记录 SHALL 固化创建时读取到的候选内容，使历史归档不受后续源码版本或候选更新影响。

#### Scenario: 归档项固化
- **WHEN** 归档任务读取 active candidates
- **THEN** 后端 SHALL 为每个 candidate 创建归档项
- **AND** 归档项 SHALL 保存 candidate ID、`nodeType`、`candidateType`、资源引用、标题、摘要和 artifact 引用快照

#### Scenario: 后续候选变化
- **WHEN** 归档完成后同一项目产生新的源码版本或新的候选内容
- **THEN** 已完成归档的详情和下载内容 SHALL 保持创建时的快照
- **AND** 已完成归档 MUST NOT 动态读取当前 candidate 状态覆盖历史内容

### Requirement: 归档包必须汇总本次归档内的报告文件
系统 SHALL 为每条成功归档记录生成可下载归档包，汇总本次归档内已有的 HTML、JSON、LOG 或摘要文件。

#### Scenario: 下载归档包
- **WHEN** 用户下载归档包
- **THEN** 后端 SHALL 返回该归档记录生成时的压缩包
- **AND** 压缩包 SHALL 包含 `manifest.json` 和 `summary.json`
- **AND** 压缩包 SHALL 包含本次归档项引用的可下载 HTML、JSON、LOG 或摘要文件

#### Scenario: 归档包不包含未执行阶段
- **WHEN** 某个阶段没有登记归档候选
- **THEN** 归档包 MUST NOT 为该阶段生成占位报告文件
- **AND** manifest SHALL 只列出实际包含的归档项

#### Scenario: 归档包安全
- **WHEN** 后端生成归档包
- **THEN** 归档包文件名和内部路径 SHALL 使用受控相对路径
- **AND** 归档包 MUST NOT 包含明文凭据、对象存储内部 key、服务器真实路径或完整任务输入快照

### Requirement: 归档必须支持依赖分析候选
项目归档运行时 SHALL 支持归档当前源码版本下的依赖分析报告和结果摘要，并 SHALL 保留历史 SBOM 归档项兼容。

#### Scenario: 登记依赖分析归档候选
- **WHEN** 依赖分析成功生成 HTML、JSON 或摘要制品
- **THEN** 后端 SHALL 为当前 `sourceRevisionId` 登记归档候选
- **AND** 候选的 `nodeType` 或等效字段 SHALL 表达依赖分析节点
- **AND** 候选 SHALL 关联依赖分析运行、任务和制品引用

#### Scenario: 归档当前状态包含依赖分析
- **WHEN** 用户归档当前状态且当前源码版本存在 active 依赖分析候选
- **THEN** 归档 SHALL 固化依赖分析报告、JSON 摘要和结果统计
- **AND** 归档详情和下载包 MUST NOT 暴露对象存储内部 key 或服务器真实路径

#### Scenario: 历史 SBOM 归档兼容
- **WHEN** 用户查看包含 SBOM 归档项的历史归档
- **THEN** 后端 SHALL 继续展示和下载历史 SBOM 归档项
- **AND** 新归档默认 SHALL 使用依赖分析候选而不是 SBOM 候选

### Requirement: 归档候选摘要必须保持安全轻量
归档候选 summary SHALL 作为归档列表和归档 manifest 的安全索引摘要使用，不得承载完整报告正文、完整问题明细、原始 evidence、服务器路径、对象存储内部位置或敏感凭据；合法路径字段名和安全项目相对路径不应仅因名称或相对路径形式被拒绝。

#### Scenario: 业务节点登记报告候选
- **WHEN** 业务节点成功生成可归档报告并登记归档候选
- **THEN** 候选 summary SHALL 只包含聚合统计、受控资源 ID、状态、风险摘要和可安全展示的短文本
- **AND** 完整报告内容 SHALL 通过 artifact 引用下载
- **AND** 候选 summary MUST NOT 包含 `locationLabel` 明细列表、完整 `evidence`、完整输入快照、bucket、object key 或服务器真实路径

#### Scenario: 候选摘要包含合法路径结构
- **WHEN** 候选 summary 包含 `path`、`paths`、`filePath` 等字段名，且字段值为空列表、文件名或不含目录穿越的安全项目相对路径
- **THEN** 归档候选服务 SHALL 允许保存该候选
- **AND** 后端 MUST NOT 仅因为字段名包含 `path` 而拒绝候选

#### Scenario: 候选摘要包含危险路径文本
- **WHEN** 候选 summary 中包含服务器绝对路径、`../` 目录穿越、对象存储内部 key、凭据、token 或私钥相关文本
- **THEN** 归档候选服务 SHALL 拒绝保存该候选
- **AND** 调用方 SHALL 将该失败作为候选登记失败处理
- **AND** 调用方 MUST NOT 因候选登记失败泄露被拒绝的敏感文本

#### Scenario: 嵌套候选摘要安全校验
- **WHEN** 合法或危险内容出现在嵌套 object、array 或集合中
- **THEN** 归档候选服务 SHALL 递归执行相同的字段和值安全校验
- **AND** 空 `paths` 数组 SHALL 被视为安全内容

#### Scenario: 归档打包读取候选
- **WHEN** 归档任务读取 active candidates 生成归档详情和归档包
- **THEN** 归档详情 SHALL 使用候选 summary 作为列表摘要
- **AND** 归档包 SHALL 通过 artifact 引用读取完整 HTML、JSON 或 LOG
- **AND** 归档任务 MUST NOT 假设候选 summary 包含完整报告明细

### Requirement: 归档必须兼容依赖自动修复制品登记
项目归档运行时 SHALL 允许依赖自动修复节点在产生报告或摘要制品时登记归档候选，并 SHALL 在无制品时保持现有归档行为不变。

#### Scenario: 登记依赖自动修复归档候选
- **WHEN** 依赖自动修复任务生成 HTML、JSON 或摘要制品
- **THEN** 后端 SHALL 按全局归档规则登记归档候选
- **AND** 候选 SHALL 关联项目、源码版本、任务、自动修复运行和制品引用
- **AND** 候选的 `nodeType` 或等效字段 SHALL 表达依赖自动修复节点

#### Scenario: 无制品时不登记候选
- **WHEN** 依赖自动修复任务只产生运行记录、条目记录和任务日志
- **THEN** 后端 MAY 不登记归档候选
- **AND** 项目归档 MUST NOT 因没有依赖自动修复制品而失败

### Requirement: 项目归档必须提供 latest
项目归档领域 SHALL 提供当前 Context 下的 latest 接口，用于展示最近归档记录和归档物摘要。

#### Scenario: 查询归档 latest
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/archives/latest`
- **THEN** 后端 SHALL 返回统一 latest 外壳
- **AND** `result` SHALL 包含最近归档记录、归档 item 摘要和下载入口信息

#### Scenario: 当前 Context 没有归档
- **WHEN** 当前源码版本下没有归档记录
- **THEN** latest SHALL 成功返回
- **AND** `freshness` SHALL 为 `EMPTY` 或 `STALE`

### Requirement: 项目归档 readiness 必须返回可归档事实
项目级 readiness 在 `stageId=archive` 时 SHALL 返回归档所需前置条件。

#### Scenario: 当前 Context 存在可归档内容
- **WHEN** 当前源码版本下存在归档候选或已完成报告
- **THEN** readiness SHALL 返回对应 prerequisite 为 `SATISFIED`
- **AND** `referenceId` SHALL 指向候选、报告或执行记录

#### Scenario: 当前 Context 无可归档内容
- **WHEN** 当前源码版本下没有可归档内容
- **THEN** readiness SHALL 返回 `MISSING`
- **AND** `reasonCode` SHALL 为 `ARCHIVE_CANDIDATES_MISSING`

### Requirement: 专项分析必须登记可插拔归档候选
浮点和内存序运行成功发布可查询结果后 SHALL 为当前源码版本登记归档候选，包括安全摘要、JSON 和 HTML；内存序 MAY 额外登记审计 bundle。

#### Scenario: 登记浮点制品
- **WHEN** 浮点运行完成并保存制品
- **THEN** 系统 SHALL 登记 node type、candidate type、run reference、JSON 与 HTML artifact

#### Scenario: 登记内存序制品
- **WHEN** 内存序运行完成并保存统一输出
- **THEN** 系统 SHALL 登记 JSON、HTML 和受控审计 bundle
- **AND** 摘要 SHALL 包含 verdict、Finding、candidate、Scope 和 diagnostic 数量

#### Scenario: 新源码版本隔离
- **WHEN** 项目激活新的源码版本
- **THEN** 归档当前状态 MUST NOT 收集旧源码版本的专项分析候选
- **AND** 历史归档详情仍 SHALL 保持可读

### Requirement: 专项归档摘要必须安全且轻量
归档候选摘要 SHALL 只包含展示所需计数、状态、版本和业务引用，不得嵌入完整 Finding、证据图、源码上下文或服务器路径。

#### Scenario: 内存序输出很大
- **WHEN** 审计 bundle 包含大量 evidence steps 和 source snapshots
- **THEN** candidate summary SHALL 仅保存聚合计数与 artifact reference
- **AND** 完整内容 SHALL 通过受控制品读取
