## MODIFIED Requirements

### Requirement: 项目创建阶段详情

项目流水线工作台 SHALL 在用户点击 `project` 节点后打开项目基础配置 Drawer，并根据 `projectId` 与 `stageId` 获取项目详情数据。

#### Scenario: 请求项目创建阶段详情

- **WHEN** 用户点击 Workflow 中的 `project` 节点
- **THEN** 系统 SHALL 使用当前 `projectId` 与 `stageId=project` 请求阶段详情接口

#### Scenario: 展示项目基本信息

- **WHEN** 项目基础配置详情加载成功
- **THEN** 抽屉 SHALL 展示项目名称、项目描述、源架构、目标架构、C/C++ 源码来源和首批语言

#### Scenario: 仅项目描述可编辑

- **WHEN** 用户查看项目基础配置详情
- **THEN** 抽屉 SHALL 默认以只读文本展示项目描述，并在项目描述标签旁提供编辑入口
- **AND** 用户点击编辑入口后，系统 SHALL 仅将项目描述切换为可编辑输入框
- **AND** 项目名称、源架构、目标架构、C/C++ 源码来源和首批语言 SHALL 只读展示

#### Scenario: 保存项目描述

- **WHEN** 用户在项目描述编辑态确认保存
- **THEN** 系统 SHALL 调用项目创建阶段更新接口保存项目描述
- **AND** 系统 SHALL 在保存成功后恢复项目描述展示态

#### Scenario: 取消编辑项目描述

- **WHEN** 用户取消项目描述编辑
- **THEN** 系统 SHALL 恢复最近一次已保存的项目描述
- **AND** 系统 SHALL 恢复项目描述展示态

#### Scenario: 展示项目状态信息

- **WHEN** 项目基础配置详情加载成功
- **THEN** 抽屉 SHALL 展示项目当前的 x86 源环境、RISC-V 目标环境、知识库扫描、依赖分析、构建验证和自动化测试进展

#### Scenario: 展示项目创建阶段操作

- **WHEN** 项目基础配置详情加载成功
- **THEN** 抽屉 footer SHALL 展示进入环境管理和进入源码管理两个同级入口
- **AND** 保存和取消编辑操作 SHALL 位于项目描述编辑区域

#### Scenario: 继续环境管理

- **WHEN** 用户确认进入环境管理，且项目描述不处于编辑态
- **THEN** 系统 SHALL 打开环境管理节点的 Drawer

#### Scenario: 进入源码管理

- **WHEN** 用户确认进入源码管理，且项目描述不处于编辑态
- **THEN** 系统 SHALL 打开源码管理节点的 Drawer

#### Scenario: 编辑期间阻止推进

- **WHEN** 用户编辑项目描述时尝试进入环境管理或源码管理
- **THEN** 系统 SHALL 阻止导航
- **AND** 系统 SHALL 提示用户先保存或取消编辑

### Requirement: 环境管理阶段详情

项目流水线工作台 SHALL 在用户点击 `env` 节点后打开专属环境管理 Drawer，并加载当前项目的远程环境资源。

#### Scenario: 请求环境列表

- **WHEN** 用户点击 Workflow 中的 `env` 节点
- **THEN** 系统 SHALL 使用当前 `projectId` 请求项目环境列表接口

#### Scenario: 展示环境列表

- **WHEN** 环境列表加载成功
- **THEN** Drawer SHALL 展示名称、角色、架构、OS、主机、连接状态、最近采集时间和行级操作

#### Scenario: 展示项目级分析环境

- **WHEN** 用户打开环境管理 Drawer
- **THEN** 系统 SHALL 使用当前 `projectId` 读取项目级运行环境配置
- **AND** SHALL 以“当前运行环境”展示当前 x86 源环境与 RISC-V 目标环境的配置状态
- **AND** 环境名称 SHALL 在当前卡片完整展示，必要时换行，不得仅以省略号截断
- **AND** SHALL 说明该配置会被后续需要执行环境的节点复用

#### Scenario: 配置项目级分析环境

