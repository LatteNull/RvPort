case "$(uname -m)" in
  x86_64|amd64)
    ARCH="amd64";;
  aarch64)
    ARCH="arm64";;
  armv7l|armv6l|armhf)
    ARCH="arm";;
  ppc64le)
    ARCH="ppc64le";;
  s390x)
    ARCH="s390x";;
  riscv64)
    ARCH="riscv64";;
  *)
    echo "不支持的架构: $(uname -m)"
    exit 1
    ;;
esac
# 示例：执行不同架构下的命令
case "$ARCH" in
  riscv64)
    ARCH="riscv64";;
  amd64|arm64|arm)
    echo "执行通用逻辑";;
  ppc64le|s390x)
    echo "为特殊架构执行自定义逻辑";;
esac

# 示例：执行不同架构下的命令
case "$ARCH" in
  amd64|arm64|arm)
    echo "执行通用逻辑";;
  ppc64le|s390x)
    echo "为特殊架构执行自定义逻辑";;
esac

#!/bin/bash/arm

#多行注释检查
:<<'command'
arch
arm64
command

# 编译时指定 x86、arm 架构参数
gcc -march=x86-64 -o myapp_x86 myapp.c
gcc -march=armv7-a -o myapp_arm myapp.c

# 使用 x86 反汇编语法
objdump -M intel -d my_binary_x86 > disasm_x86.txt

# 指定 x86/arm 架构动态链接器
/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2 ./my_binary_x86
/usr/lib/arm-linux-gnueabihf/ld-linux-armhf.so.3 ./my_binary_arm

# 检查 x86/arm 设备节点
if [ -e /sys/devices/platform/x86_specific_device ]; then
    echo "x86 device found"
fi


# 引用 x86/arm 架构相关库路径
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/usr/lib/arm-linux-gnueabihf

* amd64 [default]
* arm
* arm64
* ppc64le

ALL_ARCH.linux = amd64 arm arm64 ppc64le s390x
TRIPLE.linux-arm := arm-linux-gnueabihf
TRIPLE.linux-arm64 := aarch64-linux-gnu
case "$(uname -m)" in
  aarch64*) host_arch=arm64 ;;
  arm*) host_arch=arm ;;
case "$(uname -m)" in
  aarch64*) host_arch=arm64 ;;
  arm*) host_arch=arm ;;
readonly KUBE_SUPPORTED_SERVER_PLATFORMS=(
  linux/amd64
  linux/arm64
)

readonly KUBE_SUPPORTED_CLIENT_PLATFORMS=(
  linux/arm
  linux/arm64
)

volume /usr/local/go/pkg/linux_arm_cgo

volume /usr/local/go/pkg/linux_arm64_cgo


