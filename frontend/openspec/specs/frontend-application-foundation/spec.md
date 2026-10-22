# frontend-application-foundation Specification

## Purpose

定义已交付前端的运行工具链、应用入口、会话认证和开发连接方式。请求协议由 request-client 定义，工程质量由相应共享规范定义。

## Requirements

### Requirement: 前端运行与开发入口

前端 SHALL 使用 pnpm、React、TypeScript 和 Vite，并提供 dev、dev:api、build、preview、lint、format、format:check、typecheck 和非 watch test 命令。Vite 与 TypeScript SHALL 将 `@` 解析为 `src`。

#### Scenario: 启动本地开发

- **WHEN** 开发者执行 `pnpm dev` 或 `pnpm dev:api`
- **THEN** Vite SHALL 将 `/api` 转发到 `VITE_API_PROXY_TARGET` 指定的后端，缺省为 `http://127.0.0.1:8080`
- **AND** 页面和领域 API SHALL 使用相同请求边界，开发服务器不注册业务 Mock 路由

### Requirement: 统一应用 Provider 与样式基础

应用 SHALL 通过 Ant Design ConfigProvider、统一反馈桥接、QueryClientProvider 和 RouterProvider 提供中文界面、主题、反馈、查询与路由能力。Ant Design SHALL 是唯一运行时 UI 库，局部样式 SHALL 使用 SCSS Modules。

#### Scenario: 渲染应用

- **WHEN** 浏览器加载应用
- **THEN** 页面 SHALL 获得统一的 Ant Design 主题、中文 locale 和消息反馈
- **AND** 服务端数据 SHALL 由 TanStack Query 管理，认证用户快照 SHALL 由 Zustand 认证 store 管理

### Requirement: Cookie Session 认证与路由守卫

应用 SHALL 通过 `GET /api/auth/me` 校验 Cookie Session，并缓存用户信息。客户端 SHALL NOT 要求或保存 Bearer token；本地用户快照不得替代服务端会话校验。

#### Scenario: 登录成功

- **WHEN** `POST /api/auth/login` 返回用户
- **THEN** 应用 SHALL 保存用户并按 `mustChangePassword` 导向 `/force-change-password` 或 `/home`

#### Scenario: 访问受保护页面

- **WHEN** 用户访问首页、项目页、个人中心或管理中心
- **THEN** 守卫 SHALL 校验会话，未认证时转向 `/login`
- **AND** 60 秒内已校验的会话 MAY 复用，正在进行的会话请求 SHALL 合并
- **AND** 需要强制改密的用户 SHALL 先进入 `/force-change-password`
- **AND** 管理路由 SHALL 额外要求 `isSuperAdmin=true`

#### Scenario: 访问访客页面与根路径

- **WHEN** 已登录用户访问登录、忘记密码、重置密码或接受邀请页面
- **THEN** 守卫 SHALL 按改密状态导向 `/force-change-password` 或 `/home`
- **AND** 根路径 `/` SHALL 导向 `/home`

### Requirement: 记住账号与安全退出

登录页 SHALL 提供账号、密码和记住账号选项。记住账号 SHALL 仅保存账号字符串，不保存密码或延长服务端会话。退出 SHALL 调用受 CSRF 保护的登出接口。

#### Scenario: 记住或取消记住账号

- **WHEN** 用户勾选记住账号并成功登录
- **THEN** 下次打开登录页 SHALL 回填账号和勾选状态
- **WHEN** 用户取消该选项或未勾选时成功登录
- **THEN** 应用 SHALL 删除已保存账号

#### Scenario: 用户主动退出

- **WHEN** `POST /api/auth/logout` 返回 `loggedOut=true`
- **THEN** 应用 SHALL 清除认证用户并替换当前路由为 `/login`
- **WHEN** 登出请求失败或未确认退出
- **THEN** 应用 SHALL 展示失败反馈，不将未完成请求显示为成功

### Requirement: 强制改密码与邀请激活

应用 SHALL 为必须改密的已登录用户提供 `/force-change-password`，为邀请接收者提供 `/accept-invitation`。表单 SHALL 校验必填字段、密码规则和确认密码。

#### Scenario: 强制改密完成

- **WHEN** 用户提交有效的当前密码和新密码且修改成功
- **THEN** 应用 SHALL 调用登出接口、清除认证状态并转向 `/login`

#### Scenario: 接受邀请

- **WHEN** 用户通过带 token 的邀请链接设置有效密码
- **THEN** 应用 SHALL 调用邀请接受接口，成功后提示登录
- **AND** 缺少 token 时 SHALL 展示链接无效状态，不提交激活请求
- **AND** 有效 token SHALL 读取到页面内存后从地址栏移除，不写入浏览器持久化存储

### Requirement: 提交事务从异步校验前归属于会话

前端 SHALL 在异步表单校验前捕获认证、项目及编辑会话归属并取得提交锁，每个异步阶段后 SHALL 检查归属；旧校验 SHALL NOT 在新身份下发起写请求，旧提交完成 SHALL NOT 关闭、重置或反馈到新编辑会话。