- **WHEN** 用户在环境管理中发起配置当前运行环境
- **THEN** 系统 SHALL 请求 `status=AVAILABLE` 的环境候选列表，并在客户端继续排除未启用或 SSH 连接未成功的环境
- **AND** 系统 SHALL 在同一 Drawer 内选择 x86 源环境和 RISC-V 目标环境
- **AND** 保存后 SHALL 更新项目级运行环境配置并刷新共享读取缓存

#### Scenario: 搜索和筛选环境

- **WHEN** 用户在环境列表使用关键词搜索或组合筛选条件
- **THEN** 系统 SHALL 按名称、主机、角色、连接状态和采集状态过滤当前环境列表
- **AND** 系统 SHALL 提供一键重置筛选条件的入口

#### Scenario: 新建环境

- **WHEN** 用户点击环境列表标题右侧的新建环境
- **THEN** 系统 SHALL 在同一个 Drawer 内切换至新建环境视图
- **AND** 新建环境视图 SHALL 支持服务器名称、主机、环境角色、架构、SSH 端口、登录类型和工作目录配置

#### Scenario: 根据登录类型填写凭据

- **WHEN** 用户选择账号密码或密钥登录类型
- **THEN** 系统 SHALL 仅展示该登录类型对应的凭据输入字段
- **AND** 系统 SHALL NOT 在环境读取模型或编辑表单中返回密码、私钥或密钥正文

#### Scenario: 上传私钥内容

- **WHEN** 用户选择密钥登录并上传私钥文件
- **THEN** 系统 SHALL 读取文件内容并填入当前表单的私钥字段
- **AND** 系统 SHALL 不单独持久化私钥文件
- **AND** 拖拽导入提示 SHALL 使用次级文本颜色

#### Scenario: 修改环境

- **WHEN** 用户对环境行发起修改操作
- **THEN** 系统 SHALL 在同一个 Drawer 内切换至该环境的修改视图
- **AND** 服务器名称 SHALL 只读展示
- **AND** 只有用户重新填写的敏感凭据 SHALL 覆盖已保存凭据

#### Scenario: 测试表单连接配置

- **WHEN** 用户在新建或修改环境表单的凭据区域点击测试连接
- **THEN** 系统 SHALL 使用当前表单草稿发起连接测试，而无需先保存环境
- **AND** 系统 SHALL 展示测试结果且不修改已保存的环境配置

#### Scenario: 检查和采集环境

- **WHEN** 用户对环境行发起环境检查或采集环境信息操作
- **THEN** 系统 SHALL 将操作绑定到该环境
- **AND** 操作完成后系统 SHALL 刷新该环境的连接状态或最近采集信息

#### Scenario: 运行环境脚本

- **WHEN** 用户对环境行发起运行脚本操作
- **THEN** 系统 SHALL 在同一个 Drawer 内打开绑定该环境的脚本配置视图
- **AND** 系统 SHALL 支持脚本类型、工作目录、超时时间和脚本内容配置
- **AND** 脚本内容编辑器 SHALL 显示行号
- **AND** 脚本提交后 SHALL 创建可追溯的执行记录

#### Scenario: 编辑环境脚本

- **WHEN** 用户配置待运行的环境脚本
- **THEN** 系统 SHALL 使用支持 Bash 语法高亮和行号的代码编辑器编辑脚本内容
- **AND** 编辑器 SHALL 仅在脚本配置视图打开时加载
- **AND** 编辑器 SHALL 使用 Vite 打包的本地 Monaco 资源和 worker，而不依赖外部 CDN

#### Scenario: 查看环境执行记录

- **WHEN** 用户对环境行发起执行记录操作
- **THEN** 系统 SHALL 展示该环境的脚本执行记录
- **AND** 每条记录 SHALL 展示执行 ID、状态、执行摘要、退出码、日志数量、提交时间、耗时和查看日志操作
- **AND** 执行摘要 SHALL 完整展示，不得仅以省略号或浏览器原生 Tooltip 截断
- **AND** 脚本 SHA-256 SHALL NOT 在执行记录表中展示
- **AND** 退出码 SHALL 以普通文本展示

