## 1. 环境采集增强

- [x] 1.1 盘点 `SshRuntimeService` 当前 `TOOL_VERSION`、`TOOL_PROVIDER` 输出和 `createCollectedComponents` 工具组件构造逻辑
- [x] 1.2 调整采集脚本，使 owner package 查询失败时仍输出工具路径、版本和 provider 状态
- [x] 1.3 为工具 metadata 增加 `installOrigin`、`versionText`、`versionMajor`、`providerScanner` 和 `toolPath`
- [x] 1.4 实现 unmanaged 路径判断：`/usr/local`、`/opt`、`/home/*/.local`、`/root/.local`
- [x] 1.5 确保 owner package 存在时 `installOrigin=package`，owner package 缺失但命令存在时不丢弃 `TOOL` 组件

## 2. SBOM analyzer 匹配增强

- [x] 2.1 盘点 `tools/sbom-analyzer` 当前 `TOOL` 与 `PACKAGE` 共用匹配路径，确认 installed 优先级
- [x] 2.2 增加同名 `TOOL` installed match，输出 `TARGET_PRESENT` 和 `matchType=tool_name_version`
- [x] 2.3 对 package-managed 同名工具且主版本一致的结果保留 `LOW` 风险
- [x] 2.4 对 unmanaged/unknown 工具或主版本不同的同名工具输出 `MEDIUM` 风险
- [x] 2.5 在 candidate metadata 中输出 source/candidate `versionText`、`versionMajor`、`installOrigin` 和 `toolPath`
- [x] 2.6 确保目标已安装工具命中优先于目标仓库候选

## 3. 测试覆盖

- [x] 3.1 补充 Java 测试：package-managed 工具 metadata 包含 `installOrigin=package`
- [x] 3.2 补充 Java 测试：provider 查询失败但工具在 `/opt` 或 `/usr/local` 时生成 unmanaged `TOOL` 组件
- [x] 3.3 补充 analyzer 测试：同名 package-managed tool 生成 `TARGET_PRESENT` / `LOW`
- [x] 3.4 补充 analyzer 测试：同名 unmanaged tool 生成 `TARGET_PRESENT` / `MEDIUM`
- [x] 3.5 补充 analyzer 测试：同名工具主版本不同生成 `TARGET_PRESENT` / `MEDIUM`
- [x] 3.6 补充 analyzer 测试：目标 installed tool 优先于 repository candidate

## 4. 报告和验证

- [x] 4.1 更新静态 SBOM HTML 报告，展示工具 `installOrigin`、`versionMajor` 和 `toolPath`
- [x] 4.2 运行 `python -m unittest discover -s tests` 于 `tools/sbom-analyzer`
- [x] 4.3 运行相关 Maven 测试或 `mvn -q test`
- [x] 4.4 运行 `openspec validate --all`
- [x] 4.5 使用真实或 fixture 环境生成一份包含 unmanaged 工具场景的验证记录
