# 分类与静态评估

[English](classification-assessment-design.md) | 简体中文

本工具只做静态分析。它不会编译项目、运行测试、调用 Make/CMake/Meson/CTest/RPM，也不会访问网络。

## 决策层次

1. Test Asset Analyzer 从 CTest、构建 target、RPM `%check` 和源码关系中识别测试；路径或文件名看起来像测试时只记为 candidate。
2. Test Selection Analyzer 在既有 Evidence Graph 中连接架构 selector、test target、test source 和依赖；selected、inactive、not_selected 必须有完整 proof，缺失或冲突保持 unknown。
3. Migration Classifier 保留原 Observation，并将根因分类为 blocking、actionable non-blocking、guarded/inactive、hint 或 unknown。unknown 的优先级最高。
4. Migration Assessor 分别归约输入完整性、目标可达性、x86 依赖、RISC-V/通用替代、测试选择/覆盖和打包约束，再按保守状态格产生项目状态。

枚举名称命中本身永远只是 candidate：孤立或未决选择为 unknown/non-actionable；绑定完整且闭合到真实 x86 依赖、但目标选择未知时为 actionable non-blocking；只有静态证明 RISC-V 选择该 x86 路径时才 blocking，静态排除时为 guarded inactive。unknown 会降低 readiness，零 blocker 不能反推 ready。

## Readiness 限定

`riscv_ready` 只表示当前静态输入范围完整、存在可证明的 RISC-V/通用路径、没有 blocker/unknown，且适用实现存在静态可证明的测试关系。它强制携带 `staticScopeOnly=true`、`compiled=false`、`testsExecuted=false`，不表示真实编译成功或测试通过。

## 兼容边界

默认输出 schema 2.0，显式选择 schema 1.0。V2/V1 直接读取同一 snapshots。qualification 使用相同分析阶段和 no-op Projector，不写报告。Legacy/YAML 不参与当前分析管线。
