## 1. 环境采集工具预检与安装

- [x] 1.1 梳理 `SshRuntimeService` 中环境采集、依赖分析前刷新、source-only 构建观测对远端工具的依赖。
- [x] 1.2 增加源环境辅助工具预检，覆盖 `find`、`readelf`、`objdump`、`rpm/dpkg-query`、`strace`、`bear`。
- [x] 1.3 增加目标环境辅助工具预检，覆盖 `find`、`readelf`、`objdump`、`rpm/dpkg-query`，不强制要求 `strace` 和 `bear`。
- [x] 1.4 为 RPM/DNF 环境实现受控自动安装尝试，源环境 allowlist 包含 `findutils`、`binutils`、`strace`、`bear`，目标环境 allowlist 包含 `findutils`、`binutils`。
- [x] 1.5 将工具缺失、安装成功、安装失败和跳过安装原因写入任务日志或环境快照 raw summary。

## 2. 库文件采集降级

- [x] 2.1 修复标准库目录扫描对 `find` 的静默依赖，缺少 `find` 时必须产生明确 warning。
- [x] 2.2 增加 `/lib`、`/lib64`、`/usr/lib`、`/usr/lib64`、`/usr/local/lib` 的 shell glob 或固定深度 fallback 扫描。
- [x] 2.3 确保符号链接目录和符号链接库文件不会导致基础库完全漏采。
- [x] 2.4 确保 fallback 发现的 `.so` 仍会执行 owner package 查询并写入 provider metadata。

## 3. 依赖分析 provider 匹配

- [x] 3.1 将 `compile_commands.json` 解析出的 `-l<name>` 链接库改为 provider-aware 匹配。
- [x] 3.2 将 strace execve 解析出的 `-l<name>` 链接库改为 provider-aware 匹配。
- [x] 3.3 将通用 linker flag 解析出的 `-l<name>` 链接库改为 provider-aware 匹配。
- [x] 3.4 确保源侧 owner package 已知时，目标侧库文件未命中后会回退到目标同名包、规范化包名和基础库别名包。
- [x] 3.5 补齐 `libc -> glibc`、`libgcc_s -> gcc/libgcc` 的目标 provider 匹配路径，并保留 evidence。
- [x] 3.6 校验 provider version status 与风险等级映射保持一致。

## 4. 测试覆盖

- [x] 4.1 增加环境采集单元测试，覆盖辅助工具缺失、自动安装命令生成、安装失败 warning 和 fallback 扫描。
- [x] 4.2 增加依赖分析单元测试，覆盖 `libc.so`、`libgcc_s.so` 在目标库快照缺失但 package 存在时不误判缺失。
- [x] 4.3 增加 edge case 测试，覆盖源 owner package 缺失、目标 provider 缺失、目标版本缺失和主版本比较。
- [x] 4.4 更新 API E2E 依赖分析模块，覆盖极简 RPM/openEuler 目标环境和源环境 `strace/bear` 补齐。
- [x] 4.5 运行后端单元测试和相关 E2E，并记录 openEuler SP2 真实环境 `libc.so`、`libgcc_s.so` 的结果。

## 5. 验证与收尾

- [x] 5.1 使用 4005 openEuler 24.03 LTS-SP2 RISC-V 环境重新执行环境刷新和依赖分析。
- [x] 5.2 验证环境快照包含辅助工具检测结果、安装尝试结果和库/provider 证据。
- [x] 5.3 验证依赖分析结果中 `libc.so`、`libgcc_s.so` 不再错误显示为 `MISSING`。
- [x] 5.4 检查 OpenSpec 变更状态并运行必要的校验命令。
