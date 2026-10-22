## ADDED Requirements

### Requirement: 宏作用环境必须按 TU 调用时状态与可行分支合流
Analyzer SHALL 按 TU/configuration、include/definition 顺序与调用 occurrence 解析宏，区分 known defined、explicitly undefined、unknown/conflicting；源码中缺少定义 MUST NOT 单独证明 undefined。对象别名 SHALL 按使用时环境求值，支持受限整数、括号、defined、!、&&、||、==、!= 条件，超出语义边界 SHALL unknown。if/elif/else SHALL 按 first-match 和可行路径分别推进，合流包括未执行任何分支的路径。

#### Scenario: 对象宏别名晚绑定
- **WHEN** A 的 replacement 为 B，B 在 A 的两个使用点之间被重定义或取消
- **THEN** 两处 A SHALL 分别使用当时的 B 状态及来源，不能缓存为定义 A 时的值
- **AND** 别名循环或未知外部 B SHALL 保持 unknown

#### Scenario: 相同分支状态与冲突状态
- **WHEN** 未知条件的所有可行分支均定义同值宏，或其中一支定义不同值/不定义
- **THEN** 前者 SHALL 合流为可证明的相同状态并保留所有来源，后者 SHALL 保留 unknown/conflicting
- **AND** inactive 分支的 define/undef SHALL 不改变可达环境

#### Scenario: 定义存在性与布尔条件
- **WHEN** 已证明 `-DFEATURE=0` 且源码测试 `defined(FEATURE)`、`FEATURE` 或与其他条件组合
- **THEN** SHALL 区分已定义性和数值真假，使用受限表达式语义及明确来源
- **AND** 未知整数行为或不支持表达式 SHALL 不被强制求值

#### Scenario: 重复 include 与未知 include
- **WHEN** 同一头文件在不同宏环境下重复包含，或者遇到未解析的 include
- **THEN** Analyzer SHALL 按当前 TU 状态处理重复包含，仅在完整 guard/pragma once 证明下跳过
- **AND** 未知 include 的潜在宏副作用 SHALL 使相关确定性失效，不能简单沿用旧状态

### Requirement: 固定参数宏传递必须绑定真实调用和终端事实
Analyzer SHALL 对固定参数、完整边界、无 #/##/变参的受支持宏建立实参→形参引用→replacement/嵌套调用的可核查关系，按调用时可见定义处理标识符、整数及其括号包装。终端 x86 符号 SHALL 通过正式 Knowledge/Fact/Observation 路径识别，宏定义存在或参数名称相同 MUST NOT 构成实际调用证明。

#### Scenario: 实参提供 intrinsic 名称
- **WHEN** `OUTER(_mm256_add_epi32, x, y)` 经固定参数包装最终调用该实参
- **THEN** scanner SHALL 保留实参位置、参数声明/引用、各层调用/定义和终端知识来源的关系
- **AND** 不得因初始 replacement 仅为参数名而遗漏已证明的 x86 终端

#### Scenario: 不同调用传入不同终端
- **WHEN** 同一包装分别接收 x86 intrinsic 和普通函数名
- **THEN** Analyzer SHALL 保持每次调用的参数及作用身份，不把一处 x86 证明复制到另一处
- **AND** 普通函数的通用性或 RISC-V 等价性 SHALL 不因命名被确认

#### Scenario: 不支持展开或没有调用
- **WHEN** 参数绑定存在歧义、递归、变参、token pasting、stringification 或宏未被调用
- **THEN** 原事实 SHALL 保留，仅提供局部链及对应断点，不构造完整执行证明

### Requirement: 宏作用图必须按需求复用索引并独立计量预算
Analyzer SHALL 使用原始 facts、宏调用和构建绑定确定需求，按 TU/configuration 复用有序事件及作用索引，不逐 Finding 全项目重扫。每 TU 事件 100000、宏展开深度 32、单调用展开 token 4096、扫描新增作用关系 100000 SHALL 作为本轮硬上限；继承旧图不计入新增关系额度。现有源码链 depth=16/visited=256/paths=32 SHALL 保持，所有截断 SHALL 有稳定原因及计数。

#### Scenario: 新终端尚未形成 Finding
- **WHEN** 宏实参经展开才能发现 x86 终端，而初始 detector 尚无对应 Finding
- **THEN** 需求选择 SHALL 仍能从宏调用事实启动该有界分析，不以已有 Finding 为唯一入口

#### Scenario: 同名宏跨 TU 和配置
- **WHEN** 两个 TU 使用同名头文件宏但环境或构建参数不同
- **THEN** 状态缓存、关系及 proof 消费 SHALL 逐 TU/configuration 隔离
- **AND** baseline/default provenance MUST NOT 充当跨配置拼接 complete 路径的通配证明

#### Scenario: 查询和生成耗尽预算
- **WHEN** include 环、展开或查询达到硬上限
- **THEN** scanner SHALL 保留原始 Fact/Evidence 与已验证局部关系，记录实际使用量/上限并返回 partial/unknown
- **AND** 不完整作用证明 MUST NOT 降低已有 confirmed x86 结论，亦不得冒充 non_execution_data 或替代实现证明
