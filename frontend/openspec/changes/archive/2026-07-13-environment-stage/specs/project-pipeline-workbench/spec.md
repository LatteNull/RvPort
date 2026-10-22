## ADDED Requirements

### Requirement: 环境管理阶段详情

项目流水线工作台 SHALL 在用户点击 `env` 节点后打开专属环境管理 Drawer，并加载当前项目的远程环境资源。

#### Scenario: 请求环境列表

- **WHEN** 用户点击 Workflow 中的 `env` 节点
- **THEN** 系统 SHALL 使用当前 `projectId` 请求项目环境列表接口

#### Scenario: 展示环境列表

- **WHEN** 环境列表加载成功
- **THEN** Drawer SHALL 展示名称、角色、架构、OS、主机、连接状态、最近采集时间和行级操作
- **AND** Drawer SHALL NOT 额外展示重复 x86 源环境或 RISC-V 目标环境状态的环境接入摘要

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
