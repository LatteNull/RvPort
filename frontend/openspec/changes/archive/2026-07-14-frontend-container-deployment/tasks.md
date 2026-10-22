## 1. 部署资产

- [x] 1.1 创建前端 Docker ignore 与 `deploy/docker/`、`deploy/nginx/` 目录
- [x] 1.2 创建生产 Dockerfile 与 API 上游 Nginx 模板
- [x] 1.3 创建 Vite mock 开发 Dockerfile
- [x] 1.4 将部署说明合并到前端 README
- [x] 1.5 提供安全的前端构建产物与依赖缓存清理脚本

## 2. 生产启动与验证

- [x] 2.1 在根 Compose 中添加测试/生产可复用的 frontend service，并通过 `API_UPSTREAM` 配置上游
- [ ] 2.2 构建生产和开发镜像，并验证生产静态服务与开发 mock 服务可启动
- [ ] 2.3 运行 `pnpm format:check`、`pnpm lint`、`pnpm typecheck`、`pnpm test` 与严格 OpenSpec 校验
