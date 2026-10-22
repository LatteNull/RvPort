# 对象存储镜像构建

[English](README.md) | 简体中文

MinIO 社区版当前采用[源码分发](https://github.com/minio/minio#source-only-distribution)，原先使用的官方镜像无法匿名拉取。本项目在 Docker 内构建官方 `RELEASE.2025-10-15T17-29-55Z`，对应提交 `9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a`；下载归档的 SHA-256 固定在 Dockerfile 中，依赖使用上游 `go.mod`、`go.sum`。

在项目根目录按安装指南执行完整 `docker compose build` 即可构建。没有修改 MinIO 源码；上游 `LICENSE`、`NOTICE` 随镜像保留在 `/usr/share/licenses/minio/`。MinIO 的 AGPL-3.0 许可独立保留，不能用本项目许可证替代。

运行配置继续使用 `MINIO_ROOT_USER`、`MINIO_ROOT_PASSWORD`、`MINIO_API_PORT`、`MINIO_CONSOLE_PORT`。凭据只写入本地 `.env`，不得提交。服务健康检查与后端制品存取仍须通过 Compose 联合启动验证。

官方社区仓库已归档；此处固定源码仅解决当前基线的构建可复现性。后续对象存储维护或更换应另行规划，不将未经验证的第三方镜像作为默认依赖。
