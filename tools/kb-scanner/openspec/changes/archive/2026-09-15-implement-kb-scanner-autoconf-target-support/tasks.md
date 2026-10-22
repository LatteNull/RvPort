## 1. 收敛范围与基线

- [x] 1.1 按后端零改动约束收敛 proposal/design/specs/tasks，撤回新快照协议/CLI/source registry，保持现有输入与 V2 schema。
- [x] 1.2 冻结 scanner、镜像、两份 compiler JSON、V1/V2 schema 与测试基线，建立最小人工 oracle 和模块 unit inventory。

## 2. 正式输入与有界前端

- [x] 2.1 正式发现 config.guess，安全读取已授权工作区 Autoconf 文件，预算/异常/逃逸均有隔离单元测试。
- [x] 2.2 实现 scanner-owned AST lowering，保留真实 byte span；fake parser 单元与真实 grammar 组件分开。
- [x] 2.3 实现有界字符串、变量、正确 uname -m 与未知目标环境隔离，补正常/边界/异常单元。
- [x] 2.4 实现 case first-match/模式、if/嵌套、未知备选与预算，补 wildcard 拒绝/遮蔽/多 case/未知传播单元。
- [x] 2.5 实现输出/exit/规范化以及有界辅助调用参数结果传播，补空输出/失败/guess-sub 链和安全单元。
- [x] 2.6 实现 M4 无括号/多行字面宏、AUX_DIR 与配置单元/辅助文件绑定，补动态/冲突/缺失/多项目单元。

## 3. 正式图与兼容结果

- [x] 3.1 将 Autoconf 事实隔离于旧关键词式 gap 推断，专用 analyzer 保留事件/proof/digest/使用边界，补 fake snapshot 单元。
- [x] 3.2 接入既有 detector/classification：拒绝与 unknown 分开，局部不升级 blocker/ready，原始事实保留；补单元。
- [x] 3.3 验证原 V2/V1 schema 不变、已有节点/字段承载证据、±20/高亮及成对建议，补必要投影单元和合同。

## 4. 真实回归与质量门禁

- [x] 4.1 固定 GNU 脚本来源/哈希及真实 Autoconf 输入，人工 oracle 逐项审校，禁执行项目脚本。
- [x] 4.2 独立容器运行 source-only/compile-database-only、缺失/动态输入和安全/预算组件与性能记录。
- [x] 4.3 完整 AVX/RPM/枚举/候选/原生崩溃/源码链/双语/V1/V2 回归，记录 Autoconf 有意差异，复核 schema/知识哈希。
- [x] 4.4 整体与所有受影响模块隔离 unit 行/分支≥90%，未加载源码纳入分母，排除/不适用如实记录。

## 5. 文档与交接

- [x] 5.1 更新支持矩阵与 Autoconf 边界文档，明确后端零改动、无新参数、远端不可见输入不作证明。
- [x] 5.2 完成 verification.md 的容器命令、测试/覆盖/统计范围/持久报告、人工与差异审校。
- [x] 5.3 OpenSpec 严格验证、文档/格式和范围检查通过；全部任务通过后仅交接同步归档命令，不自动执行。