#### Scenario: 查看完成态环境脚本日志

- **WHEN** 用户查看已完成环境脚本执行记录的日志
- **THEN** 系统 SHALL 使用 `GET /api/tasks/{taskId}/log-content` 读取 `merged`、`stdout` 或 `stderr` 的日志正文
- **AND** 日志详情顶部的执行摘要 SHALL 完整展示，必要时换行
- **AND** 系统 SHALL 支持按日志类型从末尾向上加载更早内容
- **AND** 系统 SHALL 将运行摘要、状态、提交时间、退出码和日志数量以紧凑布局展示
- **AND** 系统 SHALL 仅在存在日志资源时提供受控下载

#### Scenario: 展示环境检查结果

- **WHEN** 用户完成环境检查
- **THEN** 系统 SHALL 展示 SSH、基础工具、工作目录和权限的检查结果或失败原因

#### Scenario: 防止子视图意外关闭

- **WHEN** 用户处于新建、修改、检查、运行脚本或执行记录视图
- **THEN** Drawer SHALL 隐藏右上角关闭按钮
- **AND** Drawer SHALL 不因遮罩点击或键盘关闭而离开当前子视图

#### Scenario: 返回环境列表

- **WHEN** 用户从新建、修改或检查视图点击返回
- **THEN** 系统 SHALL 返回环境列表视图
- **AND** 若存在未保存配置，系统 SHALL 要求用户确认放弃修改

#### Scenario: 进入源码制品管理

- **WHEN** 用户在环境列表 Footer 确认进入源码制品管理
- **THEN** 系统 SHALL 请求阶段推进接口
- **AND** 服务端 SHALL 校验 x86 源环境和 RISC-V 目标环境均存在、连接成功且已完成环境信息采集

#### Scenario: 环境前置条件不满足

- **WHEN** 用户尝试进入源码制品管理但环境前置条件不满足
- **THEN** 系统 SHALL 保持在环境列表视图
- **AND** 系统 SHALL 展示服务端返回的缺失条件或失败原因

#### Scenario: 环境前置条件满足

- **WHEN** 服务端确认环境前置条件满足
- **THEN** 系统 SHALL 使用返回的 workflow 状态更新画布
- **AND** 系统 SHALL 关闭环境管理 Drawer 并聚焦 `assets` 节点

## ADDED Requirements

### Requirement: 源码管理阶段详情

项目流水线工作台 SHALL 在用户点击 `assets` 节点后打开源码管理 Drawer，以“Git / 源码压缩包”说明该节点支持的源码导入方式。

#### Scenario: 展示当前源码

- **WHEN** 源码列表加载成功且存在有效版本
- **THEN** 系统 SHALL 以 `active=true` 识别并展示当前有效源码
- **AND** SHALL 将当前版本、来源、源码包或仓库地址、Git 分支、Commit 和最近更新时间组织为可追溯的信息面板
- **AND** Git 来源的仓库地址 SHALL 作为可跳转链接展示，并显示 Git 分支和 Commit
- **AND** 可能截断的仓库地址、分支和 Commit SHALL 提供组件级悬浮提示

#### Scenario: 未导入源码

- **WHEN** 源码列表中不存在有效版本
- **THEN** 系统 SHALL 使用简洁空状态提示用户选择上传压缩包或从 Git 导入源码
- **AND** SHALL 将导入方式选择置于对应表单之前，并说明导入后的源码会作为后续扫描和构建的当前源码
- **AND** 上传拖拽区域的辅助提示 SHALL 使用次级文本颜色

#### Scenario: 重新打开源码管理

- **WHEN** 用户关闭后重新打开源码管理 Drawer
- **THEN** 系统 SHALL 使用 `active=true` 重新请求当前源码
- **AND** SHALL NOT 展示已关闭 Drawer 保留的旧源码缓存
- **AND** Drawer Header 右侧 SHALL 提供图标形式的刷新操作

### Requirement: 知识库扫描结果展示

