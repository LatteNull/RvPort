## 1. 数据库与模型

- [x] 1.1 使用 Liquibase 新增 `sbom_package_alias_observations` 表，包含 project/task/run、source/target package、distro、package manager、evidence、confidence、status、observed_count、first_seen_at、last_seen_at 等字段
- [x] 1.2 为 alias observation 增加唯一约束和查询索引，覆盖 source package、target package、status、distro、package manager 和 last_seen_at
- [x] 1.3 重新运行 jOOQ 生成脚本，生成并提交对应代码
- [x] 1.4 增加 Java DTO、Repository 和 Service 方法，用于保存、合并、查询和注入 package alias observation

## 2. 环境采集

- [x] 2.1 将系统库目录 `.so*` 扫描从 `-maxdepth 2` 调整为 `-maxdepth 4`
- [x] 2.2 保持 `/opt` 和 `/usr/local/bin` unmanaged native 扫描深度不扩大
- [x] 2.3 验证 Bianbu/Debian multiarch 路径 `/usr/lib/<arch>/gconv/CP1250.so` 能被采集并记录 owner package
- [x] 2.4 补充采集测试，覆盖正常流程、异常流程和 edge case

## 3. SBOM Analyzer

- [x] 3.1 扩展 analyzer input，支持可选 `packageAliases`
- [x] 3.2 增加 library/native evidence pre-pass，在跨操作系统、发行版或包管理器场景下先生成本次 package alias observations
- [x] 3.3 在 analyzer 中发现 capability/library/filename 匹配但 owner package 不同的 package alias observation
- [x] 3.4 将 pre-pass alias observation 用于 package/tool candidate 判断，并在 candidate metadata 中输出 alias 证据
- [x] 3.5 在 library/native finalization 阶段使用 package 判断结果覆盖已由 package candidate 解决的库
- [x] 3.6 输出 `packageAliasObservations`，包含 source/target package、evidence type/value、confidence、status 建议和 source/target component 信息
- [x] 3.7 增加 analyzer 单元测试，覆盖 `glibc -> libc6`、跨 OS 先库后包、弱匹配不高置信、多候选冲突和历史 alias 注入

## 4. Java 后端集成

- [x] 4.1 在构造 analyzer input 时注入未被拒绝的历史 package alias observations
- [x] 4.2 在导入 analyzer output 时保存或更新 package alias observations
- [x] 4.3 在分析结果 evidence 中保留 alias 证据字段
- [x] 4.4 增加 package alias observation 查询接口，支持分页、排序和按包名、状态、distro、package manager 过滤
- [x] 4.5 确认接口进行项目权限校验，避免跨项目读取 alias observation

## 5. 验证与测试

- [x] 5.1 运行 Maven 单元测试，确保正常流程、异常流程和 edge case 覆盖新增逻辑
- [x] 5.2 运行 `tools/sbom-analyzer` 测试套件
- [x] 5.3 启动后端和基础设施，跑一遍 API/E2E 验证新增接口
- [x] 5.4 使用真实 x86 source 与 `ssh root@localhost -p 4002` Bianbu/RISC-V target 跑全流程，确认 `CP1250.so` 不再误判为人工确认
- [x] 5.5 使用 HTML/API 查看结果，确认 alias evidence、分页、排序和过滤可审计

## 6. 文档与收尾

- [x] 6.1 更新相关 README 或设计文档，说明自动发现 alias 的置信度和审核边界
- [x] 6.2 记录已知限制，包括自动候选不是人工强规则、版本归一化另行处理
- [x] 6.3 检查 OpenSpec tasks 全部完成后再 archive 和 sync
