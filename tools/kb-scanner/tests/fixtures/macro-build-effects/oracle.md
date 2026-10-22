# 宏构建作用人工真值

此文在实现前编写，不由 scanner 输出生成。样例只用于静态分析，故意不提供可执行项目或要求真实 intrinsic 类型检查。`kernel.cpp` 两份文本相同，4 行实参 `_mm256_add_epi32` 从第 41 列开始（结束列 57，半开区间）；条件位于 3 行，别名定义在 2 行。初稿列号经原始行 IndexOf/Length 核查修正为 41/57；后续仍须以字节切片断言复核，不能为迁就记录改坏实现。

| 编号 | 输入/变体 | 人工期望 |
| --- | --- | --- |
| M1 | make/Makefile 1 行 include flags.mk，2/3 行 NAME/DEFINES，5 行 recipe | `-D` 在 flags.mk:1，名字在 Makefile:2；两来源通过变量引用进入 kernel.cpp 的编译使用实例，`$<` 为 kernel.cpp，`$@` 为 kernel.o |
| C1 | cmake/CMakeLists.txt 2 行定义，经 4 行 link 到 3 行 kernel 目标 | api 的 INTERFACE 定义只传播给 kernel；不能证明 api 自身编译 kernel.cpp |
| P1 | 两份 kernel.cpp 与 wrapper.h | 条件为真，OUTER→INNER→fn 的三个实参逐位置对应，终端引用来源为调用实参，不是替换 token `fn` 的伪位置 |
| N1 | M1 移除 recipe 中 DEFINES 引用 | 变量事实保留，不证明 USE_AVX2 启用 |
| N2 | 两个 target/TU 一个 -DUSE_AVX2=1，一个 -UUSE_AVX2 | 头文件位置可共享，但作用实例不合并；第一处条件真，第二处假 |
| N3 | C1 再链接独立 api2，提供 USE_AVX2=0 | 冲突 unknown，不能按 target/文件/命令排序选择 0 或 1 |
| N4 | 未知 if/else 分别定义 A=1/A=1 或 A=1/A=0 | 前者合流确定且保留双来源，后者 unknown；无 else 要纳入没有分支执行的路径 |
| N5 | define A B，B 使用前后从 1 改为 0 | A 使用时晚绑定；undef B 后不得沿用旧值 |
| N6 | false 分支中的 undef/include/动态构造 | 不改变可达环境；未知可达 include 则不能沿用旧确定状态 |
| N7 | 两次包含无 guard 头文件且中间改变宏 | 分别处理；不得按文件去重；环终止且记录预算/断点 |
| N8 | OUTER 接收普通函数；参数仅作为数据或没有被使用 | 不借用另一调用的 x86 证明；命名不证明通用实现等价 |
| N9 | #/##/变参/递归/模板逗号/畸形调用 | 保留原始事实及明确 unknown/partial，不宣称完整展开 |
| N10 | shell/eval/动态 include、模式规则、target-specific/response file | 不执行，不借用失效前变量形成确定作用证明 |
| N11 | 同一文件 compdb 观察为 x86，目标分析为 RISC-V | 两种 provenance 隔离；观察成功不证明目标 selected |
| B1 | 人工降低事件/token/include/新增边/查询预算 | 原 fact 保留，明确截断，不能用不完整证明降低 confirmed x86 风险 |

每个正例检查来源行列、引用有效性、配置身份和每段真实边；V2 检查默认 20/20、highlight、无 classification/assessment，V1 检查既有字段。反例不可仅以 finding 数量作为断言。语义期望后续细化到可执行用例，但不得从实现结果反推真值。