知识库扫描结果列表 SHALL 将严重等级统一展示为“风险”，并提供与依赖分析一致的迁移输入入口。

#### Scenario: 固定结果列

- **WHEN** 用户横向滚动知识库扫描结果表
- **THEN** 文件和风险列 SHALL 固定在左侧
- **AND** 行号列 SHALL 随表格横向滚动

#### Scenario: 纳入迁移输入

- **WHEN** 用户查看知识库扫描结果行
- **THEN** 系统 SHALL 在右侧固定操作列提供该结果的迁移输入操作

### Requirement: x86 构建日志展示

x86 构建完成态日志 SHALL 适配 `log-content` 最新页优先的分页语义。

#### Scenario: 初始日志阅读顺序

- **WHEN** 用户首次打开完成态 x86 构建日志
- **THEN** 系统 SHALL 请求 `offset=0`、`lines=100` 的日志页
- **AND** SHALL 将最终日志行显示在 Monaco 编辑器底部
- **AND** 编辑器 SHALL 初始滚动至底部

#### Scenario: 向上加载更旧日志

- **WHEN** 用户滚动至日志顶部且后端返回 `hasMore=true`
- **THEN** 系统 SHALL 请求下一 offset 的更旧日志页
- **AND** SHALL 将其拼接至当前内容顶部并保留当前阅读位置

### Requirement: 依赖分析阶段详情

依赖分析 Drawer SHALL 以依赖分析结果为中心展示后端聚合、映射结果、制品和迁移输入入口。

#### Scenario: 展示依赖分析概览

- **WHEN** 依赖分析完成且存在结果
- **THEN** 系统 SHALL 展示分析依赖总数、风险分布和目标侧匹配分布
- **AND** 风险分布 SHALL 使用与知识库扫描一致的等级计数展示
- **AND** 风险分布与目标侧匹配 SHALL 在宽屏并列展示

#### Scenario: 展示依赖结果列表

- **WHEN** 用户查看依赖分析结果
- **THEN** 系统 SHALL 将依赖和风险列固定在左侧
- **AND** SHALL 映射风险、依赖类型和目标侧匹配状态
- **AND** SHALL NOT 在列表中展示置信度、版本证据或来源位置
- **AND** SHALL 在右侧固定操作列提供迁移输入操作

#### Scenario: 查看依赖结果详情

- **WHEN** 用户点击依赖名称打开详情
- **THEN** 系统 SHALL 打开二级依赖结果详情视图
- **AND** SHALL 提供返回依赖分析的图标入口
- **AND** SHALL 隐藏关闭按钮并禁止通过遮罩关闭 Drawer

### Requirement: 评估报告依赖分析映射

评估报告 SHALL 将依赖分析输入的来源、风险和目标侧匹配状态映射为用户可读文本。

#### Scenario: 展示依赖分析来源与状态

- **WHEN** 评估报告包含 `DEPENDENCY_RESULT` 输入
- **THEN** 系统 SHALL 展示“依赖分析”而非原始来源枚举
- **AND** SHALL 映射依赖分析的目标侧匹配状态和 `COMMENT` 风险等级

### Requirement: 评估报告信息层级

评估报告 SHALL 以报告结论和后续处理优先级为主要阅读路径，避免重复的身份与说明信息占用内容空间。

#### Scenario: 展示报告概览

- **WHEN** 评估报告生成成功
- **THEN** 系统 SHALL 在报告概览展示生成时间、总体风险、纳入报告的问题数、高风险问题数和预计工作量
- **AND** SHALL NOT 单独展示重复的报告身份卡或工作量依据说明卡

#### Scenario: 展示输入构成

- **WHEN** 报告包含纳入输入
- **THEN** 系统 SHALL 并列展示来源构成和风险分布
- **AND** SHALL 将优先处理项和依赖替代提示作为报告的主要后续内容

### Requirement: 人工修复问题处理引导

人工修复 Drawer SHALL 作为评估报告后的问题处理引导页，帮助用户根据问题类型选择依赖修复或源码修复路径。

