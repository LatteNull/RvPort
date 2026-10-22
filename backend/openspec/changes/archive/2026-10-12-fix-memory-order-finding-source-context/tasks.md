## 1. 范围和回归基线

- [x] 1.1 确认 tools/memory-order-analyzer 特别允许范围，读取工具规范及现有位置/快照契约，固定正式风险与源码候选的缺片段回归样本。
- [x] 1.2 获取用户实例或记录其不可用限制，对照原始 JSON、数据库位置和详情原因码，建立 AST/IR 引用到源码位置的映射清单。

## 2. 工具位置和上下文

- [x] 2.1 实现受 scope/TU/编译上下文约束的位置解析，补齐 publication、advanced-atomic 及 discharged 投影，不修改风险判断。
- [x] 2.2 修复源码候选实际文件归属，处理项目头文件、宏 expansion/spelling、跨文件范围和不可用位置。
- [x] 2.3 按真实文件建立或复用哈希快照，保留多位置及步骤关联，实施 end-exclusive 高亮、安全校验与上下文预算。
- [x] 2.4 校验双语不可用说明、Schema、稳定 Finding 身份、occurrence 确定性及结果摘要；按既有版本策略处理结果缓存和发布版本。

## 3. 后端适配和规范

- [x] 3.1 核验导入关系字段与 detail 保真，完善既有详情 codeContext 的摘要、范围和不可用原因处理，不新增接口且不回填历史记录。
- [x] 3.2 同步工具 memory-order-finding-evidence-projection 和必要的 unified-project-analysis-entry 主规范及中文 doc，更新后端 specialized-finding-code-context 文档，确认继续复用现有制品归档登记。

## 4. 测试和交付验证

- [x] 4.1 补充工具正常、异常、边界独立单测，覆盖正式风险/候选/审计、多文件/宏/头文件、无调试信息、歧义、摘要错误、预算和身份稳定性。
- [x] 4.2 补充后端导入/详情独立单测，mock 外部连接返回值，覆盖版本绑定、权限、路径安全、空位置和 end-exclusive，并回归共用的浮点上下文行为。
- [x] 4.3 在 Linux Docker 执行后端和工具全量独立单测及覆盖率门禁；整体和受影响模块行/可用分支至少 90%，包含未加载自有源码，保存命令、排除依据和报告；未达标不勾选完成。
- [x] 4.4 运行真实 Clang AST-only/AST+BC fixture，验证项目头文件、宏与多位置；构建更新 API/worker，通过正式 API 完成扫描并对照 JSON、落库和详情源码文本及高亮，保留审计记录。
- [x] 4.5 严格校验 backend change 和工具受影响规范、文档链接及 Git 差异，记录真实实例复现范围与剩余限制，全部验收通过后才归档。

详见 [validation.md](validation.md)。后端项目整体按 Java + 全部 Python 资源脚本计数；
历史未修改 BC 生产脚本的单文件缺口没有排除。真实 API 此次为 AST_ONLY，真实 BC 位置
路径另用 Clang fixture 验证，不将远端 BC 失败记为成功。未归档、未提交。
