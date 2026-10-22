## Context

后端 `overallStatus` 的合法值为 `EQUIVALENT`、`DIFFERENT_ACCEPTABLE`、`DIFFERENT_BLOCKING` 和 `INCONCLUSIVE`，前端映射仍使用 `CONSISTENT` 与 `INCONSISTENT`。

## Goals / Non-Goals

目标：前端完整识别当前后端枚举并显示中文语义。非目标：修改后端枚举或重新判断测试结论。

## Decisions

四种后端枚举分别展示为“结果等价”“差异可接受”“阻断性差异”“暂无法判断”，并同步驱动成功、警告、错误和中性标题。旧枚举继续作为历史数据兼容项。

## Risks / Trade-offs

未知的新枚举仍会回退显示原始值，便于发现契约变化。
