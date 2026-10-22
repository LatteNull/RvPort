import { type CSSProperties, Fragment } from 'react'
import type { EdgeProps } from '@xyflow/react'

import { getFeedbackRoute } from './routing'

const feedbackEdgeStyle: CSSProperties = {
  stroke: '#7c3aed',
  strokeDasharray: '9 7',
  strokeWidth: 2,
  fill: 'none'
}

export function FeedbackEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  markerEnd,
  animated,
  label
}: EdgeProps) {
  const {
    path: edgePath,
    labelX,
    labelY
  } = getFeedbackRoute(id, sourceX, sourceY, targetX, targetY)

  return (
    <Fragment>
      <path className="workflow-edge-hover-underlay" d={edgePath} />
      <path
        className="react-flow__edge-path"
        id={id}
        d={edgePath}
        markerEnd={markerEnd}
        style={feedbackEdgeStyle}
      >
        {animated && (
          <animate
            attributeName="stroke-dashoffset"
            dur="700ms"
            from="16"
            repeatCount="indefinite"
            to="0"
          />
        )}
      </path>
      {label ? (
        <text
          fill="#6d4cc4"
          fontSize="11"
          textAnchor="middle"
          x={labelX}
          y={labelY}
          stroke="#f5f5f5"
          strokeWidth={5}
          strokeLinejoin="round"
          paintOrder="stroke"
        >
          {String(label)}
        </text>
      ) : null}
    </Fragment>
  )
}
