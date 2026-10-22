import { memo } from 'react'
import { Handle, type Node, type NodeProps, Position } from '@xyflow/react'
import { Tooltip } from 'antd'

import type { WorkflowGatewayState } from '../presentation'

import styles from './node.module.scss'

export interface WorkflowGatewayData extends Record<string, unknown> {
  completed: number
  state: WorkflowGatewayState
  title: string
  total: number
}

export type WorkflowGatewayNodeType = Node<WorkflowGatewayData, 'workflow-gateway'>

function WorkflowGatewayNodeComponent({ data }: NodeProps<WorkflowGatewayNodeType>) {
  return (
    <Tooltip title={`${data.title}：${data.completed}/${data.total}`}>
      <div
        aria-label={`${data.title}，${data.completed}/${data.total}`}
        className={styles.gatewayNode}
        data-state={data.state}
        tabIndex={0}
      >
        <span>{data.completed}</span>
        <small>/{data.total}</small>
        <Handle className={styles.gatewayHandle} type="target" position={Position.Left} />
        <Handle className={styles.gatewayHandle} type="source" position={Position.Right} />
      </div>
    </Tooltip>
  )
}

export const WorkflowGatewayNode = memo(WorkflowGatewayNodeComponent)
