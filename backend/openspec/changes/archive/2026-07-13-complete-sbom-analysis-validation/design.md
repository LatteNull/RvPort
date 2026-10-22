## Context

`improve-library-provider-resolution` 已经把 provider/whatprovides、repo metadata refresh、架构归一化候选接入环境采集和 SBOM 分析器，并生成过一次真实 x86/RISC-V 比较记录。但该 change 归档时仍有 4 个验证类任务未完成：真实环境采集记录、使用采集结果运行 `SBOM_ANALYSIS`、清理测试数据、完整测试执行。

本 change 的目标是补齐验证闭环，而不是继续扩展 SBOM 算法。验证需要同时覆盖后端 API 路径、worker 路径、分析器路径和本地记录留存。由于真实 SSH 环境、Docker、数据库和后端服务可能不可用，脚本必须明确报告前置条件缺失，不能把未运行伪装为成功。

## Goals / Non-Goals

**Goals:**

- 提供可复跑的 SBOM 验证入口，能创建或复用 x86/RISC-V 环境，运行连接测试、环境采集和 SBOM 分析。
- 保存非敏感验证记录，包括 API 请求摘要、任务 ID、快照摘要、repo metadata 状态、provider/whatprovides 命中摘要、分析器输入输出摘要和 warning。
- 校验目标仓库候选与 provider 证据不为空或给出明确不完整原因。
- 清理验证产生的数据库记录、运行时目录、队列残留和临时文件。
- 补齐单元测试、分析器测试和可运行的 API E2E 结果记录。

**Non-Goals:**

- 不新增 SBOM 数据表。
- 不改变现有替代算法的风险等级或状态枚举。
- 不把真实 SSH 地址、账号、密码、私钥、token 写入仓库。
- 不要求普通 `mvn test` 连接真实基础设施。

## Decisions

### 1. 使用独立 E2E/validation 脚本，不并入 Maven 单元测试

SBOM 真实验证依赖 PostgreSQL、Redis、RabbitMQ、后端服务、worker 和可访问的 SSH 环境。将其并入 `mvn test` 会让普通单元测试不稳定。因此验证入口放在 `backend/e2e` 或同级脚本中，由开发者显式运行。

替代方案是使用 Testcontainers 启动依赖，但真实 SSH 环境和远程 repo metadata 仍不可控，不能完全解决端到端验证问题。

### 2. 记录文件只保留非敏感摘要

验证记录应保存在 `backend/runtime/real-records` 或等效目录，文件名包含 run id 和时间戳。记录内容允许包含组件数量、包名、版本、架构、provider evidence 类型、warning 和 analyzer summary，不允许包含明文凭据、私钥、token、服务器真实敏感路径或完整任务日志。

### 3. 清理必须独立可执行

清理逻辑需要可单独执行，支持按 run id 清理本次验证，也支持清理历史 `e2e_` 或 `sbom_validation_` 前缀残留。清理失败必须返回非零退出码并指出未清理资源类型。

### 4. 前置条件缺失必须显式失败或标记 skipped

如果 Docker、后端 API、worker、RabbitMQ 或 SSH 环境不可用，验证脚本必须输出明确原因。对于不影响普通单元测试的真实验证，可以标记 skipped；但归档前需要人工看到 skipped 原因，不能只输出“通过”。

## Risks / Trade-offs

- [Risk] 真实远程环境不稳定导致验证失败。→ Mitigation: 记录具体失败阶段、命令摘要和安全错误，允许重跑，不把失败隐藏成成功。
- [Risk] 验证记录泄露真实环境或凭据信息。→ Mitigation: 统一脱敏，记录前扫描敏感字段，真实凭据只从环境变量或本机配置读取。
- [Risk] 清理脚本误删非测试数据。→ Mitigation: 所有测试资源使用 run id 或固定测试前缀，清理只按白名单前缀和关联表顺序执行。
- [Risk] API E2E 与直接 analyzer 验证结果不一致。→ Mitigation: 记录两条路径的输入摘要，并以 API/worker 路径作为最终验收依据。

## Migration Plan

1. 增加或完善 SBOM validation/E2E 脚本。
2. 增加记录输出和清理入口。
3. 补齐 Java 单元测试、analyzer 测试和 API E2E 覆盖。
4. 在本机可用基础设施下执行完整验证；若外部前置条件不可用，记录 skipped 原因并保留可复跑命令。
5. 验证通过后归档并同步 spec。

## Open Questions

- 真实 x86/RISC-V 环境的连接配置是否长期固定，还是每次通过本机 `.env` 或外部配置注入。
- `backend/runtime/real-records` 是否长期保留在仓库外，还是只作为本机审计记录。
