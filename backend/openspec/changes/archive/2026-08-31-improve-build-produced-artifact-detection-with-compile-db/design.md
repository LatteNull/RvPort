## Context

依赖分析当前主要依赖构建前后 ELF manifest、`buildProducedElf`、`repositoryBundledElf`、`elfNeeded`、`elfSoname`、构建日志和目标环境 provider 查询。近期已经修复了一个实际问题：`test2` 项目中 `libcjson.so.1` 和 `libcjson_utils.so.1` 是当前项目构建产物，但在部分日志形态下会被识别成外部依赖。

现有修复使用 `buildProducedElf` 和 CMake `Linking ... shared library` 输出过滤自产库。问题是这些信号仍可能缺失：例如构建目录残留导致前后 manifest 不产生新增项，或链接日志格式不被识别。另一方面，构建验证已经可以保存 `compile_commands.json` 作为构建上下文 artifact。该文件能够提供源码文件、编译命令、object 输出和工作目录信息，适合用于增强构建产物归因。

## Goals / Non-Goals

**Goals:**
- 使用 `compile_commands.json` 建立项目源码到 object 文件的关系。
- 将 object 关系和现有链接/ELF 事实结合，辅助判断哪些 ELF/SO 是本次项目构建产物。
- 过滤确认属于本次构建产物的 `elfSoname` 和内部 `elfNeeded` 结果。
- 保留仓库原本携带的 prebuilt ELF/SO 作为依赖候选。
- 保持 API 结构稳定，不向前端暴露完整 compile database 或远端路径。

**Non-Goals:**
- 不为所有构建系统实现完整 build graph 解析器。
- 不把 `compile_commands.json` 本身、compiler flag 或宏重新展示为依赖结果。
- 不仅凭路径前缀、build 目录名或 object 文件存在就判定某个 SO/ELF 是构建产物。
- 不改变构建验证生成 compile database artifact 的存储模型。

## Decisions

### 1. compile database 作为归因证据，不作为唯一过滤依据

`compile_commands.json` 通常只记录编译命令，不稳定记录最终链接命令。因此它能证明“某个源码被编译成某个 object”，但不能单独证明“某个 `.so` 是这些 object 链接出来的”。

实现应从 compile database 中提取：
- `file`: 项目源码相对路径。
- `directory`: 编译工作目录的脱敏/归一化相对表示。
- `command` 或 `arguments`: 编译命令摘要。
- `-o` 输出 object 路径。

提取结果进入内部 `CompileObjectIndex`，用于后续和链接日志、strace 或 ELF 产物事实交叉验证。

### 2. 使用多信号确认 build-produced artifact

确认某个 ELF/SO 是本次构建产物时，优先级如下：

```text
buildProducedElf before/after manifest
        │ strongest
        ▼
link log / ninja / make explicit output
        │ strong
        ▼
strace linker exec/output relation
        │ strong when available
        ▼
compile_commands object -> project source relation
        │ supporting evidence
        ▼
mtime/path hints
        │ weak, never alone
```

推荐实现为一个内部归因器，而不是把规则分散到多个 `add*` 方法中：

```text
BuildArtifactOriginIndex
  ├─ producedPaths
  ├─ producedLibraryKeys
  ├─ repositoryBundledPaths
  ├─ compileObjects
  └─ evidenceByArtifact
```

依赖分析只消费判断结果：

```text
origin == BUILD_PRODUCED   -> 过滤自产结果
origin == REPOSITORY_BUNDLED -> 保留为依赖候选
origin == UNKNOWN          -> 保持现有降级行为
```

### 3. 对 repository bundled 保持保守

如果某个 ELF/SO 在构建前 manifest 中已经存在，应继续视作仓库原本携带的 prebuilt 制品，即使它路径在 `build/`、`out/` 或其他常见构建目录下。

只有在有更强证据表明它被本次构建覆盖或重新生成时，才允许标记为 `BUILD_PRODUCED`。该证据可以来自：
- manifest 中同一路径在构建后发生新增或内容 hash 变化；
- strace/linker 明确输出该路径；
- 构建日志明确链接生成该路径或其 library key，并且 compile object 证据能证明链接输入来自项目源码。

### 4. compile database artifact 使用受控读取

依赖分析可以从同一源码版本、同一 source/x86 构建运行中读取已保存的 compile database artifact。读取时需要沿用现有安全策略：
- 校验 artifact 属于当前项目、源码版本和成功构建运行。
- 限制解析大小和 entry 数量，避免大型 compile database 导致 worker 内存不可控。
- 只保存脱敏摘要和归因 evidence，不把完整命令或远端绝对路径写入结果。

### 5. 缺失 compile database 时不改变现有行为

没有 compile database、compile database 无效或 artifact 读取失败时，依赖分析应继续使用现有 `buildProducedElf`、链接日志、strace 和 ELF 事实。该能力是增强项，不应让原本可用的依赖分析失败。

## Risks / Trade-offs

- [Risk] compile database 不包含链接命令，单独使用会误判。
  Mitigation: 要求 compile DB 只能作为辅助证据，必须和 manifest、链接日志、strace 或明确产物事实组合。

- [Risk] 构建目录中存在历史残留，会把旧产物误认为本次产物。
  Mitigation: 构建前 manifest 中已存在的文件默认归为 repository bundled，除非有强覆盖证据。

- [Risk] compile database 很大，解析成本高。
  Mitigation: 复用 artifact 大小限制，并在归因解析阶段限制 entry 数量、字段长度和 evidence 大小。

- [Risk] 路径脱敏后影响 object/artifact 关联。
  Mitigation: 内部可使用受控归一化路径完成关联，对外只输出相对路径、hash 或摘要，不暴露服务器真实路径。

## Migration Plan

该 change 不需要数据库迁移。实现后，新依赖分析运行会使用 compile database 增强归因；历史依赖分析结果保持不变。

回滚时可以关闭 compile DB 归因路径，继续使用当前 `buildProducedElf` 和链接日志过滤逻辑。

## Open Questions

- 是否需要在构建 wrapper 中为 ELF manifest 增加 hash/mtime 字段，用于判断构建前已存在但被本次覆盖的同路径产物？
- 是否需要优先支持 `build.ninja` 的 `build <target>: ... <objects>` 图解析，以增强 object 到 artifact 的关联？
