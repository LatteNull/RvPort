## MODIFIED Requirements

### Requirement: 项目流水线工作台内容

项目流水线工作台页面 SHALL 汇总当前迁移项目状态并渲染迁移流程，但 MUST NOT 在页面渲染时自动执行流水线任务。

#### Scenario: 项目流水线工作台渲染摘要

- **WHEN** 项目概览数据加载成功
- **THEN** 页面 SHALL 展示项目标识、架构迁移方向、总体风险、问题数量、当前阶段和构建状态摘要卡片

#### Scenario: 项目流水线工作台渲染流程画布

- **WHEN** 项目概览数据加载成功
- **THEN** 页面 SHALL 渲染 React Flow 流水线画布，包含前端固定维护的迁移阶段节点、分组框和连接边
- **AND** SHALL 将 `env` 和 `assets` 放入“源数据管理”分组，将 `sbom` 放入“环境扫描”分组，将 `kb` 放入“源码扫描”分组
- **AND** SHALL 将 `assets` 展示为“源码管理”，将 `sbom` 展示为“环境与依赖对比”

#### Scenario: 展示源数据与扫描依赖边

- **WHEN** 页面渲染当前主流程
- **THEN** 画布 SHALL 使用具体节点 edge 表示 `project -> env`、`project -> assets`、`env -> sbom`、`assets -> kb`、`sbom -> merge`、`kb -> merge`、`merge -> report`、`report -> manual` 和 `manual -> assets`
- **AND** SHALL NOT 将业务 edge 连接到分组边界

#### Scenario: Workflow 状态映射到固定拓扑

- **WHEN** Workflow 状态快照加载成功
- **THEN** 页面 SHALL 将后端返回的阶段状态、当前阶段摘要、运行中边和可选焦点映射到前端固定维护的节点、分组和边上
- **AND** 页面 SHALL NOT 要求后端返回 React Flow 节点、分组、边或布局坐标

#### Scenario: 环境与依赖对比阶段状态

- **WHEN** workflow 状态快照包含 `sbom` 任务状态
- **THEN** 页面 SHALL 将其映射到前端固定的“环境与依赖对比”节点
- **AND** 该任务的执行、完成或失败 SHALL 以服务端返回状态为事实来源

#### Scenario: 用户操作流水线画布

- **WHEN** 用户平移或缩放流水线画布
- **THEN** 画布 SHALL 支持 React Flow 的平移和缩放行为，且不改变服务端拥有的项目状态

#### Scenario: 扫描任务不自动启动

- **WHEN** 用户完成环境配置或更新当前源码
- **THEN** 页面 SHALL NOT 自动启动环境与依赖对比、知识库扫描、迁移输入合并或评估报告任务
- **AND** SHALL 仅根据服务端返回的 workflow 状态更新对应节点状态

#### Scenario: 聚焦扫描分组

- **WHEN** workflow 状态快照指定 `focusGroupId=environment-scan` 或 `focusGroupId=source-scan`
- **THEN** 画布 SHALL 在初始化或状态切换时将对应分组置于视觉中心
- **AND** 页面 SHALL NOT 为并行支路任意选择单一节点作为唯一当前阶段

#### Scenario: 流水线节点不可拖拽编排

- **WHEN** 用户查看项目流水线工作台
- **THEN** 页面 SHALL 禁止拖拽节点改变 workflow 布局或流程结构

#### Scenario: 初始化聚焦当前阶段

- **WHEN** Workflow 状态快照包含当前阶段且不包含分组焦点
- **THEN** 画布 SHALL 在初始化或状态切换时将当前阶段置于视觉中心
- **AND** 画布 SHALL NOT 以展示完整 workflow 为初始化目标

#### Scenario: 用户悬浮流水线节点

- **WHEN** 用户将鼠标悬浮在流水线节点上
- **THEN** 页面 SHALL 通过样式联动展示该节点直接相连的 source/target edges
- **AND** 页面 SHALL NOT 通过每次悬浮修改 React Flow edges 数组来实现该效果

#### Scenario: 项目流水线工作台不建立实时连接

- **WHEN** 本 change 中的项目流水线工作台页面渲染
- **THEN** 页面 SHALL NOT 建立项目级 SSE 连接

#### Scenario: 项目流水线工作台不自动执行任务

- **WHEN** 用户查看项目流水线工作台页面且未确认阶段操作
- **THEN** 页面 SHALL NOT 启动扫描、环境与依赖对比、报告、构建、测试、归档或其他长任务

#### Scenario: 已确认的阶段操作启动任务

- **WHEN** 用户在阶段 Drawer 中确认启动环境与依赖对比或知识库扫描
- **THEN** 页面 SHALL 通过阶段 API 请求服务端启动对应任务
- **AND** 页面 SHALL 仅根据服务端返回的 workflow 状态更新画布

### Requirement: 环境管理阶段详情

项目流水线工作台 SHALL 在用户点击 `env` 节点后打开专属环境管理 Drawer，并加载当前项目的远程环境资源。

#### Scenario: 请求环境列表

- **WHEN** 用户点击 Workflow 中的 `env` 节点
- **THEN** 系统 SHALL 使用当前 `projectId` 请求项目环境列表

#### Scenario: 展示项目级分析环境

- **WHEN** 用户打开环境管理 Drawer
- **THEN** 系统 SHALL 使用当前 `projectId` 读取项目级运行环境配置
- **AND** SHALL 在环境列表中展示当前 x86 源环境与 RISC-V 目标环境的配置状态

#### Scenario: 配置项目级分析环境

- **WHEN** 用户在环境管理中发起配置分析环境
- **THEN** 系统 SHALL 在同一 Drawer 内选择启用的 x86 源环境和 RISC-V 目标环境
- **AND** 保存后 SHALL 更新项目级运行环境配置并刷新共享读取缓存

#### Scenario: 展示环境列表

- **WHEN** 环境列表加载成功
- **THEN** Drawer SHALL 展示名称、角色、架构、OS、主机、连接状态、最近采集时间和行级操作

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
- **AND** 脚本提交后 SHALL 创建可追溯的执行记录

#### Scenario: 编辑环境脚本

- **WHEN** 用户配置待运行的环境脚本
- **THEN** 系统 SHALL 使用支持 Bash 语法高亮和行号的代码编辑器编辑脚本内容
- **AND** 编辑器 SHALL 仅在脚本配置视图打开时加载
- **AND** 编辑器 SHALL 使用 Vite 打包的本地 Monaco 资源和 worker，而不依赖外部 CDN

#### Scenario: 查看环境执行记录

- **WHEN** 用户对环境行发起执行记录操作
- **THEN** 系统 SHALL 展示该环境的脚本执行记录
- **AND** 每条记录 SHALL 展示脚本、执行人、开始时间、耗时、退出码和状态
- **AND** 用户 SHALL 能查看记录的标准输出、标准错误和退出码
- **AND** 标准输出和标准错误 SHALL 使用只读代码视图展示

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
