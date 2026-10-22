# 双架构构建与测试样例

[English](build.md) | 简体中文

本文中的命令均假定源码已经由 RvPort 部署到当前工作目录。除特别说明外，同一段命令可分别在 x86_64 源环境和 riscv64 目标环境原生执行；不要用 x86 的编译产物替代 RISC-V 的构建。

## 样例选择与基础依赖

| 难度             | 仓库                                                   | 用途                                | 环境基础依赖                                                                   |
| ---------------- | ------------------------------------------------------ | ----------------------------------- | ------------------------------------------------------------------------------ |
| 简单             | [simdinfo](https://github.com/abetlen/simdinfo)        | x86 SIMD 探测与 RISC-V 适配分支验证 | `gcc`、`make`                                                                  |
| 简单             | [cJSON](https://github.com/DaveGamble/cJSON)           | ANSI C、库与单元测试                | `gcc`、`make`、`cmake`                                                         |
| 中等             | [zlib](https://github.com/madler/zlib)                 | 压缩库、CMake/CTest                 | `gcc`、`make`、`cmake`                                                         |
| 复杂             | [SQLite](https://github.com/sqlite/sqlite)             | 代码生成、CLI、完整回归测试         | `gcc`、`make`；完整测试另需 `tcl`、`tcl-devel`                                 |
| 复杂             | [libarchive](https://github.com/libarchive/libarchive) | 多格式归档、特性探测、CLI、测试集   | `gcc`、`make`、`cmake`；完整特性另需各压缩格式的 `*-devel` 包                  |
| 高复杂度（可选） | [curl](https://github.com/curl/curl)                   | 协议、TLS、压缩、SSH 等可选依赖矩阵 | `gcc`、`make`、`autoconf`、`automake`、`libtool`、`pkgconf-pkg-config`、`perl` |

建议先运行 simdinfo，验证两种架构确实走到了各自的编译分支；再让 cJSON、zlib 成功，最后用 SQLite 和 libarchive 验证更复杂的构建与测试链路。curl 建议在前述样例稳定后再导入。

---

# simdinfo 构建与验证（架构差异）

源码：https://github.com/abetlen/simdinfo

simdinfo 是架构迁移样例，不是通用跨架构库：其 x86 目标使用项目提供的 Makefile，RISC-V 目标使用显式的通用编译路径。上游没有可直接调用的自动化测试目标，因此以“成功构建 + 对应架构二进制可执行”作为测试/冒烟验证。

## 双环境公共构建脚本

```shell
set -e
mkdir -p bin

case "$(uname -m)" in
  x86_64)
    make clean
    make bin/main-x86_64
    ;;
  riscv64)
    gcc \
      -o bin/main-riscv64 \
      main.c \
      -march=rv64gc \
      -mabi=lp64d \
      -I. \
      -O2 \
      -Wall
    ;;
  *)
    echo "Unsupported architecture: $(uname -m)" >&2
    exit 1
    ;;
esac
```

## 测试/冒烟验证脚本

```shell
set -eu

case "$(uname -m)" in
  x86_64)
    test -x bin/main-x86_64
    bin/main-x86_64
    ;;
  riscv64)
    test -x bin/main-riscv64
    bin/main-riscv64
    ;;
  *)
    echo "Unsupported architecture: $(uname -m)" >&2
    exit 1
    ;;
esac
```

---

# cJSON 构建命令（简单）

源码：https://github.com/DaveGamble/cJSON

## 双环境公共构建脚本

```shell
set -eu

cmake -S . -B build \
  -DENABLE_CJSON_TEST=ON \
  -DENABLE_CJSON_UTILS=ON
cmake --build build --parallel 2
```

## 测试脚本

```shell
set -eu

ctest --test-dir build --output-on-failure
```

---

# zlib 构建命令（中等）

源码：https://github.com/madler/zlib

## 双环境公共构建脚本

```shell
set -eu

cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DZLIB_BUILD_TESTING=ON
cmake --build build --parallel 2
```

## 测试脚本

```shell
set -eu

ctest --test-dir build --output-on-failure
```

---

# SQLite 构建命令（复杂）

源码：https://github.com/sqlite/sqlite

SQLite 的 `sqlite3` CLI 可以仅用 C 工具链构建；其完整回归测试依赖 Tcl。因此将“基础构建验证”和“完整测试”分开记录。

## 双环境公共构建脚本

```shell
set -eu

mkdir -p build
cd build
../configure
make -j"$(nproc)" sqlite3
./sqlite3 --version
```

## 完整测试脚本（需要 `tcl` 与 `tcl-devel`）

```shell
set -eu

cd build
make -j"$(nproc)" test
```

## 无 Tcl 时的基础验证

```shell
set -eu

cd build
./sqlite3 ':memory:' 'select sqlite_version();'
```

---

# libarchive 构建命令（复杂）

源码：https://github.com/libarchive/libarchive

该仓库会根据当前环境自动探测压缩、加密、ACL、xattr 等能力。首次验证建议保留默认探测结果；缺少某个可选 `*-devel` 包通常会减少对应功能，并不等同于构建失败。

## 构建命令（双环境）

```shell
set -eu

cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_TEST=ON
cmake --build build --parallel 2
```

## 测试命令（双环境）

```shell
set -eu

ctest --test-dir build --output-on-failure
```

构建命令会启用并编译测试目标；在该构建目录上，测试命令只执行 `ctest`。

---

# curl 构建命令（高复杂度，可选）

源码：https://github.com/curl/curl

curl 适合验证依赖发现与功能裁剪。先关闭 TLS、压缩、LDAP 等可选功能，得到可在两端稳定复现的最小构建；后续再逐项安装开发包、打开相应开关。

## 双环境最小构建脚本

```shell
set -eu

./buildconf
./configure \
  --without-ssl \
  --without-libpsl \
  --without-zlib \
  --without-brotli \
  --without-zstd \
  --disable-ldap \
  --disable-ldaps
make -j"$(nproc)"
```

## 测试脚本（需要 `perl`）

```shell
set -eu

make test
```

## 最小构建冒烟验证

```shell
set -eu

./src/curl --version
```
