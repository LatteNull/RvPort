## 项目结构

本项目采用统一的构建脚本和 Dockerfile 模板，最大程度减少重复代码：

- `Dockerfile.template`: 公共的 Dockerfile 模板，使用 ARG 参数化处理架构差异
- `build_docker.sh`: 公共的构建脚本，自动处理不同架构的配置
- `arm/`: ARM 架构相关目录
    - `build_docker.sh`: 调用公共构建脚本的包装器
- `x86/`: x86 架构相关目录
    - `build_docker.sh`: 调用公共构建脚本的包装器

## 使用方法

### 方式：使用公共构建脚本

```bash
# 构建 ARM 镜像
./build_docker.sh arm

# 构建 x86 镜像
./build_docker.sh x86
```

### 自定义 CROSS_COMPILER

如果需要自定义交叉编译器，可以设置环境变量：

```bash
export CROSS_COMPILER="gcc-14-riscv64-linux-gnu,g++-14-riscv64-linux-gnu,gcc-x86-64-linux-gnu,g++-x86-64-linux-gnu,binutils-x86-64-linux-gnu"
./build_docker.sh arm
```

## 构建过程说明

构建脚本会自动：

1. **准备构建文件**：
    - 复制对应架构的 node.js 文件
    - 下载并准备 qemu 模拟器文件
    - 从模板生成对应架构的 Dockerfile

2. **检查 Docker 环境**：
    - 检查 Docker 是否安装，如未安装则自动安装
    - 确保 Docker 服务正在运行

3. **构建镜像**：
    - 使用 Dockerfile 构建镜像
    - 将镜像保存为 tar 文件

4. **清理临时文件**：
    - 自动清理构建过程中产生的临时文件

## 架构配置

各架构的配置差异已统一在 `build_docker.sh` 中管理：

- **ARM**: 使用 `ubuntu-ports` 镜像源，node-aarch64，qemu-arm64
- **x86**: 使用 `ubuntu` 镜像源，node-x86_64，qemu-amd64

## 基础镜像信息

arm的docker镜像：`arm64v8/ubuntu:24.04`（Docker Hub，或用国内镜像站加速）

x86的docker镜像：`ubuntu:24.04`（Docker Hub，或用国内镜像站加速）

## 代理设置

如果有代理，在执行 build.sh 之前先设置代理

```aiignore
export https_proxy=http://127.0.0.1:3128
export http_proxy=http://127.0.0.1:3128
export no_proxy=localhost,127.0.0.1,::1,10.0.0.0/8,<你的内网地址段>
```

需要在低版本上制作镜像

- x86 ubuntu

```
wget https://mirrors.aliyun.com/docker-ce/linux/ubuntu/dists/focal/pool/stable/amd64/docker-ce_20.10.17~3-0~ubuntu-focal_amd64.deb
wget https://mirrors.aliyun.com/docker-ce/linux/ubuntu/dists/focal/pool/stable/amd64/docker-ce-cli_20.10.17~3-0~ubuntu-focal_amd64.deb
wget https://mirrors.aliyun.com/docker-ce/linux/ubuntu/dists/focal/pool/stable/amd64/containerd.io_1.6.6-1_amd64.deb
wget https://mirrors.aliyun.com/docker-ce/linux/ubuntu/dists/focal/pool/stable/amd64/docker-compose-plugin_2.6.0~ubuntu-focal_amd64.deb
apt-get update
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    iptables \
    libseccomp2
dpkg -l | grep -i docker  # 查看安装的docker
apt-get remove -y docker.io  # 卸载docker，按上面的打印修改安装包名
sudo rm -rf /var/lib/docker
sudo rm -rf /var/lib/containerd
sudo rm -f /etc/docker/daemon.json
dpkg -i containerd.io_1.6.6-1_amd64.deb
dpkg -i docker-ce-cli_20.10.17~3-0~ubuntu-focal_amd64.deb
dpkg -i docker-ce_20.10.17~3-0~ubuntu-focal_amd64.deb
apt-get install -f -y
systemctl start containerd
systemctl enable containerd
systemctl start docker
systemctl enable docker
```

- arm centos

```
rpm -qa|grep docker
rpm -qa|grep containerd
wget https://mirrors.aliyun.com/docker-ce/linux/centos/8/aarch64/stable/Packages/containerd.io-1.6.6-3.1.el8.aarch64.rpm
wget https://mirrors.aliyun.com/docker-ce/linux/centos/8/aarch64/stable/Packages/docker-ce-20.10.17-3.el8.aarch64.rpm
wget https://mirrors.aliyun.com/docker-ce/linux/centos/8/aarch64/stable/Packages/docker-ce-cli-20.10.17-3.el8.aarch64.rpm
wget https://mirrors.aliyun.com/docker-ce/linux/centos/8/aarch64/stable/Packages/docker-compose-plugin-2.6.0-3.el8.aarch64.rpm
yum localinstall containerd.io-1.6.6-3.1.el8.aarch64.rpm
yum localinstall docker-ce-cli-20.10.17-3.el8.aarch64.rpm
yum localinstall docker-ce-20.10.17-3.el8.aarch64.rpm

```
