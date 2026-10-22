## Why

当前 scanner 缺少 config.guess 正式输入，Autoconf Shell 主要按架构名称判分支，无法区分通用接受与 `*) exit 1` 拒绝。补齐配置单元、脚本内容版本和有界接受证明，且按用户最终约束保持 **V2 schema、现有 CLI 和后端接入全部不变**。

## What Changes

- 在现有 --input 源码工作区内发现 config.guess/config.sub/configure/configure.ac/M4，分析安全有界的变量、case/if、输出/退出和辅助调用。
- 复用已有编译数据库接入；它只表示原构建编译上下文，不能证明使用 Autoconf 或充当目标配置。不读取远端构建环境，不要求新增构建产物传输。
- 只分析当前输入中真实存在的配置逻辑，以路径、内容 digest 和配置单元隔离不同版本；未知 OS/libc、动态脚本、缺失文件和未来重新生成都保留 unknown。
- 区分 source-level 配置关联与已观测执行；Makefile/config.h/config.status/cache 等 x86 已求值结果不作为本次 Autoconf 的目标环境。
- 接入现有 Fact/图/分类/证据链与报告，保持默认 V2/显式 V1、三个 artifact、上下各 20 行和双语建议，不修改封闭报告 schema。
- 单元测试纳入所有新增/修改模块及未加载源码，独立测试容器验收整体和受影响模块 90% 行/90% 分支覆盖。

## Capabilities

### New Capabilities

- `kb-scanner-autoconf-target-support`: 现有输入下的配置单元发现、有界接受/拒绝/unknown、版本范围、兼容证据链与验证。

### Modified Capabilities

- `kb-scanner-build-selection-analysis`: 发现 config.guess，Autoconf 不再用名称/wildcard 或全文件角色集合推导确定支持。

## Impact

- 仅 tools/kb-scanner 正式 frontend、analyzer、必要的分类/投影接入和测试文档。
- **无新 CLI 参数、manifest、target-platform 输入协议、snapshot source registry 或后端采集交接任务。** 此前草案的 observed-build-context capability 撤回，不是已实现能力的删除。
- 不改 backend/frontend、根 Compose、生产镜像、报告 schema 或两份编译器 JSON；不在宿主机安装/测试 scanner 依赖。
- 保持 source-only/compile-database-only 路径可用；未传入的远端生成脚本不在证明范围，不能声称已自动复用完整 x86 环境。
