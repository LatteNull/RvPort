#!/bin/bash
set -e  # 遇错立即退出
readonly SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
readonly ARCH_DIR=$(cd "$(dirname "$0")/${1:-x86}" && pwd)
# 可选环境变量（内网用户覆盖公网默认值用）：
#   BASE_IMAGE / APT_URI      —— 基础镜像与 apt 源
#   CURSOR_CLI_URL             —— cursor CLI 下载地址（默认官方）
#   ART_API_KEY                —— 下载源需要鉴权时设置（curl -H 使用）；不再硬编码
# 资源获取统一优先级：thirdapp/ 本地文件 > 环境变量 URL > 公网默认
BASE_IMAGE="${BASE_IMAGE:-}"
APT_URI="${APT_URI:-}"
CURSOR_CLI_URL="${CURSOR_CLI_URL:-}"
ART_API_KEY="${ART_API_KEY:-}"
# 架构配置函数
get_arch_config() {
    local arch=$1
    local key=$2
    
    case "$arch" in
        arm)
            case "$key" in
                BASE_IMAGE) echo "${BASE_IMAGE:-arm64v8/ubuntu:24.04}" ;;
                APT_URI) echo "${APT_URI:-http://ports.ubuntu.com/ubuntu-ports/}" ;;
                NODE_URL) echo "https://nodejs.org/dist/v26.7.0/node-v26.7.0-linux-arm64.tar.xz" ;;
                NODE_FILE) echo "node-aarch64.tar.xz" ;;
                QEMU_URL) echo "https://github.com/tonistiigi/binfmt/releases/download/deploy%2Fv10.0.4-56/qemu_v10.0.4_linux-arm64.tar.gz" ;;
                QEMU_FILE) echo "qemu_v10.0.4_linux-arm64.tar.gz" ;;
                TAR_SUFFIX) echo "_arm.tar" ;;
                CROSS_COMPILER) echo "gcc-14-riscv64-linux-gnu,g++-14-riscv64-linux-gnu,gcc-x86-64-linux-gnu,g++-x86-64-linux-gnu,binutils-x86-64-linux-gnu" ;;
                CURSOR_CLI_URL) echo "${CURSOR_CLI_URL:-}" ;;
                CURSOR_CLI_FILE) echo "cursor_cli.tar"
            esac
            ;;
        x86)
            case "$key" in
                BASE_IMAGE) echo "${BASE_IMAGE:-ubuntu:24.04}" ;;
                APT_URI) echo "${APT_URI:-http://archive.ubuntu.com/ubuntu/}" ;;
                NODE_URL) echo "https://nodejs.org/dist/v26.7.0/node-v26.7.0-linux-x64.tar.xz" ;;
                NODE_FILE) echo "node-x86_64.tar.xz" ;;
                QEMU_URL) echo "https://github.com/tonistiigi/binfmt/releases/download/deploy%2Fv10.0.4-56/qemu_v10.0.4_linux-amd64.tar.gz" ;;
                QEMU_FILE) echo "qemu_v10.0.4_linux-amd64.tar.gz" ;;
                TAR_SUFFIX) echo "_x86.tar" ;;
                CROSS_COMPILER) echo "gcc-14-riscv64-linux-gnu,g++-14-riscv64-linux-gnu,gcc-aarch64-linux-gnu,g++-aarch64-linux-gnu,binutils-aarch64-linux-gnu" ;;

                CURSOR_CLI_FILE) echo "cursor_cli.tar"
            esac
            ;;
        *)
            return 1
            ;;
    esac
}
# 解析架构参数
ARCH=${1:-x86}
if ! get_arch_config "$ARCH" BASE_IMAGE > /dev/null 2>&1; then
    echo "错误: 不支持的架构 '$ARCH'。支持: arm, x86"
    exit 1
fi
# 加载架构配置到变量
RESOLVED_BASE_IMAGE=$(get_arch_config "$ARCH" BASE_IMAGE)
APT_URI=$(get_arch_config "$ARCH" APT_URI)
NODE_URL=$(get_arch_config "$ARCH" NODE_URL)
NODE_FILE=$(get_arch_config "$ARCH" NODE_FILE)
QEMU_URL=$(get_arch_config "$ARCH" QEMU_URL)
QEMU_FILE=$(get_arch_config "$ARCH" QEMU_FILE)
TAR_SUFFIX=$(get_arch_config "$ARCH" TAR_SUFFIX)
DEFAULT_CROSS_COMPILER=$(get_arch_config "$ARCH" CROSS_COMPILER)
CURSOR_CLI_FILE=$(get_arch_config "$ARCH" CURSOR_CLI_FILE)
CURSOR_CLI_URL=$(get_arch_config "$ARCH" CURSOR_CLI_URL)

