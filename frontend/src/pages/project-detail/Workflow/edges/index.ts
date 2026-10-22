import { type CSSProperties } from 'react'
import { type Edge, type EdgeTypes, MarkerType } from '@xyflow/react'

import type { ProjectWorkflowStatus } from '@/types/project'

import { deriveWorkflowGatewayPresentation, deriveWorkflowPresentation } from '../presentation'
import { type WorkflowEdgeDefinition, workflowEdges } from '../topology'
import { FeedbackEdge } from './FeedbackEdge'
import { WorkflowSmoothStepEdge } from './WorkflowSmoothStepEdge'

function createBaseEdge(edge: WorkflowEdgeDefinition): Edge {
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.feedback ? 'feedback-source' : edge.sourceHandle,
    targetHandle: edge.feedback ? 'feedback-target' : edge.targetHandle,
    type: edge.feedback ? 'feedback' : 'workflow-smoothstep',
    label: edge.label,
    className: `workflow-edge workflow-edge-source-${edge.source} workflow-edge-target-${edge.target}`,
    zIndex: 1,
    animated: false
  }
}

const baseEdges: Edge[] = workflowEdges.map(createBaseEdge)

const hoveredEdgeClassName = 'workflow-edge-hovered'
const hoveredEdgeZIndex = 2

type WorkflowEdgeState = 'active' | 'blocked' | 'complete' | 'waiting'

const markerByState: Record<WorkflowEdgeState, NonNullable<Edge['markerEnd']>> = {
  active: { color: '#2563eb', height: 12, type: MarkerType.ArrowClosed, width: 12 },
  blocked: { color: '#dc2626', height: 12, type: MarkerType.ArrowClosed, width: 12 },
  complete: { color: '#6f89aa', height: 12, type: MarkerType.ArrowClosed, width: 12 },
  waiting: { color: '#a9b4c3', height: 12, type: MarkerType.ArrowClosed, width: 12 }
}

const edgeStyleByState: Record<WorkflowEdgeState, CSSProperties> = {
  active: { stroke: '#2563eb', strokeWidth: 2.5 },
  blocked: { stroke: '#dc2626', strokeDasharray: '3 6', strokeWidth: 2.5 },
  complete: { stroke: '#6f89aa', strokeWidth: 2.5 },
  waiting: { stroke: '#a9b4c3', strokeDasharray: '4 7', strokeWidth: 2.5 }
}

function getEdgeState(
  edge: WorkflowEdgeDefinition,
  activeEdgeIds: Set<string>,
  presentationByStageId: ReturnType<typeof deriveWorkflowPresentation>,
  presentationByGatewayId: ReturnType<typeof deriveWorkflowGatewayPresentation>
): WorkflowEdgeState {
  const source = presentationByStageId.get(edge.source)
  const target = presentationByStageId.get(edge.target)
  const sourceGateway = presentationByGatewayId.get(edge.source)
  const targetGateway = presentationByGatewayId.get(edge.target)

  // 已完成节点是事实边界；阻塞只传播到尚未执行的前向链路。
  if (target?.status === 'done') {
    return 'complete'
  }

  if (source?.flowBlocked || target?.flowBlocked || sourceGateway?.state === 'BLOCKED') {
    return 'blocked'
  }

  if (activeEdgeIds.has(edge.id)) {
    return 'active'
  }

  if (targetGateway?.state === 'COMPLETE') {
    return 'complete'
  }

  if (sourceGateway) {
    switch (sourceGateway.state) {
      case 'ACTIVE':
        return 'active'
      case 'COMPLETE':
        return 'complete'
      case 'WAITING':
        return 'waiting'
    }
  }

  switch (target?.status) {
    case 'running':
      return 'active'
    case 'blocked':
      return 'blocked'
  }

  if (source?.status === 'blocked' || source?.assistStatus === 'BLOCKED') {
    return 'blocked'
  }

  switch (source?.status) {
    case 'running':
      return 'active'
    case 'done':
      return 'complete'
    default:
      return 'waiting'
  }
}

export const DEFAULT_ACTIVE_EDGE_ANIMATION_BUDGET = 4

export function createWorkflowEdges(
  workflowStatus?: ProjectWorkflowStatus,
  previousEdges?: Edge[],
  animationBudget = DEFAULT_ACTIVE_EDGE_ANIMATION_BUDGET
): Edge[] {
  if (!workflowStatus) {
    return previousEdges === baseEdges ? previousEdges : baseEdges
  }

  const activeEdgeIds = new Set(workflowStatus.activeEdgeIds)
  const presentationByStageId = deriveWorkflowPresentation(workflowStatus)
  const presentationByGatewayId = deriveWorkflowGatewayPresentation(workflowStatus)
  const definitionById = new Map(workflowEdges.map((edge) => [edge.id, edge]))
  const previousById = new Map(previousEdges?.map((edge) => [edge.id, edge]))
  let animatedCount = 0
  let changed = previousEdges === undefined

  const nextEdges = baseEdges.map((edge) => {
    const definition = definitionById.get(edge.id)

    if (definition?.feedback) {
      return previousById.get(edge.id) ?? edge
    }

    const edgeState = definition
      ? getEdgeState(definition, activeEdgeIds, presentationByStageId, presentationByGatewayId)
      : 'waiting'
    const active = edgeState === 'active'
    const animated = active && animatedCount++ < animationBudget
    const className = `${edge.className} workflow-edge-${edgeState}`
    const markerEnd = markerByState[edgeState]
    const style = edgeStyleByState[edgeState]
    const previous = previousById.get(edge.id)
    if (
      previous?.animated === animated &&
      previous.className === className &&
      previous.markerEnd === markerEnd &&
      previous.style === style
    ) {
      return previous
    }
    changed = true
    return { ...edge, className, animated, markerEnd, style }
  })
  return !changed && previousEdges ? previousEdges : nextEdges
}

export function highlightConnectedWorkflowEdges(
  edges: Edge[],
  nodeId?: string,
  currentStageId?: string
): Edge[] {
  if (!nodeId && !currentStageId) {
    return edges
  }

  return edges.map((edge) => {
    if (
      edge.source !== nodeId &&
      edge.target !== nodeId &&
      edge.source !== currentStageId &&
      edge.target !== currentStageId
    ) {
      return edge
    }

    return {
      ...edge,
      className: `${edge.className ?? ''} ${hoveredEdgeClassName}`.trim(),
      // Smooth-step edges can share path segments. Elevating every connected edge keeps a
      // later-rendered, unrelated solid edge from covering the hovered dashed path.
      zIndex: hoveredEdgeZIndex
    }
  })
}

export const edgeTypes = {
  feedback: FeedbackEdge,
  'workflow-smoothstep': WorkflowSmoothStepEdge
} satisfies EdgeTypes
