# 浮点扫描器架构与维护

[English](architecture.md) | 简体中文

## 输入和处理

`Scan Request → profile/输入校验 → C/C++ TU 规划 → canonical AST facts → 可选共享 BC/IR facts → AST↔IR evidence → 规则 assessment → suppression → 结果 V2 投影`。

只规划 C11、C17、C++17、C++20。Clang/LLVM 锁定 21.1.8；其他语言以双语 `unsupported_language` 排除，不计入 C/C++ 分母。输入在编译数据库与显式 TU 间二选一，并固定 source/target profile。

BC 来自上游终态 artifact；扫描器不生成 BC。路径、摘要、版本、source revision 和 member 身份校验失败必须显式降级或失败；禁止按同名文件猜测对齐。规则仅消费 canonical facts、版本化 profile、evidence 与 build context，不直接读取 Clang 内部对象。

## 规则与版本

十条规则及其证据边界集中维护在 [README](../README.zh-CN.md)。请求 schema 1.3–1.4 默认启用十条规则，1.0–1.2 保留原四条；`rules.enabled=[]` 表示 factsOnly。请求版本与输出 `schemaVersion: 2.0` 是两个不同合同。

AST 候选、IR 事实和已证明差异分别表达。类型不可恢复、间接调用、未知 libm/运行环境、失败及预算截断保留 unknown/failed 分母；零 Finding 不表示数值等价。工具不执行被分析程序，不自动给出业务容差，也不代替实际迁移测试。

## 结果与维护

Finding 包含事实、结论、occurrence 与 evidenceChain；稳定身份不依赖绝对工作区路径。双语步骤说明见 [证据步骤](evidence-step-descriptions.zh-CN.md)。suppression 必须携带规则、相对路径与理由；带 `expires_on` 时显式提供 `policy_as_of`，到期当日仍有效，过期 Finding 恢复可见。

缓存只保存 facts/evidence，不能缓存最终 finding 或 suppression。版本和源码位置语义变化必须使旧缓存正常 miss，不能原地补字段。详见 [缓存](analysis-cache.zh-CN.md)与 [共享 BC](shared-bitcode-consumer.zh-CN.md)。

## Docker 验证

在 README 的开发容器中执行 `make verify`：lint、类型检查、全 Python 单元/契约覆盖、人工真值验证及 C++ 覆盖；发布验证使用 `make verify-release` 增加 benchmark。真实 Clang 集成另执行 `make integration`，不能计入单元覆盖。

整体及受影响模块行/分支均至少 90%，Python 统计包含未导入源码；C++ 统计包含 worker 自有实现。输出位于容器 `artifacts/coverage/`。