#### Scenario: 校验期间切换身份或项目

- **WHEN** 项目描述或知识库扫描表单正在异步校验，用户切换身份、项目、关闭或离开所属编辑视图
- **THEN** 校验完成 SHALL NOT 发起旧草稿的提交请求
- **AND** 校验期间重复提交 SHALL 被同步拦截，失败 SHALL 保留草稿并解锁

### Requirement: 项目事件流按认证生命周期隔离

项目 SSE 的连接、事件处理、重连和延迟刷新 SHALL 归属于认证 generation 与项目生命周期，认证改变时 SHALL 立即关闭旧连接并清理定时器。

#### Scenario: 旧账号事件或重连迟到

- **WHEN** 认证身份已改变，旧事件处理回调、刷新 timer 或重连回调随后执行
- **THEN** 旧回调 SHALL NOT 通知、失效新会话查询或重新建立旧会话连接
- **AND** 新连接 SHALL 保留既有 cursor、批量刷新及终态刷新规则

### Requirement: 认证会话私有数据隔离

应用 SHALL 在确认退出、认证身份改变或会话失效后隔离原会话的私有数据及异步结果，不向新身份展示或写入旧身份的缓存。隔离 SHALL 由统一认证边界负责，不替代后端访问控制。

#### Scenario: 同一页面生命周期切换账号

- **WHEN** 账号 A 已读取私有项目数据，确认退出后账号 B 登录并进入相同筛选条件的列表
- **THEN** 页面 SHALL NOT 展示 A 的缓存数据
- **AND** B 的内容 SHALL 来自 B 所属会话的数据读取，不受旧缓存新鲜时间影响

#### Scenario: 旧会话异步结果迟到

- **WHEN** 原账号的查询或提交结果在退出或身份改变后返回
- **THEN** 该结果 SHALL NOT 更新新账号的私有缓存、编辑会话或用户可见完成反馈

#### Scenario: 其他退出与恢复入口

- **WHEN** 强制改密后确认退出，或会话失效后重新登录为不同身份
- **THEN** 应用 SHALL 执行相同私有数据隔离
- **AND** 退出失败时 SHALL 保留现有认证状态并显示失败，记住账号 SHALL 仍只保存账号字符串

#### Scenario: 旧认证校验成功或失败迟到

- **WHEN** 原会话认证刷新或校验尚未完成，用户已退出或登录为新身份，随后旧校验成功或失败
- **THEN** 旧成功 SHALL NOT 覆盖新身份，旧失败 SHALL NOT 清除新登录、触发新会话错误反馈或重定向
- **AND** 旧 Promise 的清理 SHALL NOT 释放新会话的校验锁，路由 guard SHALL NOT 因旧校验失败而退出新会话
- **AND** 同一有效会话 SHALL 保留既有在途校验去重与 TTL 行为

### Requirement: 写操作与读取归属当前身份

前端的业务写操作 SHALL 在提交入口锁定当前身份及视图生命周期；异步结果仅能更新所属会话。需要完整候选集的聚合读取 SHALL 读取全部服务端分页，并在认证变化或请求取消后停止接纳结果。

#### Scenario: 旧写操作在新身份中完成

- **WHEN** 用户在公开认证表单、管理中心或项目阶段发起写操作后切换身份或离开所属视图
- **THEN** 旧请求结果 SHALL NOT 关闭新视图、覆盖私有缓存或显示新会话成功反馈
- **AND** 同一所属视图的提交中重复操作 SHALL 被阻止

#### Scenario: 候选集跨越多个服务端分页

- **WHEN** 下拉选项或聚合报告所需记录超过单页容量
- **THEN** 前端 SHALL 读取并合并全部服务端分页；可见表格 SHALL 继续使用服务端分页
- **AND** 取消或身份改变后的迟到分页 SHALL NOT 回写当前视图

### Requirement: 认证检查按错误语义恢复

受保护路由与请求客户端 SHALL 仅在明确的认证失效响应清理当前会话。非认证错误 SHALL 保留当前身份，并提供当前页面可恢复的失败反馈。

#### Scenario: 会话检查网络失败

- **WHEN** 已登录用户的会话检查因网络故障失败，而未收到明确 401
- **THEN** 前端 SHALL 保留现有认证身份并呈现错误恢复入口
- **AND** 普通 403 或网关错误 SHALL NOT 强制导航到登录页

#### Scenario: 主动取消读取

- **WHEN** 页面主动取消一个在途读取请求
- **THEN** 请求 SHALL 保留取消结果，SHALL NOT 显示网络失败提示或改变认证身份

### Requirement: 浏览器缓存失败不阻断当前会话登录

认证身份缓存及记住账号 SHALL 作为可失败的本地缓存；浏览器存储不可用时，前端 SHALL 继续使用当前内存身份。

#### Scenario: 存储权限或容量异常

- **WHEN** 记住账号或认证缓存的读取、写入、删除抛出异常，而登录接口成功
- **THEN** 页面 SHALL 更新内存身份并继续既定导航，SHALL NOT 因缓存异常阻断登录
