## ADDED Requirements

### Requirement: 迁移报告必须按模块文件类型和问题组织代码输入
迁移评估报告 SHALL 将代码类 confirmed 输入组织为“模块、文件、问题类型、具体 finding”四级层级，并 SHALL 保证每条输入只计入一个主模块和一个文件分组。

#### Scenario: 生成代码输入层级
- **WHEN** 报告生成任务读取当前报告源码版本下的代码类 confirmed 输入
- **THEN** 后端 SHALL 为每条输入保存模块、文件、问题类型和 finding 的组织投影
- **AND** 模块 finding 总数 SHALL 等于已组织代码类报告输入总数
- **AND** 同一 finding MUST NOT 因关联多个构建目标而重复计数

#### Scenario: 输入缺少有效文件定位
- **WHEN** 代码类 confirmed 输入缺少路径或有效行号
- **THEN** 后端 SHALL 将输入保留为可审计的未定位条目
- **AND** 后端 MUST NOT 因无法定位而丢弃该输入或使报告生成失败

### Requirement: 模块识别必须使用确定性降级链
后端 SHALL 按显式构建目标、构建产物或链接关系、最近构建描述文件、目录分组、项目根模块的顺序识别代码文件所属模块，并 SHALL 返回识别依据和置信度。

#### Scenario: 构建目标明确关联文件
- **WHEN** 报告绑定的构建上下文明确记录文件属于某个构建目标
- **THEN** 后端 SHALL 优先使用该构建目标作为模块
- **AND** 模块 SHALL 返回稳定的 `moduleKey`、`moduleName`、`basis` 和 `confidence`

#### Scenario: 构建上下文不足
- **WHEN** 文件无法通过构建目标或构建产物关系识别模块
- **THEN** 后端 SHALL 依次尝试最近构建描述文件和目录分组
- **AND** 所有策略均无法形成分组时 SHALL 回退到项目根模块

#### Scenario: 文件关联多个构建目标
- **WHEN** 同一文件被多个构建目标引用
- **THEN** 后端 SHALL 将文件归入确定性的共享模块或主模块
- **AND** 响应 SHALL 提供关联模块标识
- **AND** 该文件中的 finding MUST NOT 被复制计数

### Requirement: 报告代码层级接口必须支持逐级统计和分页查询
后端 SHALL 提供报告代码模块、模块文件、文件问题类型和具体 finding 的独立查询接口，并 SHALL 在每一级返回前端展示直接下级所需的统计。

#### Scenario: 查询模块列表
- **WHEN** 有项目访问权限的用户查询报告代码模块
- **THEN** 后端 SHALL 返回分页模块列表
- **AND** 每个模块 SHALL 包含文件数、finding 数、问题类型数、最高风险、风险分布、类型分布、识别依据和置信度

#### Scenario: 查询模块下的文件和类型
- **WHEN** 有项目访问权限的用户查询指定模块的文件或指定文件的问题类型
- **THEN** 文件响应 SHALL 包含 finding 数、问题类型数、最高风险、风险分布和类型分布
- **AND** 类型响应 SHALL 包含 finding 数、最高风险、首行、末行和符号数
- **AND** 列表 SHALL 支持白名单过滤、排序和分页

#### Scenario: 查询具体 finding 的默认顺序
- **WHEN** 用户未提交 finding 排序参数
- **THEN** 后端 SHALL 按 `lineStart ASC NULLS LAST`、`lineEnd ASC NULLS LAST` 和稳定 ID 升序返回

#### Scenario: 无权读取其他项目报告
- **WHEN** 用户查询无权访问项目中的报告层级数据
- **THEN** 后端 SHALL 拒绝请求
- **AND** 响应 MUST NOT 泄露模块、文件、finding 或源码上下文信息

### Requirement: 报告必须提供文件级联合源码上下文
后端 SHALL 为报告内代码文件提供联合源码上下文，默认覆盖首个纳入报告 finding 之前 20 行至最后一个纳入报告 finding 之后 20 行，并 SHALL 高亮该文件内所有纳入报告的 finding。

#### Scenario: 同一文件存在多个 finding
- **WHEN** 用户查询报告中某文件的联合上下文
- **THEN** 后端 SHALL 返回该文件所有已纳入报告 finding 的元数据
- **AND** 上下文 SHALL 从最早 finding 的起始行向前最多 20 行开始
- **AND** 上下文 SHALL 在最晚 finding 的结束行之后最多 20 行结束
- **AND** 每个代码行 SHALL 返回真实行号、文本和关联 finding 高亮

