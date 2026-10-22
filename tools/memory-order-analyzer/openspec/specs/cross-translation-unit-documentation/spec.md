# cross-translation-unit-documentation

## Purpose

规范跨翻译单元关联文档，区分包含、构建、符号、对象与线程关系，明确目标范围、候选/未知关系和增量失效边界。

## Requirements

### Requirement: Separate dependency layers

文档 SHALL 区分包含依赖、构建/链接依赖、函数调用、共享对象访问及线程同步关系，并用一个跨头文件与两个源文件的例子标明每种关系的证据来源；SHALL 说明依赖采集可与同配置的编译前端处理协同进行，而非必须先单独扫描全部源码。

#### Scenario: Two sources include the same header

- **WHEN** 两个源文件均包含声明函数和全局对象的头文件
- **THEN** 文档说明包含边本身不足以建立调用或共享访问边，需要从函数引用/定义和对象访问证据解析关联

### Requirement: Describe scoped symbol resolution and module organization

文档 SHALL 说明逐 TU BC、范围内符号索引和函数摘要的关联流程，以及限定范围 `llvm-link` 的可选用途；SHALL 覆盖内部/外部链接、C++ 符号、弱符号/COMDAT、静态库选择及动态库边界的限制，不声称链接 BC 自动解决所有跨文件关系。

#### Scenario: Internal symbols share a name

- **WHEN** 不同 TU 中存在同名 `static` 函数或对象
- **THEN** 文档保留模块身份，不将它们解析为同一个跨文件符号

#### Scenario: Modules belong to different executables

- **WHEN** 同一个项目包含多个可执行目标或不同构建变体
- **THEN** 文档按已知链接范围组织关联，明确禁止无条件把所有模块合并成一个程序

### Requirement: Expose unresolved and candidate relationships

文档 SHALL 区分已解析直接调用/全局引用、候选间接调用/别名和未知外部实现，说明函数指针、虚调用、动态加载及缺失库函数体会限制跨模块完整性；SHALL 说明调试信息提供源码映射但优化可能造成缺失或一对多映射。

#### Scenario: A call target has no available body

- **WHEN** 外部库只有声明，或间接调用无法确定唯一目标
- **THEN** 文档将其表示为外部摘要、候选或未知，不能用空影响或唯一猜测替代，也不能由此宣称全程序分析完整

### Requirement: Document layered incremental invalidation

文档 SHALL 分别说明头文件/源码、编译配置、符号/摘要和链接范围变化对 BC 与后续关联的失效传播，并明确这只是设计约束而非已实现缓存能力。

#### Scenario: A shared header changes

- **WHEN** 头文件被多个不同配置的 TU 实际包含
- **THEN** 文档说明对应 TU 的 BC 需要重新生成或验证，受影响摘要及其消费者需要更新，不能只重算与头文件同目录的源码
