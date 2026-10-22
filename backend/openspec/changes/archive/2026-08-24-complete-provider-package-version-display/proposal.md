## Why

当前构建驱动依赖分析已经能从 ELF/SO 和构建工具事实中找到部分目标 provider 证据，但真实验证结果显示源端和目标端的软件包名称、软件包版本、命令检测版本没有形成稳定的结构化字段，HTML/API 也没有完整展示双方版本。用户无法直接判断“源环境用了哪个包和版本，目标环境或目标源提供哪个包和版本，以及版本关系对应的风险”。

本次变更需要补齐 provider package/version 的采集、持久化、API 输出和 HTML 展示，使真实依赖分析结果可以被审计，并为后续迁移输入、报告和前端列表展示提供统一字段。

## What Changes

- 为依赖分析结果补齐源端 provider package、源端 provider version、目标端 provider package、目标端 provider version、源端 detected version、目标端 detected version、provider version status 等结构化字段。
- ELF/SO 版本识别必须优先使用包管理器 owner/provider 查询；无法找到 owner package 时，才使用 SONAME、文件名、readelf、objdump、strings 等低置信度证据作为 detected version。
- 构建工具版本识别必须优先使用包管理器 owner/provider 查询，并可辅以安全的 `--version`/专用版本命令作为 detected version。
- 依赖分析列表 API、详情 API、JSON artifact 和 HTML artifact 必须展示源端包名/版本、目标端包名/版本、detected version、provider version status 和风险等级。
- 真实验证汇总 HTML 必须展示上述字段，避免只显示裸 `provider` 名称。
- 补充单元测试和 E2E/真实验证脚本，覆盖源/目标包版本完整、源 owner 缺失、目标版本缺失、命令版本可检测、SO 只能读取 ELF evidence 等情况。
- 不改动旧 SBOM 主流程；本次变更只面向构建驱动依赖分析。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `dependency-analysis-runtime`: 补齐 provider package/version 和 detected version 的结果契约、API 输出、制品展示和风险审计能力。
- `api-e2e-test-suite`: 增加依赖分析 E2E 对 provider package/version 字段、版本状态和展示字段的验证。

## Impact

- 影响依赖分析 fact 提取、源端/目标端 provider resolver、依赖结果持久化、jOOQ 生成代码、依赖分析 API DTO、JSON/HTML artifact、真实验证汇总脚本和 E2E 测试。
- 可能需要新增数据库字段或扩展现有 `evidence` JSON；如果新增字段，应通过 Liquibase 迁移并重新运行 jOOQ 生成脚本。
- 不应暴露服务器真实路径、SSH 凭据、私钥、token 或完整远端日志；路径和 evidence 仍需要遵循现有脱敏规则。