#### Scenario: 文件边界不足二十行
- **WHEN** finding 距离文件头或文件尾不足 20 行
- **THEN** 后端 SHALL 将上下文裁剪到真实文件边界
- **AND** 后端 MUST NOT 生成不存在的行号或占位代码

#### Scenario: 只包含生成报告时的 finding
- **WHEN** 同一路径在当前输入池中还有 candidate、excluded 或其他源码版本的 finding
- **THEN** 文件上下文 SHALL 只高亮该报告输入快照中的 confirmed finding
- **AND** 后端 MUST NOT 动态混入当前输入池或 active source revision 的其他问题

### Requirement: 文件上下文省略必须结构化表达
当联合上下文跨度超过服务端限制时，后端 SHALL 以 `CODE` 和 `OMITTED` block 返回内容，并 MUST NOT 将省略提示伪装成源码文字。

#### Scenario: 远距离 finding 之间产生省略区间
- **WHEN** 同一文件的 finding 窗口之间存在超过阈值的未命中行
- **THEN** 响应 SHALL 为真实源码返回 `kind=CODE` block
- **AND** 响应 SHALL 为省略范围返回 `kind=OMITTED` block
- **AND** `OMITTED` block SHALL 包含起止行、行数、稳定原因码和 `loadable` 状态

#### Scenario: 展开可加载省略区间
- **WHEN** 用户使用文件上下文 API 请求 `OMITTED` block 对应的合法行范围
- **THEN** 后端 SHALL 返回该范围内的真实代码行
- **AND** 返回内容 SHALL 继续使用报告绑定的源码版本

### Requirement: 文件上下文必须保持历史版本完整性和路径安全
报告文件上下文 SHALL 绑定报告的不可变 `sourceRevisionId`、规范化相对路径、内容哈希和行号范围，且 SHALL 通过对象存储制品或等价不可变快照提供内容。

#### Scenario: 源码更新后查看旧报告
- **WHEN** 项目 active source revision 已更新且用户查看旧报告文件上下文
- **THEN** 后端 SHALL 返回旧报告生成时绑定的源码内容和哈希
- **AND** 后端 MUST NOT 回退读取当前 active source revision

#### Scenario: 路径逃逸或文件不可读取
- **WHEN** 报告输入路径逃逸源码根、文件缺失、文件为二进制、文件过大或行号失效
- **THEN** 后端 SHALL 返回 `contextAvailable=false` 和稳定原因码
- **AND** 后端 MUST NOT 返回宿主机绝对路径、对象存储内部位置或底层异常细节
- **AND** 该情况 MUST NOT 使整份报告生成失败

### Requirement: 依赖迁移输入必须保持全局聚合展示
迁移评估报告 SHALL 将依赖分析输入独立于代码模块层级展示，并 SHALL 按 provider 软件包或待安装软件包聚合依赖证据。

#### Scenario: 同一软件包提供多个库或程序
- **WHEN** 多个 SO 或 ELF 证据解析到同一 provider 软件包
- **THEN** 报告 SHALL 只生成一个软件包主条目
- **AND** SO 或 ELF SHALL 作为该条目的 evidence 展示
- **AND** 条目 SHALL 展示依赖类型、目标匹配状态、风险和一键修复状态

#### Scenario: 依赖没有代码文件定位
- **WHEN** confirmed 依赖输入没有源码文件位置
- **THEN** 后端 SHALL 将其保留在全局依赖迁移列表
- **AND** 后端 MUST NOT 将其强行归入项目根代码模块

### Requirement: HTML 和 JSON 报告必须共享组织口径
后端 SHALL 使用同一版本化报告视图模型生成 HTML 与 JSON 报告，并 SHALL 包含执行摘要、代码模块/文件层级、全局依赖迁移列表和原始证据附录。

#### Scenario: 生成组织化报告制品
- **WHEN** 报告生成任务成功完成
- **THEN** HTML 和 JSON 的模块数、文件数、finding 数、风险分布和依赖条目数 SHALL 一致
- **AND** HTML SHALL 默认以聚合摘要展示并避免一次渲染全部源码行
- **AND** JSON SHALL 通过 schemaVersion 标识新的组织结构

#### Scenario: 查看缺少组织投影的历史报告
- **WHEN** 用户查看本变更前生成且没有组织投影的历史报告
- **THEN** 后端 SHALL 返回 `organizationAvailable=false` 或等价兼容状态
- **AND** 既有平铺输入接口及历史 HTML/JSON 下载 SHALL 保持可用
- **AND** 后端 MUST NOT 使用当前算法覆盖历史报告内容
