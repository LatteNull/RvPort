## 1. Scanner 文件发现与类型识别

- [x] 1.1 将 `*.spec` 纳入 KB Scanner 文件发现范围
- [x] 1.2 为 RPM spec 文件增加独立类型标记或等效 source kind
- [x] 1.3 确认扫描排除路径对 `*.spec` 文件继续生效

## 2. RPM spec 解析与匹配基础

- [x] 2.1 实现 RPM spec 轻量按行解析，识别 `%prep`、`%build`、`%install`、`%check`、`%files`、`%changelog`
- [x] 2.2 识别 `ExclusiveArch`、`ExcludeArch`、`%ifarch`、`%ifnarch`、`%if`、`%else`、`%endif`
- [x] 2.3 为命中项生成包含 section、条件栈、命中 token 和原始行摘要的 evidence
- [x] 2.4 忽略注释行和 `%changelog` section，避免默认误报
- [x] 2.5 仅对架构相关局部宏做静态识别，不引入完整 RPM 宏展开作为必需流程
- [x] 2.6 确认缺少 `rpmspec` 时 scanner 仍能完成 RPM spec 扫描

## 3. 独立 YAML 规则

- [x] 3.1 新增 RPM spec 专属 YAML 规则文件，不混入现有通用 build 规则
- [x] 3.2 增加 `ExclusiveArch` 不包含 RISC-V 的匹配规则
- [x] 3.3 增加 `ExcludeArch` 显式排除 RISC-V 的匹配规则
- [x] 3.4 增加 `%build`、`%install` 中 x86-only 编译参数匹配规则
- [x] 3.5 增加 `%check` 中 x86-only 测试逻辑、RISC-V 跳过逻辑和 x86-only 参数匹配规则
- [x] 3.6 增加架构条件块中依赖行或 source/patch 选择逻辑的匹配规则

## 4. Finding 输出与后端链路

- [x] 4.1 确认 RPM spec finding 能被现有 `scan-result.json` schema 表达
- [x] 4.2 确认后端导入 findings 时保留 RPM spec source kind、rule id、severity 和 evidence
- [x] 4.3 确认代码上下文 API 能读取 `*.spec` 文件并高亮命中行
- [x] 4.4 确认报告 artifact 和归档候选登记包含 RPM spec findings
- [x] 4.5 确认不新增、不替换、不重命名 KB Scanner 主输出文件，并保持 `scan-result.json`、`scan-report.html`、`scan.log` 契约兼容

## 5. 测试覆盖

- [x] 5.1 增加 scanner 正常流程测试：包含 x86-only `ExclusiveArch`、`%build` 和 `%check` 的 spec 文件
- [x] 5.2 增加 scanner 异常流程测试：未知宏、条件块不完整或格式不完整时不导致整次扫描失败
- [x] 5.3 增加 edge case 测试：注释、`%changelog` 和普通依赖行不误报
- [x] 5.4 增加 edge case 测试：存在 portable/RISC-V sibling 分支时按预期降级或标记 hint
- [x] 5.5 增加后端或 E2E fixture，验证 RPM spec finding 可通过 API 查询和下载报告查看
- [x] 5.6 增加兼容性测试，验证 RPM spec 扫描结果仍使用现有 `scan-result.json` 输出结构
- [x] 5.7 增加无 `rpmspec` 环境测试，验证基础 RPM spec finding 不依赖完整宏展开工具

## 6. 验证

- [x] 6.1 运行 KB Scanner 测试
- [x] 6.2 运行后端相关单元测试
- [x] 6.3 使用包含 RPM spec 的真实或 fixture 项目跑一次 KB 扫描 API 验证
- [x] 6.4 执行 `openspec validate add-rpm-spec-kb-scan --strict`
