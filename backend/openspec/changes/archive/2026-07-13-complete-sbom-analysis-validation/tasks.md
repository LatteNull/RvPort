## 1. 验证入口和配置

- [x] 1.1 盘点现有 `backend/e2e`、SBOM analyzer 和真实记录脚本，确认可复用入口与缺口
- [x] 1.2 增加或完善 SBOM validation 运行入口，支持显式传入后端 API 地址、run id、x86 环境配置和 RISC-V 环境配置
- [x] 1.3 确保真实 SSH 地址、账号、密码、私钥、token 只从环境变量或本机配置读取，不写入仓库
- [x] 1.4 增加前置条件检查：PostgreSQL、Redis、RabbitMQ、后端 API、worker、Docker 和 SSH 环境不可用时必须明确失败或 skipped

## 2. 真实环境采集验证

- [x] 2.1 通过 API 或既有 runtime 创建/复用测试项目、x86 源环境和 RISC-V 目标环境
- [x] 2.2 运行 x86 与 RISC-V 连接测试，记录任务 ID、终态、OS、架构、包管理器和基础工具摘要
- [x] 2.3 运行 x86 与 RISC-V 环境采集，记录 owner package、provider evidence、repo metadata refresh、whatprovides 和 warning 摘要
- [x] 2.4 校验 RISC-V 仓库候选和 repository provides 数据不因 metadata 未准备而稳定为空；为空时记录明确原因

## 3. SBOM_ANALYSIS 验证

- [x] 3.1 使用真实采集快照触发 `SBOM_ANALYSIS` 任务并等待终态
- [x] 3.2 校验 `sbom_runs`、`sbom_components`、`replacement_candidates`、`tasks`、`task_events`、`tool_runs` 写入符合预期
- [x] 3.3 记录 analyzer 输入摘要、输出摘要、replacement status counts、risk counts、match counts、warnings 和 repository evidence counters
- [x] 3.4 校验 API 响应、任务事件、日志 excerpt 和记录文件不包含明文凭据、私钥、token 或敏感路径

## 4. E2E 覆盖补齐

- [x] 4.1 补齐 SBOM E2E 正常流程：创建分析任务、等待成功、查询列表、查询详情、查询组件和替代候选
- [x] 4.2 补齐 SBOM E2E 异常流程：快照不存在、环境不属于项目、无项目权限、分析器失败
- [x] 4.3 补齐 SBOM E2E edge case：空组件清单、仓库候选为空但有 warning、同名不同架构、重复仓库候选、输出脱敏
- [x] 4.4 确保 E2E 用例不会随 `mvn test` 自动运行，只能通过显式脚本执行

## 5. 清理和记录

- [x] 5.1 增加按 run id 清理本次验证数据的脚本或 runner 流程
- [x] 5.2 清理数据库中的项目、环境、快照、组件、SBOM 运行、替代候选、任务、事件、日志、tool run 和审计测试记录
- [x] 5.3 清理测试运行时目录、上传文件、临时 analyzer 输入输出和队列残留消息
- [x] 5.4 保留必要的非敏感验证记录文件，并在记录中写入复跑命令、环境摘要和脱敏检查结果

## 6. 测试和验收

- [x] 6.1 运行 Maven 相关单元测试，覆盖正常流程、异常流程和 edge case
- [x] 6.2 运行 `tools/sbom-analyzer` 测试
- [x] 6.3 运行 SBOM E2E 脚本或在前置条件不可用时记录明确 skipped 原因
- [x] 6.4 运行 `openspec validate --all`
- [x] 6.5 更新必要中文文档，说明 SBOM 验证运行命令、前置条件、记录位置和清理命令
