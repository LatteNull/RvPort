## ADDED Requirements

### Requirement: 以真实协议断言覆盖工具结果修复
本工具涉及的自有代码 SHALL 同步具备正常、边界、异常和 partial/unknown 单元测试。适配器合同测试 MUST 调用真实 schema/reference validator，不得同时 mock 生产请求和校验为成功；进程 I/O 可注入。离线真实 worker 集成 SHALL 独立运行，不替代单元测试或混入其覆盖 profile。

#### Scenario: 多 TU 与特殊文件名回归
- **WHEN** 测试 TU/artifact 反序、重复同值/冲突及 thread-0/thread-entry 共存
- **THEN** 实际 validator 接受正确请求、拒绝冲突，发布分析选择正确 P3 依赖

#### Scenario: 支持与降级场景对照
- **WHEN** 测试普通循环负例、线程/原子/同步候选、AST-only、IR-only、partial 混合、缺摘要、零成员、profile 和多标准组
- **THEN** 断言候选准入、证据边界、分母、诊断及完整性，不只检查退出码或文件存在

#### Scenario: 工具投影与历史版本回归
- **WHEN** 测试 2.0/3.0、未知版本、frontier-only、主路径引用、截断及冷/热缓存
- **THEN** 本工具的校验、投影、计数和不可变制品符合合同，不把外部页面或报告业务当成本工具已验证功能

#### Scenario: 多 Scope 并发发布
- **WHEN** 某个 Scope 索引/缓存时另一 Scope 正在写任务目录或原子写入临时文件
- **THEN** 只读取已发布产物，不因临时文件消失而丢弃当前 Scope 结果

### Requirement: 实际执行工具全量与受影响模块覆盖门槛
实施交付前 SHALL 在 Docker 中运行本工具全部自有 Python/C++ 单元覆盖；整体、每语言和受影响模块的行及可用分支覆盖率 MUST 至少 90%，现有更严格逐模块门槛保持。统计 MUST 纳入未加载源码、可执行头和自有质量入口，不得缩小范围或混入集成 profile。外部项目的质量结果不得替代本工具门槛。

#### Scenario: 整体达标但模块不足
- **WHEN** 整体超过 90% 但某个受影响模块的行或可用分支为 89%
- **THEN** 自动门槛非零，验收未完成，不用变更行或平均百分比替代

#### Scenario: 文件未被单元加载
- **WHEN** 自有可执行源码未被单元测试加载
- **THEN** 仍纳入分母，不通过排除文件或降低阈值取得通过

#### Scenario: 历史缺口需要扩大范围
- **WHEN** 全量门槛失败且补齐需要超出当前 root 或无关大规模改造
- **THEN** 记录差距并停止范围外修改，不能自行扩大实施边界或标记通过

### Requirement: 工具 Docker 验证隔离且遵守文件边界
编译、安装、代码生成、单元和集成测试 SHALL 在独立 Docker 环境中按顺序执行，限制 CPU、内存和编译并发，使用专用卷。宿主机新写入文件 MUST 位于当前工具 root 内；不得连接真实 SSH、已有部署数据库或用旧分析结果代替当前源码验证。

#### Scenario: 执行真实组合验收
- **WHEN** 使用 Docker 预生成的合成 BC 和源码夹具运行统一入口
- **THEN** 验证诊断、候选、证据引用、跨 Scope 和 partial 语义，不运行被分析程序

#### Scenario: 必需检查失败或受阻
- **WHEN** 本工具 Docker 构建、单元、集成或覆盖检查失败/受阻
- **THEN** 如实记录并保留未完成，不用历史报告冒充本次通过

### Requirement: 验证证据可复现且责任范围明确
验收 SHALL 记录源码/镜像/工具版本、精确命令、测试结果、行/分支 covered/total、范围、排除理由和报告位置；跨语言合计按命中数和总数加权。公开夹具 MUST 为合成或授权脱敏数据。真实源码、日志、凭据和审计包不得进入公开源码。外部任务移出范围 MUST 明确记为移交，不能记为本工具已完成。

#### Scenario: 纯 artifact 范围修订
- **WHEN** 只修改 proposal/design/specs/tasks 或规则文本
- **THEN** 校验内容、链接、边界和 OpenSpec，保留历史测试日期，不声称重新执行代码测试或新增覆盖率结果

#### Scenario: 外部消费问题移交
- **WHEN** 输出合同需要前端或后端配合
- **THEN** 仅给出非规范性接口影响和交接，由对应 root 管理实现，不在本 change 留跨 root 实施任务