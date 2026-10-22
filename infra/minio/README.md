# Building the object-storage image

English | [简体中文](README.zh-CN.md)

The MinIO Community distribution uses [source distribution](https://github.com/minio/minio#source-only-distribution), and the previously used official image cannot be pulled anonymously. This project builds official `RELEASE.2025-10-15T17-29-55Z` source inside Docker, at commit `9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a`. The archive SHA-256 is pinned in the Dockerfile; dependencies use upstream `go.mod` and `go.sum`.

Run the complete `docker compose build` from the repository root as described in the installation guide. MinIO source is unmodified. Upstream `LICENSE` and `NOTICE` are retained in `/usr/share/licenses/minio/` inside the image. MinIO's AGPL-3.0 license remains separate and cannot be replaced by this project's license.

Runtime configuration uses `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_API_PORT`, and `MINIO_CONSOLE_PORT`. Store credentials only in the local `.env`, which must not be committed. Validate service health and backend artifact access together through Compose startup.

The official community repository is archived. Pinning this source makes the current build reproducible; future maintenance or replacement of object storage requires separate planning. Unverified third-party images are not default dependencies.
