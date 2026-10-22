## Why

前端当前只有单一生产 Dockerfile，静态 Nginx 镜像无法使用 Vite mock，且 API 上游被写死。需要区分开发/mock 演示容器与可多环境复用的生产容器。

## What Changes

- 建立 `deploy/docker/` 与 `deploy/nginx/` 前端部署资产目录。
- 提供 Vite mock 开发容器，以及可由测试、生产环境复用的 Nginx 镜像。
- 将 Compose 内的 API 上游统一为 `http://backend:8080`，保留 Nginx 运行时配置边界以供后续环境演进。
- 为生产前端添加 Compose service、Docker ignore、健康检查和部署说明。

## Capabilities

### New Capabilities

- `frontend-container-deployment`: 前端开发/mock 与生产容器的构建、启动和多环境配置能力。

### Modified Capabilities

无。

## Impact

- `frontend/deploy/`、`frontend/.dockerignore`、根 `docker-compose.yml`。
- 不改动前端业务代码、Vite mock 或后端服务实现。
