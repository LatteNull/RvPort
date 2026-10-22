## Purpose

定义 RvPort 前端在 Vite API 代理开发容器与 Nginx 生产容器中的构建、运行、服务发现和 API 上游配置要求，确保两种运行模式具有清晰且可验证的边界。

## Requirements

### Requirement: 前端容器运行模式

前端 SHALL 提供 Vite API 代理开发容器和 Compose 生产容器。开发容器 SHALL 运行 Vite dev server 并通过 API 代理连接真实后端；生产容器 SHALL 使用静态 Nginx 镜像并通过 Compose 服务网络访问真实 API。

#### Scenario: 启动开发容器

- **WHEN** 开发者使用 `Dockerfile.dev` 构建并运行容器
- **THEN** Vite SHALL 监听容器外可访问地址，且 `/api/*` 请求 SHALL 转发至容器可访问的 `VITE_API_PROXY_TARGET` 后端地址

#### Scenario: 启动生产容器

- **WHEN** 部署者使用生产 Dockerfile 构建并运行容器
- **THEN** 容器 SHALL 使用 Nginx 服务 `dist`，且 SHALL NOT 包含 Vite mock 服务

### Requirement: 生产 API 上游配置

生产 Nginx SHALL 通过 `API_UPSTREAM` 代理 `/api/`，并使用 Docker DNS 动态解析上游服务地址。根 Compose frontend service SHALL 将其设置为内部服务地址 `http://backend:8080`，且 SHALL 等待 backend 健康后再启动，避免首次解析竞态和容器重建后的陈旧地址。

#### Scenario: 生产前端访问内部后端服务

- **WHEN** 完整项目 Compose 启动 frontend 和 backend 服务
- **THEN** frontend SHALL 将 `/api/` 请求代理至 `http://backend:8080`

#### Scenario: 后端尚未健康

- **WHEN** Compose 启动时 backend 尚未通过健康检查
- **THEN** frontend SHALL 等待 backend 健康后再启动 Nginx

#### Scenario: 后端容器地址发生变化

- **WHEN** backend 容器重建并获得新的 Compose 网络地址
- **THEN** Nginx SHALL 通过 Docker DNS 重新解析 backend，且 `/api/` 请求 SHALL NOT 继续访问旧地址