#### Scenario: 选择依赖问题处理路径

- **WHEN** 用户需要处理缺失依赖、目标侧未安装或版本不兼容问题
- **THEN** 系统 SHALL 提供前往依赖分析的入口
- **AND** SHALL 说明用户可在依赖分析中确认替代包、目标侧匹配情况和迁移输入

#### Scenario: 选择源码问题处理路径

- **WHEN** 用户需要处理知识库扫描发现的源码问题或在线下修改源码
- **THEN** 系统 SHALL 提供前往源码管理的入口
- **AND** SHALL 说明更新后的当前源码版本将用于后续构建

#### Scenario: 修复后验证

- **WHEN** 用户完成依赖或源码修复
- **THEN** 系统 SHALL 提示用户更新当前源码版本并重新执行构建验证
- **AND** SHALL 提供前往构建验证的入口

### Requirement: RISC-V 构建验证信息层级

构建验证 Drawer SHALL 以当前源码在 x86 源环境和 RISC-V 目标环境的准备状态作为主要构建结论，并将环境检查和构建配置组织为后续操作。

#### Scenario: 展示构建就绪结论

- **WHEN** 用户打开构建验证 Drawer
- **THEN** 系统 SHALL 明确展示当前是否可以开始构建
- **AND** SHALL 在未就绪时提示用户完成两个环境的检查和源码准备
- **AND** SHALL 在就绪时说明当前源码已准备到两个运行环境
- **AND** SHALL 将未满足的前置条件及其直达操作放在就绪结论面板内，而非置于环境检查卡之后

#### Scenario: 刷新构建信息

- **WHEN** 用户需要刷新构建验证的前置数据
- **THEN** Drawer Header 右侧 SHALL 提供图标形式的刷新操作

#### Scenario: 查看 RISC-V 构建日志

- **WHEN** 用户从构建记录进入 RISC-V 构建日志详情
- **THEN** 系统 SHALL 提供合并输出、标准输出和标准错误的切换，以及图标形式的刷新操作
- **AND** SHALL 使用 Monaco 按时间正序展示日志，并使最终日志行位于底部
- **AND** SHALL 支持向上加载更早日志并保持当前阅读位置
- **AND** 日志编辑器 SHALL 填满 Drawer 的剩余高度并在编辑器内部纵向滚动

#### Scenario: 展示构建日志摘要

- **WHEN** 用户查看 x86 或 RISC-V 构建日志详情
- **THEN** 系统 SHALL 以横向紧凑摘要展示构建记录 ID、构建状态、退出码和完整执行时间
- **AND** SHALL 将构建目录作为带标签、可查看完整文本的信息项展示

#### Scenario: 收敛构建记录与状态展示

- **WHEN** 用户查看 RISC-V 构建记录列表或 x86、RISC-V 构建日志详情
- **THEN** RISC-V 构建记录列表 SHALL NOT 展示退出码列
- **AND** 详情中的构建状态 SHALL 以内容宽度的语义标签展示，不得填满描述表的信息单元格

### Requirement: 自动化测试信息层级

自动化测试 Drawer SHALL 以当前源码在 x86 和 RISC-V 环境的有效成功构建为前置结论，并将测试执行、结果比较和日志阅读组织为连续的验证路径。

#### Scenario: 展示测试可执行结论

- **WHEN** 用户打开自动化测试 Drawer
- **THEN** 系统 SHALL 明确展示当前是否可以开始自动化测试
- **AND** SHALL 展示两个环境对应的构建可用性与构建目录
- **AND** 前置条件未满足时 SHALL 提供前往构建验证的入口

#### Scenario: 展示测试结果和比较

- **WHEN** 当前源码存在测试批次
- **THEN** 系统 SHALL 并列展示 x86 与 RISC-V 测试的通过、失败和跳过数量
- **AND** SHALL 将比较状态与风险等级映射为中文语义标签

#### Scenario: 查看测试日志

