## ADDED Requirements

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
