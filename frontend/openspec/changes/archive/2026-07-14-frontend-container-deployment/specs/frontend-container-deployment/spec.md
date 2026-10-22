## ADDED Requirements

### Requirement: 前端容器运行模式

前端 SHALL 提供 Vite mock 开发容器和 Compose 生产容器。开发容器 SHALL 运行 Vite dev server 并保留 Vite mock；生产容器 SHALL 使用静态 Nginx 镜像并通过 Compose 服务网络访问真实 API。

#### Scenario: 启动开发 mock 容器

- **WHEN** 开发者使用 `Dockerfile.dev` 构建并运行容器
- **THEN** Vite SHALL 监听容器外可访问地址，且 `/api/*` 请求 SHALL 由现有 Vite mock 处理

#### Scenario: 启动生产容器

- **WHEN** 部署者使用生产 Dockerfile 构建并运行容器
- **THEN** 容器 SHALL 使用 Nginx 服务 `dist`，且 SHALL NOT 包含 Vite mock 服务

### Requirement: 生产 API 上游配置

生产 Nginx SHALL 通过 `API_UPSTREAM` 代理 `/api/`。根 Compose frontend service SHALL 将其设置为内部服务地址 `http://backend:8080`，使前端通过 Compose 服务 DNS 访问后端。

#### Scenario: 生产前端访问内部后端服务

- **WHEN** 完整项目 Compose 启动 frontend 和 backend 服务
- **THEN** frontend SHALL 将 `/api/` 请求代理至 `http://backend:8080`
