#!/usr/bin/env bash

# @Description: build to static resources using Docker
# @Create Date: 2025/01/19

# Started by AICoder, pid:02dc032640a1bfa14f6a09b160e7b72e7c29c971
set -euo pipefail

node_docker_image="${NODE_DOCKER_IMAGE:-node:20.8.0-alpine3.18}"

check_docker() {
    # 检查docker是否安装
    if ! command -v docker &>/dev/null; then
        echo "Docker is not installed"
        return 1
    fi

    # 检查docker是否可用（通过运行一个简单的命令测试）
    if ! docker info &>/dev/null; then
        echo "Docker is installed but not accessible"
        return 1
    fi

    echo "Docker is available and ready to use"
    return 0
}

# 获取脚本所在目录的绝对路径
SCRIPT_PATH=$(cd "$(dirname "$0")" && pwd)
PROJECT_PATH=$(cd "${SCRIPT_PATH}"/../ && pwd)

# 删除 dist 目录（如果存在）
if [ -d ${SCRIPT_PATH}/dist ]; then
    echo "删除 dist 目录"
    rm -rf ${SCRIPT_PATH}/dist
fi

if check_docker; then
    # Started by AICoder, pid:l1da8w67b2z2a61142e808b140adc103ef178231
    echo "开始使用 Docker 进行 npm run build"
    docker run --rm \
        -u $(id -u):$(id -g) \
        -v "${SCRIPT_PATH}:/app" \
        -w /app \
        ${node_docker_image} \
        sh -c "npm install --legacy-peer-deps && npm run build"
    # Ended by AICoder, pid:l1da8w67b2z2a61142e808b140adc103ef178231
else
    echo "docker不可用，请安装docker，参考链接https://docs.docker.com/engine/install/"
    exit 1
fi
echo "npm run build 完成"

# 删除目标目录（如果存在）
if [ -d ${PROJECT_PATH}/server/static ]; then
    echo "开始删除目标目录"
    rm -rf ${PROJECT_PATH}/server/static
fi

# 确保目标目录存在
mkdir -p ${PROJECT_PATH}/server/static

echo "开始复制静态资源"
cp -r ${SCRIPT_PATH}/dist/frontend/browser/* ${PROJECT_PATH}/server/static/
echo "复制完成"
# Ended by AICoder, pid:02dc032640a1bfa14f6a09b160e7b72e7c29c971
