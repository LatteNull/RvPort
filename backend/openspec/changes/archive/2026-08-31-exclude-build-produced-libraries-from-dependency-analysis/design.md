## Context

当前构建验证 wrapper 会在用户构建前后采集 ELF manifest，并输出：

- `RVPORT_OBSERVATION repositoryBundledElf`: 构建前已存在的仓库内 ELF/SO。
- `RVPORT_OBSERVATION buildProducedElf`: 本次构建后新增的 ELF/SO。
- `RVPORT_OBSERVATION elfNeeded`: ELF 的动态依赖。
- `RVPORT_OBSERVATION elfSoname`: 共享库自身声明的 SONAME。
- `RVPORT_OBSERVATION resolvedNeededLibrary`: `NEEDED` 动态库在 source 环境中的解析结果。

`test2` 的真实数据表明，`build/libcjson.so.1.7.19` 和 `build/libcjson_utils.so.1.7.19` 是本次构建产物，但依赖分析仍然把它们的 SONAME 和其他本次构建产物对它们的 `NEEDED` 关系保存成外部依赖结果。这会把项目内部链接关系误判成目标环境缺失依赖。

## Goals / Non-Goals

**Goals:**

- 基于 `buildProducedElf` 建立本次构建产物路径集合。
- 从本次构建产物中提取自产共享库 SONAME 集合。
- 跳过本次构建产物自身的 `elfSoname` 依赖结果。
- 跳过任意 ELF 对本次构建产物 SONAME 的 `elfNeeded` 依赖结果。
- 保留本次构建产物对外部系统库的依赖分析，例如 `libc.so.6`、`libm.so.6`、`libgcc_s.so.1`。
- 保留仓库原本携带 ELF/SO 的分析能力。

**Non-Goals:**

- 不改变构建 wrapper 的 ELF 采集输出格式。
- 不引入新的数据库字段或 API。
- 不做跨项目、跨构建目录的历史产物识别。
- 不把所有 `build/` 路径粗暴排除，因为仓库原本可能包含构建目录或 vendor 产物。

## Decisions

1. 使用 `buildProducedElf` 作为唯一强证据

   分析器应解析 `RVPORT_OBSERVATION buildProducedElf`，而不是按路径前缀判断。原因是路径规则容易误伤，例如仓库中本来就有 `build/third_party/libfoo.so`。

2. 先建立构建产物 SONAME 集合，再处理 `elfNeeded`

   处理流程应分两层：

   ```text
   buildProducedElf path set
          │
          ├─ elfSoname(path, soname)
          │      └─ if path is produced => producedSonames.add(soname)
          │
          └─ elfNeeded(any path, needed)
                 ├─ if needed in producedSonames => skip
                 └─ else analyze as external dependency
   ```

   这样可以覆盖 `build/tests/foo` 依赖 `build/libbar.so` 的情况，即使 `foo` 自身也是构建产物，也不会影响它对系统库的外部依赖分析。

3. `resolvedNeededLibrary` unresolved 不能单独说明是外部依赖

   对 `libcjson.so.1` 这种本项目构建出的库，`ldconfig` 查不到是正常的，因为它不在系统库缓存中。若该 SONAME 已由本次构建产物声明，则 unresolved 不应升级为 `CRITICAL`。

4. 使用构建输出作为 marker 缺失时的补充证据

   真实 `test2` 数据中存在一种降级形态：远端构建目录残留导致 wrapper 没有输出 `buildProducedElf`，但构建日志中仍有 `Linking C shared library libcjson.so`。这类构建动作日志可以作为自产共享库名称的补充证据，用于过滤 `libcjson.so.1` 和 `libcjson.so.1.7.19` 这类派生结果。该逻辑只识别明确的 shared library 链接输出，不按目录前缀过滤。

5. 测试覆盖必须包含真实问题形态

   单元测试需要模拟：

   - 本次构建生成 `build/libcjson.so.1.7.19` 并声明 `libcjson.so.1`。
   - 本次构建生成的测试程序 `NEEDED libcjson.so.1`。
   - 同一测试程序仍 `NEEDED libc.so.6` 或 `libm.so.6`，这些外部库必须保留。

## Risks / Trade-offs

- [Risk] 某些项目构建产物 SONAME 与系统库 SONAME 同名，可能导致真实外部依赖被过滤。
  Mitigation: 只在本次构建产物明确声明相同 SONAME 时过滤；这是当前构建内部库优先的合理假设，且 evidence 中仍可通过构建日志审计。

- [Risk] 如果构建 wrapper 没有输出 `buildProducedElf`，过滤不会生效。
  Mitigation: 保持现有降级行为，不阻断依赖分析；单元测试覆盖有/无 `buildProducedElf` 两种路径。

- [Risk] 只过滤 SONAME 可能漏掉没有 SONAME 但通过文件名被链接的自产 `.so`。
  Mitigation: 对 build-produced shared object 同时索引声明 SONAME 和文件名 stem，例如 `libfoo.so.1.2.3`、`libfoo.so.1`、`libfoo.so` 的可归一化形式。

## Migration Plan

- 无数据库迁移。
- 修改依赖分析器后，已有历史依赖分析结果不会自动重写。
- 用户重新运行依赖分析后，新结果会排除本次构建产物派生的误报。
