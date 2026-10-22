## Why

V1 前端需要在 `5173` 开发服务器上逐步接入本地 Docker 中的真实后端，但后端模块并非同时完成。当前开发模式会统一启用 Mock，且没有将未命中 Mock 的 `/api` 请求代理到本地后端，无法让已完成接口和未完成接口并存联调。

联调发现也需要形成可直接交给后端处理的事实记录，而不是散落在浏览器网络面板或临时沟通中。

## What Changes

- 为 Vite 开发服务器提供到本地后端的同源 `/api` 代理能力。
- 提供明确的两种开发模式：`dev:api` 全量请求本地后端，`dev:mock` 全量使用现有 Mock；前端业务组件不感知分流。
- 将根目录 Markdown 联调文档作为联调唯一记录源，记录实际请求、回参、追踪信息、字段缺口和面向后端的待修改项。
- 定义“已通”状态仅在真实页面调用与页面行为均验证成功后使用。
- 为后端返回 `mustChangePassword` 的首次登录用户提供前端强制改密入口，并避免先进入业务页再触发拒绝。

## Capabilities

### New Capabilities

- `incremental-api-integration`: 在 Vite 开发服务器中按启动模式将请求发送到真实本地后端或现有 Mock，并保持 Cookie、CSRF 和既有 `/api` 调用约定。
- `integration-feedback-record`: 以根目录 Markdown 文档记录前后端联调证据、问题、字段缺口与可交付给后端的修改清单。

### Modified Capabilities

无。

## Impact

- 影响 `frontend/vite.config.ts`、Mock 注册方式和开发环境变量/启动方式。
- 不改变页面组件调用 API 的方式，也不改变生产容器 `8081` 的 Nginx 代理链路。
- 根目录联调 Markdown 文档将成为模块化联调的记录与后端协作入口。
- 本地 Docker 后端继续暴露在 `http://localhost:8080`；前端开发服务器继续运行在 `http://localhost:5173`。
