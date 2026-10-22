# Build context 固定夹具

这两个夹具只固定 Clang 21.1.8 target/profile 绑定，不声称锁定 glibc、musl 或 vendor
libm。当前 `Dockerfile.dev` 用于分析工具链验证，但没有固定被扫描应用的 sysroot、链接结果和
运行镜像，因此 libm、运行时浮点环境与应用 target features 均显式保留为 `unknown`。这可防止
扫描器借用宿主环境补值。
