import { Fragment } from 'react'
import { BaseEdge, type EdgeProps } from '@xyflow/react'

import { getWorkflowStepPath } from './routing'

export function WorkflowSmoothStepEdge({
  id,
  interactionWidth,
  markerEnd,
  markerStart,
  sourcePosition,
  sourceX,
  sourceY,
  style,
  targetPosition,
  targetX,
  targetY
}: EdgeProps) {
  const edgePath = getWorkflowStepPath({
    sourcePosition,
    sourceX,
    sourceY,
    targetPosition,
    targetX,
    targetY
  })

  return (
    <Fragment>
      <path className="workflow-edge-hover-underlay" d={edgePath} />
      <BaseEdge
        id={id}
        interactionWidth={interactionWidth}
        markerEnd={markerEnd}
        markerStart={markerStart}
        path={edgePath}
        style={style}
      />
    </Fragment>
  )
}
