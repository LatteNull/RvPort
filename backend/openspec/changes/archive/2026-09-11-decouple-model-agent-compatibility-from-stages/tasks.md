## 1. 数据库与生成代码

- [x] 1.1 新增前向 Liquibase changeset，删除 `model_profiles.last_test_compare_compatible`、`model_profile_agent_probe_results.test_log_compare_compatible` 和 `kb_ai_extension_compatible`，且不修改已执行的历史 changeset
- [x] 1.2 运行 Liquibase 验证数据库迁移成功，并检查阶段绑定表及通用 probe 历史表数据保持可用
- [x] 1.3 使用项目 jOOQ 生成脚本重新生成并提交元数据，确认生成代码不再包含已删除列

## 2. 通用模型与 Agent Runtime 探测

- [x] 2.1 将 probe 名称和中性 fixture 重构为 Agent 模型响应、workspace 读取、workspace 写入与基础 JSON 解析检查
- [x] 2.2 实现通用 workspace 写入闭环，校验输出文件存在、JSON 合法和 marker 正确，并在成功、失败、超时后清理临时目录
- [x] 2.3 从兼容性执行路径删除测试比较和 KB AI 扩展的 prompt、fixture、检查及聚合判断
- [x] 2.4 令 `agentCompatible` 只由通用检查计算，并保持多 Runtime 异步执行和单 Runtime 失败隔离
- [x] 2.5 确认 probe 创建、执行与查询不读取 `model_stage_assignments`，不同阶段绑定不改变同一 Profile 与 Runtime 的检查集合

## 3. 持久化与 API 契约

- [x] 3.1 更新 probe 结果模型、repository 和 service，停止读写阶段兼容性列并保留 Profile 与 Runtime 组合维度的最近结果查询
- [x] 3.2 更新模型 Profile 列表、详情、probe run 和 probe result DTO，移除所有阶段兼容性字段并返回通用 checks 与聚合状态
- [x] 3.3 保持 `model_stage_assignments` 查询、保存及实际阶段运行解析逻辑不变，确认阶段输出失败不会改写通用兼容性结果
- [x] 3.4 更新中文 API 设计、数据库设计和 E2E 覆盖说明，明确 breaking 字段变化和阶段契约边界

## 4. 单元测试与覆盖率

- [x] 4.1 补充通用 probe 正常流程单元测试，覆盖模型响应、workspace 读取、workspace 写入、JSON 校验和聚合成功
- [x] 4.2 补充异常流程单元测试，覆盖 Runtime 不可用、进程非零退出、缺失输出文件、无效 JSON、marker 不匹配、超时和敏感信息脱敏
- [x] 4.3 补充边界条件单元测试，覆盖多 Runtime 部分成功、重复或空 Runtime ID、临时目录清理、历史 checks 和未绑定或多阶段绑定场景
- [x] 4.4 更新 repository、service、controller 与 DTO 单元测试，断言阶段字段不再写入或返回，且阶段任务失败不污染兼容性记录
- [ ] 4.5 将覆盖率统计纳入未被测试加载的项目自有源码，运行可重复的 Maven 单元测试与覆盖率命令；项目整体和本次受影响模块行覆盖率均达到至少 90%，工具提供分支覆盖率时两者分支覆盖率也达到至少 90%

  当前实测：整体行/分支覆盖率为 54.53%/44.67%，`codexprovider` 为 70.00%/63.04%，`modelprofile` 为 44.95%/30.98%。覆盖率门槛已接入 Maven，但历史测试缺口尚未补齐，因此本项保持未完成。

  2026-09-11 用户确认本次暂缓补齐覆盖率，作为后续独立工作处理；本项不视为质量验收完成。
- [x] 4.6 保存并报告覆盖率报告位置、统计范围和排除项；仅允许排除第三方或自动生成代码，不得排除项目自有业务逻辑

## 5. 集成与交付验证

- [x] 5.0 修正后端镜像中的 Codex CLI 安装，显式安装匹配版本的 Linux x64 平台依赖，并增加 Agent CLI 构建期版本自检
- [x] 5.1 更新模型管理 API E2E，覆盖多 Runtime 通用 probe、活跃 run 恢复、阶段无关性、失败隔离、异常输入和权限边界
- [x] 5.2 运行 OpenSpec 校验、完整 Maven 测试和模型管理 E2E，确认无测试失败且 API 响应中不存在阶段兼容性字段
- [x] 5.3 重新构建并替换 backend 与 backend-worker 容器，使用实际 API 创建 probe run 并核对数据库、轮询结果、日志与容器健康状态
