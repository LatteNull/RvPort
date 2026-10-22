## Context

原展示模型优先解析 primaryPath，组件还根据 breaks 与 budget 生成额外提醒。

## Goals / Non-Goals

目标：后端返回几个步骤就展示几个，按返回顺序呈现状态与原因。
非目标：修改后端数据、隐藏原始诊断数据、调整位置说明或代码上下文截断提示。

## Decisions

去掉展示模型的 primary/fallback 模式，仅保留完整 steps。移除判断依据区域的附加完整性提示及废弃样式；保留后端证据链状态和 step 状态，不自行推断结论。

## Risks / Trade-offs

分支证据也会展示，列表可能更长；用户可以逐项查看，原始数据继续提供完整诊断信息。