- **WHEN** 用户进入某条测试记录的日志详情
- **THEN** 系统 SHALL 展示测试记录 ID、状态、退出码、执行时间和测试目录的紧凑摘要
- **AND** SHALL 提供合并输出、标准输出和标准错误的切换，以及图标形式的刷新操作
- **AND** SHALL 使用 Monaco 按时间正序展示日志，使最终日志行位于底部
- **AND** SHALL 支持向上加载更早日志并保持当前阅读位置
- **AND** 日志编辑器 SHALL 填满 Drawer 的剩余高度并在编辑器内部纵向滚动

### Requirement: 优化闭环本轮验证结论

优化闭环 Drawer SHALL 以当前源码在 RISC-V 构建验证和自动化测试中的结果作为本轮结论，并提供唯一的下一步操作。

#### Scenario: 展示本轮验证结果

- **WHEN** 当前存在优化轮次
- **THEN** 系统 SHALL 展示当前源码版本、RISC-V 构建和自动化测试的完整结果说明
- **AND** SHALL NOT 将迁移输入、评估报告、源码复检或测试对比作为本轮验证结论的主要内容
- **AND** 历史轮次仅作为辅助列表展示，不得打开内容重复的二级详情页面

#### Scenario: 提供唯一的下一步操作

- **WHEN** 当前 RISC-V 构建未成功
- **THEN** 系统 SHALL 将“前往构建验证”作为唯一主操作

- **WHEN** RISC-V 构建已成功但自动化测试未成功
- **THEN** 系统 SHALL 将“前往自动化测试”作为唯一主操作

- **WHEN** RISC-V 构建和自动化测试均已成功
- **THEN** 系统 SHALL 将“进入归档”作为唯一主操作

#### Scenario: 刷新本轮验证结果

- **WHEN** 用户需要重新获取当前优化轮次
- **THEN** Drawer Header 右侧 SHALL 提供图标形式的刷新操作

### Requirement: 项目归档交付信息

归档 Drawer SHALL 将当前可交付归档作为主要内容，归档历史仅用于追溯，并遵循统一的 Drawer 关闭与返回交互。

#### Scenario: 展示当前归档

- **WHEN** 项目存在最新归档
- **THEN** 系统 SHALL 展示归档名称和可下载归档包的操作
- **AND** SHALL 以紧凑分格展示归档状态、归档记录 ID、源码版本、创建时间、归档包大小和归档内容数量
- **AND** SHALL 将归档历史作为独立辅助列表展示

#### Scenario: 首次创建归档

- **WHEN** 当前源码已就绪但尚不存在归档
- **THEN** 系统 SHALL 在空状态说明下方提供“创建项目归档”操作
- **AND** SHALL NOT 将首次创建操作仅放置在 Drawer Footer

#### Scenario: 刷新和查看归档详情

- **WHEN** 用户停留在归档一级视图
- **THEN** Drawer Header 右侧 SHALL 提供图标形式的刷新操作
- **AND** 系统 SHALL 禁止通过遮罩或 Esc 关闭 Drawer

- **WHEN** 用户打开某条归档详情
- **THEN** 系统 SHALL 在 Header 左侧提供返回归档的图标入口
- **AND** SHALL 隐藏关闭按钮并禁止通过遮罩或 Esc 关闭 Drawer

### Requirement: 当前 MVP 流程节点边界

项目工作台 SHALL 仅保留当前 MVP 已交付或正在优化的流程节点。未具备产品能力或后端契约的节点不得作为占位定义、连线、分组成员或 Drawer 入口保留在前端流程中。

#### Scenario: 渲染当前流程拓扑

- **WHEN** 项目工作台渲染流程画布
- **THEN** 系统 SHALL 仅渲染项目基础配置、环境管理、源码管理、知识库扫描、x86 构建、依赖分析、评估报告、人工修复、构建验证、自动化测试、优化闭环和归档节点
- **AND** SHALL NOT 保留 SBOM、迁移输入合并、构建前确认、源码对比、AI 扫描、内存模型扫描、浮点精度扫描、知识库 AI 扩展、AI Agent 重写、Benchmark、Profiling、对齐与布局优化或 RVV 向量化的节点与连线
