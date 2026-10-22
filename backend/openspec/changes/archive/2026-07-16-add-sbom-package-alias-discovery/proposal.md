## Why

当前 SBOM 分析在跨发行版场景下会把同一运行时能力误判为缺失。例如 openEuler 中 `CP1250.so` 归属 `glibc`，而 Bianbu 中同名文件归属 `libc6:riscv64`；如果只按源包名匹配，结果会进入人工确认，降低分析可信度。

需要让分析器在分析过程中自动发现并记录这类包名等价关系，避免长期依赖人工维护静态规则。

## What Changes

- 增加 SBOM 包名等价关系自动发现能力：当源组件和目标组件通过同名文件、ELF SONAME、provided capability 或库名匹配成功，但 owner package 不一致时，记录 package alias observation。
- 在本次分析中即时使用已发现的等价关系，将有明确证据的运行时库从人工确认降级为目标已存在或可直接使用的候选。
- 沉淀跨任务可复用的 package alias 观测记录，后续分析可以读取历史候选关系作为匹配证据。
- 扩大系统库扫描深度：系统库目录从 `-maxdepth 2` 调整为 `-maxdepth 4`，覆盖 Debian/Bianbu multiarch 与 gconv 路径，例如 `/usr/lib/riscv64-linux-gnu/gconv/CP1250.so`。
- 保留自动发现关系的状态管理边界：自动发现默认是 `CANDIDATE`，后续可由人工或管理接口提升为 `APPROVED` 或标记为 `REJECTED`。

## Capabilities

### New Capabilities
- `sbom-package-alias-discovery`: 定义 SBOM 分析中的跨发行版包名等价关系发现、沉淀、复用和证据展示行为。

### Modified Capabilities
- 无

## Impact

- 影响后端环境采集脚本中的系统库扫描深度与采集结果完整性。
- 影响 `tools/sbom-analyzer` 的匹配逻辑、输出 metadata 和测试用例。
- 影响 Java 后端 SBOM 分析输入构造、结果导入、数据库 schema 和查询接口。
- 需要新增数据库表或等价结构保存 package alias observations，并通过 Liquibase 管理 schema。
- 需要补充单元测试、分析器测试和一次真实环境验证，覆盖正常流程、异常流程和 edge case。
