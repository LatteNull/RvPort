## 1. 设计范围评审

- [x] 1.1 对照 RvPort US21 评审 `docs/floating-point-precision-scanner-design.md` 的目标、非目标、C/C++ 首期范围和 x86→RISC-V 约束，并补齐需求追踪说明
- [x] 1.2 评审十类 finding code、source/target profile、canonical facts、证据来源、严重性、置信度与人工确认边界，确认不存在实现代码或自动修复范围
- [x] 1.3 将扫描语言范围明确收紧为仅支持 C/C++，统一 proposal、design、spec、测试矩阵和非目标表述
- [x] 1.4 新增 C/C++ 浮点精度扫描 roadmap，定义阶段依赖、交付物、准入/退出条件和每阶段质量门禁

## 2. 协议与失败语义评审

- [x] 2.1 校对版本化输入、双语输出、稳定 finding ID、确定性排序和原子写出设计，确保与 `scanner-io-contract` 规格一致
- [x] 2.2 校对 `complete`、`invalid_request`、`failed`、`partial`、`internal_error` 及退出码映射，并验证解析失败、unknown、预算耗尽和内部错误不会被表述为安全
- [x] 2.3 评审抑制、脱敏、路径边界和诊断聚合设计，记录仍需由后续实现 change 决定的集成问题

## 3. 测试与覆盖率设计验收

- [x] 3.1 建立需求到单元测试场景的评审矩阵，覆盖正常行为、边界条件、异常路径、unknown/unsupported、双语字段和确定性输出
- [x] 3.2 确认后续实现必须统计所有项目自有可执行源码，且项目整体与受影响模块的行覆盖率和分支覆盖率均至少为 90%
- [x] 3.3 确认第三方、自动生成文件等覆盖率排除项必须逐项记录理由，集成测试、端到端测试、编译和静态检查不得替代单元测试

## 4. 文档一致性验证

- [x] 4.1 检查 proposal、design、四份 capability specs、tasks 与 `docs/floating-point-precision-scanner-design.md` 的术语、状态、字段和范围一致性
- [x] 4.2 在工具目录执行 `openspec validate build-floating-point-precision-scanner --strict`，修复全部验证错误并保存最终检查结果
- [x] 4.3 确认本 change 只包含设计与规划文档，不包含生产代码、测试代码、schema、依赖或构建配置后，提交评审
