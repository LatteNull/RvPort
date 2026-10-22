# 测试内容人工 oracle

此文件为实现前手写，不由扫描器输出生成。最小 CMake fixture 的注册在源码中；不执行项目构建/测试。

- direct.c：main 的 assert 参数含两个 intrinsic；标准断言是否生效需独立宏/头来源证明，不能保证断言通过。保留 intrinsic 及实际断言位置。
- helper.c：unused 内的两个 intrinsic 不可被解释为 main 调用或验证过。DISABLED 仅禁止注册测试运行，目标源码的编译成员仍存在，不能撤销其编译风险。
- guarded.c：仅在明确 x86_64 构建分支出现；目标 RISC-V 不应选择该 target，注册与编译分别解释。
- 普通 value==42 / sizeof(long)==8：不得独立产生 x86 执行问题。
- codec 的 X86_FILTER 数据断言：保留事实，完整纯数据用途才排除分类，否则 unknown。
- 一跳调用/局部单次初始化允许追溯；未调用、重写、逃逸、runtime 条件、复杂框架、重载与跨 TU 不补造完整证明。
- NDEBUG：只影响确认为标准 assert 的参数求值，不影响断言外依赖。
- 相同源位置多配置分别保留；同一事实的测试语境不应重复计数。

## 固定资产

- Clang SHA-256：adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7
- GCC SHA-256：89775341ee880b13ac4f10a30558ff5d52875b25a3233114a5765601f0a9dad9
- libarchive：沿用 ../candidate-usage-performance/PROVENANCE.json，822 文件，commit c4cfba676d2b86d6a2a7c508cd90a75c4dfaa1d9，输入摘要 f52edca120bdcd98d6c3316a2c5a42c09e38a99fc2189fa07b33cd3eb85fd67c。旧 810 文件记录不改。
