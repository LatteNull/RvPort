ARG GO_IMAGE=golang:1.24.8-alpine
ARG ALPINE_IMAGE=alpine:3.22
FROM ${GO_IMAGE} AS build

ENV CGO_ENABLED=0 GOMAXPROCS=2 GOTOOLCHAIN=local
WORKDIR /src
# 官方 RELEASE.2025-10-15T17-29-55Z 对应提交；不依赖已不可拉取的旧官方镜像。
ADD --checksum=sha256:45521908307306e925c98d629e1c17d78c8b72b6ee242b1bfb1409f7d8ee5841 \
    https://codeload.github.com/minio/minio/tar.gz/9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a /tmp/minio.tar.gz
RUN tar -xzf /tmp/minio.tar.gz --strip-components=1 -C /src && rm /tmp/minio.tar.gz
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    go build -p 2 -trimpath -ldflags='-s -w' -o /out/minio .

FROM ${ALPINE_IMAGE}
RUN apk add --no-cache ca-certificates curl
COPY --from=build /out/minio /usr/local/bin/minio
COPY --from=build /src/LICENSE /src/NOTICE /usr/share/licenses/minio/
LABEL org.opencontainers.image.source="https://github.com/minio/minio" \
      org.opencontainers.image.revision="9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a" \
      org.opencontainers.image.licenses="AGPL-3.0-only" \
      org.opencontainers.image.version="RELEASE.2025-10-15T17-29-55Z"
RUN minio --version
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