IMAGE_NAME="codemig-agent-base:1.0.0"
# 颜色输出函数
log_info() {
    echo -e "\033[0;32m[INFO]\033[0m $1"
}
log_warn() {
    echo -e "\033[0;33m[WARN]\033[0m $1"
}
log_error() {
    echo -e "\033[0;31m[ERROR]\033[0m $1"
}
# 准备构建文件
prepare_build_files() {
    log_info "准备构建文件..."
    
    # 下载 node 文件
    if [ ! -f "$ARCH_DIR/node.tar.xz" ]; then
        log_info "下载 node: ${NODE_URL}"
        wget -O "$ARCH_DIR/${NODE_FILE}" "${NODE_URL}"
        mv "$ARCH_DIR/${NODE_FILE}" "$ARCH_DIR/node.tar.xz"
    fi
    
    # 复制 offline 文件
    local offline_source="${SCRIPT_DIR}/thirdapp/offline.tar.gz"
    if [ ! -f "$offline_source" ]; then
        log_error "未找到offline文件: $offline_source"
        exit 1
    fi
    cp "$offline_source" "$ARCH_DIR/offline.tar.gz"
    tar -xzvf "$ARCH_DIR/offline.tar.gz" -C "$ARCH_DIR"
    rm -rf "$ARCH_DIR/offline.tar.gz"
   
    # 复制 pipi 文件
    local pipi_source="${SCRIPT_DIR}/thirdapp/pipi.tar.gz"
    if [ ! -f "$pipi_source" ]; then
        log_error "未找到pipi文件: $pipi_source"
        exit 1
    fi
    cp "$pipi_source" "$ARCH_DIR/pipi.tar.gz"
    tar -xzvf "$ARCH_DIR/pipi.tar.gz" -C "$ARCH_DIR"
    rm -rf "$ARCH_DIR/pipi.tar.gz"
   
    # 下载并准备 qemu
    if [ ! -f "$ARCH_DIR/${QEMU_FILE}" ]; then
        log_info "下载 qemu: ${QEMU_URL}"
        wget -O "$ARCH_DIR/${QEMU_FILE}" "${QEMU_URL}"
    fi
    
    mkdir -p "$ARCH_DIR/qemu_linux"
    tar -xzvf "$ARCH_DIR/${QEMU_FILE}" -C "$ARCH_DIR/qemu_linux"
    rm -rf "$ARCH_DIR/qemu_linux/qemu-arm" \
           "$ARCH_DIR/qemu_linux/qemu-i386" \
           "$ARCH_DIR/qemu_linux/qemu-loongarch64" \
           "$ARCH_DIR/qemu_linux/qemu-mips64" \
           "$ARCH_DIR/qemu_linux/qemu-mips64el" \
           "$ARCH_DIR/qemu_linux/qemu-ppc64le" \
           "$ARCH_DIR/qemu_linux/qemu-s390x"
    tar -cJf "$ARCH_DIR/qemu_linux.txz" -C "$ARCH_DIR/qemu_linux" .
    rm -rf "$ARCH_DIR/qemu_linux"
    
    # cursor CLI：thirdapp/ 本地 tar 优先（离线/内网转存），否则按 CURSOR_CLI_URL 下载
    local cursor_local="${SCRIPT_DIR}/thirdapp/${CURSOR_CLI_FILE}"
    if [ ! -f "$ARCH_DIR/${CURSOR_CLI_FILE}" ]; then
        if [ -f "$cursor_local" ]; then
            log_info "使用本地 cursor CLI: ${cursor_local}"
            cp "$cursor_local" "$ARCH_DIR/${CURSOR_CLI_FILE}"
        elif [ -n "$CURSOR_CLI_URL" ]; then
            local auth_header=""
            [ -n "$ART_API_KEY" ] && auth_header="X-JFrog-Art-Api:${ART_API_KEY}"
            if [ -n "$auth_header" ]; then
                curl -sSf -H "$auth_header" -o "$ARCH_DIR/${CURSOR_CLI_FILE}" "$CURSOR_CLI_URL"
            else
                curl -sSfL -o "$ARCH_DIR/${CURSOR_CLI_FILE}" "$CURSOR_CLI_URL"
            fi
        else
            log_error "未找到 cursor CLI：请将 ${CURSOR_CLI_FILE} 放入 ${SCRIPT_DIR}/thirdapp/，或设置 CURSOR_CLI_URL 环境变量"
            exit 1
        fi
    fi

    # 设置 CROSS_COMPILER
    if [ -z "$CROSS_COMPILER" ]; then
        CROSS_COMPILER="${DEFAULT_CROSS_COMPILER}"
    fi
    echo "CROSS_COMPILER=$CROSS_COMPILER" > "$ARCH_DIR/env"
    export CROSS_COMPILER
    
    # 从模板生成 Dockerfile
    if [ ! -f "$ARCH_DIR/Dockerfile" ] || [ "$SCRIPT_DIR/Dockerfile.template" -nt "$ARCH_DIR/Dockerfile" ]; then
        log_info "从模板生成 Dockerfile..."
        cp "$SCRIPT_DIR/Dockerfile.template" "$ARCH_DIR/Dockerfile"
    fi
}
# 检查是否为 root 或具有 sudo 权限
check_sudo() {
    if ! command -v sudo &> /dev/null && [ "$EUID" -ne 0 ]; then
        log_error "请以 root 用户运行，或确保已安装并配置 sudo。"
        exit 1
    fi
}
# 安装 Docker（使用官方 yum 仓库）
install_docker() {
    log_info "正在安装 Docker..."
    # 安装必要依赖
    sudo yum install -y yum-utils
    # 安装 Docker Engine
    sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    # 启动并启用 Docker 服务
    sudo systemctl start docker
    sudo systemctl enable docker
    # 将当前用户加入 docker 组（避免每次用 sudo）
    if [ "$EUID" -ne 0 ]; then
        sudo usermod -aG docker "$USER"
        log_warn "已将当前用户加入 docker 组。请重新登录 shell 或运行 'newgrp docker' 以生效。"
    fi
    log_info "Docker 安装完成。"
}
# 清理构建文件
cleanup_build_files() {
    log_info "清理构建文件..."
    rm -f "$ARCH_DIR/node.tar.xz"
    rm -f "$ARCH_DIR/qemu_linux.txz"
    rm -f "$ARCH_DIR/env"
    rm -f "$ARCH_DIR/${QEMU_FILE}"
    rm -rf "$ARCH_DIR/offline"
    rm -f "$ARCH_DIR/${CURSOR_CLI_FILE}"
}
# 主逻辑
main() {
    log_info "开始为架构 '$ARCH' 检查 Docker 环境..."
    # 检查 Docker 是否安装
    if ! command -v docker &> /dev/null; then
        log_warn "Docker 未安装，正在安装..."
        check_sudo
        install_docker
    else
        log_info "Docker 已安装。"
        # 确保 Docker 服务正在运行
        if ! systemctl is-active --quiet docker; then
            log_info "启动 Docker 服务..."
            sudo systemctl start docker
        fi
    fi
    # 准备构建文件
    prepare_build_files
    # 构建镜像
    log_info "正在构建镜像: $IMAGE_NAME (架构: $ARCH)"
    if [ ! -f "$ARCH_DIR/Dockerfile" ]; then
        log_error "未找到 Dockerfile: $ARCH_DIR/Dockerfile"
        exit 1
    fi
    docker build \
        --network host \
        --build-arg BASE_IMAGE="${RESOLVED_BASE_IMAGE}" \
        --build-arg APT_URI="${APT_URI}" \
        --build-arg CROSS_COMPILER="${CROSS_COMPILER}" \
        -t "$IMAGE_NAME" \
        "$ARCH_DIR"
    log_info "镜像 $IMAGE_NAME 构建成功！"
    
    # 保存镜像
    local output_file="${IMAGE_NAME//:/_}${TAR_SUFFIX}"
    docker save -o "$output_file" "$IMAGE_NAME"
    log_info "镜像已保存到: $output_file"
    
    # 清理构建文件
    #cleanup_build_files
}
# 执行主函数
main "$@"