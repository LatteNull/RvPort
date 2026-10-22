## Why

demo-test1 的浮点扫描已有两条风险结果，但保存的 primaryLocation 和 occurrences 位置均为空，无法定位源码。当前扫描器要求 Clang 节点同时包含 file、line、col，无法处理合法的字段省略，需要恢复可靠的位置链路。

## What Changes

- 利用翻译单元、AST 文件上下文和源码字节偏移恢复可证明的位置，处理宏、头文件与起止范围，无法确定时保留空值。
- 修复聚合过程中主位置和关联位置可能遗漏或重复的问题，确保位置可追溯到直接证据。
- 经用户追加授权，修复浮点指针空值比较误报：比较操作必须依据标量操作数类型，不以类型名包含 float/double 判断。
- 经用户追加授权，在浮点/内存序现有 Finding 详情中内嵌代码上下文，按历史源码版本读取上下各 20 行并返回行号和高亮标记，不新增独立获取接口；前端由其他同事处理。
- 验证 v2 JSON、后端逐条入库、列表/详情和 HTML 的位置一致性，保持现有 API 与 schema v2。
- 同步工具自身的 spec 和中文设计文档，增加独立单测、真实 Clang 集成测试及真实项目 API 验证。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `floating-point-analysis-runtime`：增加可恢复源码位置、聚合位置完整性和端到端一致性要求。

## Impact

- 后端范围：浮点分析导入、响应映射及相关测试，仅按验证发现的实际缺口调整。
- 工具范围：`tools/floating-point-precision-scanner` 为本 change 明确申请的特别允许实现范围，主要涉及 facts、rules、result_v2、测试及工具 spec/docs；apply 时需明确该范围。
- 不修改前端、内存序工具，不引入服务依赖或数据库迁移；不伪造或覆盖历史运行的不可变结果，修复后新建扫描验证。
- Linux Docker 内执行单测和覆盖率，项目整体和受影响模块行/分支覆盖率均至少 90%，统计包含未加载自有源码，排除测试、fixture、第三方和生成文件并记录理由。
