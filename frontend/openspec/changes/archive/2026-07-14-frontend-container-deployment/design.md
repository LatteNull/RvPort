## Context

生产镜像由 Nginx 服务静态 `dist`，Vite mock 只在 dev server 生效。当前整个项目以 Docker Compose 部署，生产前端通过 Compose 内置 DNS 访问 `backend` 服务；部署资产需要按 Docker 与 Nginx 的职责分层，并保留后续环境演进边界。

## Goals / Non-Goals

**Goals:** 提供 `Dockerfile.dev` 的 Vite mock 容器、生产 Nginx 镜像与使用内部 `backend` 服务的 Compose frontend service。

**Non-Goals:** 不编排后端服务；不将 mock 引入生产镜像；不维护多份环境专用 Nginx 配置。

## Decisions

- `deploy/docker/` 存放 Dockerfile，`deploy/nginx/default.conf.template` 存放可复用 Nginx 模板。
- 生产镜像使用官方 Nginx `/etc/nginx/templates/` 的启动时 `envsubst`；当前 Compose 将 `API_UPSTREAM` 固定为内部服务 `http://backend:8080`。
- 开发环境使用 `Dockerfile.dev` 启动 `pnpm dev --host 0.0.0.0`，因此现有 Vite mock 自动生效。
- 当前 Compose 只提供内部服务上游的生产 frontend；测试与多环境覆盖文件在实际环境需求明确后再添加。
- Compose 只提供 Nginx `frontend` service；开发/mock 容器由独立 Docker 命令运行。

## Risks / Trade-offs

- [Compose 未定义 backend 服务] → frontend 无法代理 API；完整项目 Compose 必须定义该服务后再启动 frontend。
- [静态构建上下文过大] → `.dockerignore` 排除依赖缓存、构建产物与本地文件。
