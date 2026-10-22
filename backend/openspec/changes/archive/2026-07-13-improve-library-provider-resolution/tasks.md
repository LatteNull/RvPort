## 1. 现状确认

- [x] 1.1 复核当前 `ENV_COLLECT` 输出结构、`environment_components.metadata` 写入格式和 SBOM analyzer 输入 schema
- [x] 1.2 复核 rpm/dnf/yum 与 dpkg/apt 系统中 owner package、repo package、whatprovides 查询命令可用性
- [x] 1.3 明确采集输出上限、命令超时和仓库 metadata refresh 参数，避免远程命令长时间阻塞

## 2. 环境采集 provider 增强

- [x] 2.1 在环境采集脚本中为已发现 `.so` 和 native 文件增加 rpm/dpkg owner package 查询
- [x] 2.2 将 owner package、owner version、owner arch、provider scanner 和 provider warning 解析进标准化 summary
- [x] 2.3 写入 `environment_components.metadata`，保留原始文件名、路径摘要、owner package 和查询工具信息
- [x] 2.4 确保 provider 查询失败不会阻断基础快照，并将失败原因写入 `raw_snapshot.parseWarnings`
- [x] 2.5 补充 x86 和 RISC-V provider 采集单元测试，覆盖正常流程、工具缺失和查询失败

## 3. RISC-V 仓库 metadata 与 provides 查询

- [x] 3.1 在 RISC-V 仓库候选查询前增加受控 metadata refresh 或 metadata 可用性检查
- [x] 3.2 为 dnf/yum repoquery 增加 timeout、低 retry、skip unavailable 和错误摘要记录
- [x] 3.3 增加基于库名和 normalized query pattern 的定向 whatprovides 查询
- [x] 3.4 将 repository metadata 状态、repoquery 状态和 provides 状态写入 `raw_snapshot.repositories` 或等效 summary
- [x] 3.5 补充 metadata refresh 成功、DNS/404/timeout 失败、repoquery 缺失和 provides 缺失测试

## 4. 架构归一化候选

- [x] 4.1 实现库名、路径和包名的架构 token 识别，覆盖 `x86_64`、`amd64`、`x64`、`riscv64` 等常见形式
- [x] 4.2 为源侧库生成 normalized library name、query patterns 和 package candidates
- [x] 4.3 在 metadata 中记录原始值、normalized 值、候选来源和 confidence 基础信息
- [x] 4.4 补充同名不同架构、架构 token 位于路径、文件名、包名后缀的 edge case 测试

## 5. SBOM 分析器匹配增强

- [x] 5.1 扩展 analyzer 输入解析，兼容 provider metadata、normalized names、query patterns 和 repository evidence 状态
- [x] 5.2 调整匹配优先级：exact package/provider > exact provides > normalized package > normalized library > weak name match
- [x] 5.3 在 replacement candidate evidence 中输出匹配来源、原始值、normalized 值、provider 证据和 confidence
- [x] 5.4 当仓库 metadata 或 provides 不完整时输出 warning，避免把证据缺失误判为无替代包
- [x] 5.5 补充 analyzer 测试，覆盖 owner package 命中、whatprovides 命中、normalized 命中、弱匹配降级和无证据场景

## 6. Java runtime 集成

- [x] 6.1 更新 `SbomAnalysisRuntimeService` 导出 analyzer input，包含 provider metadata 和 repository evidence 状态
- [x] 6.2 确认 SBOM 结果导入不会暴露服务器真实路径、远程敏感路径或凭据内容
- [x] 6.3 确认历史快照缺少 provider metadata 时仍能执行分析并输出低置信度 warning
- [x] 6.4 补充 Java runtime 单元测试，覆盖 provider metadata 导出、仓库证据不完整和历史快照兼容

## 7. API E2E 与真实验证

- [x] 7.1 更新 API E2E，用构造快照验证 provider evidence 和 normalized evidence 可在 SBOM 详情/组件结果中体现
- [ ] 7.2 在可用 x86 与 RISC-V 环境上实际运行环境采集，记录 owner package、repo metadata、whatprovides 和 warning 结果
- [ ] 7.3 使用采集结果运行 SBOM_ANALYSIS，确认目标仓库候选不再因 metadata 未准备而稳定为空
- [ ] 7.4 清理 E2E 和真实验证产生的测试数据，保留必要的非敏感记录文件

## 8. 文档与校验

- [x] 8.1 更新 `backend/docs/API_DESIGN.md` 或开发说明，记录 provider evidence、confidence 和 repository warning 的含义
- [ ] 8.2 运行 Maven 相关单元测试、分析器测试和 API E2E
- [x] 8.3 运行 `openspec validate --all`，确认 change 可进入 apply
