# Project Stage Design

## Context

StageDrawer 只负责根据当前 `stageId` 选择具体 Stage 抽屉。每个 Stage 的内容差异较大，并且可能请求不同接口，因此请求逻辑、BaseDrawer 包裹、footer 和 loading/error 均由具体 Stage 组件自己维护。

## Decisions

### 每个 Stage 一个 change

阶段内容按节点逐步推进。当前 change 只处理 `project` 节点；其它节点暂时走 `Default`。

### 每个 Stage 使用文件夹

StageDrawer 下每个 Stage 都使用独立文件夹，入口固定为 `index.tsx`。当前只实现：

```text
StageDrawer/
  Project/
    index.tsx
  Default/
    index.tsx
```

后续复杂 Stage 可以在自己的文件夹内继续拆分，简单 Stage 也保持相同目录结构。

### Project 数据结构

后端返回统一壳子：

```ts
ProjectStageDetail<TData>
```

`project` 阶段的 `data` 使用独立结构：

```ts
ProjectCreateStageData
```

包括：

- `basicInfo`: 项目基本信息
- `statusInfo`: 项目状态信息

操作入口由具体 Stage 前端组件维护，不由后端详情接口返回。

### 编辑范围

项目创建阶段只允许编辑项目描述。项目名称、源架构、目标架构、源码来源和首批语言均只读展示。

### 查询归属

`Project/index.tsx` 自己通过 `projectId` 请求项目创建阶段详情接口。`StageDrawer/index.tsx` 不统一请求所有 Stage 的详情数据，避免后续 Stage 被强制绑定到同一个接口形态。

### 共享组件边界

StageDrawer 只抽取有明确视觉语义的组件，例如 `DrawerInfoItem` 和 `DrawerStatusTag`。纯布局结构不再封装为 `DrawerContent`、`DrawerSection`、`DrawerActions` 这类 wrapper，由各 Stage 直接使用语义标签和 SCSS class 组织，避免过度封装。
