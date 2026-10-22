import { memo } from 'react'
import type { Node, NodeProps } from '@xyflow/react'

import type { WorkflowGroupTone } from '../topology'

import styles from './node.module.scss'

export type { WorkflowGroupTone }

export interface WorkflowGroupData extends Record<string, unknown> {
  title: string
  tone: WorkflowGroupTone
}

export type WorkflowGroupNodeType = Node<WorkflowGroupData, 'workflow-group'>

function WorkflowGroupNodeComponent({ data }: NodeProps<WorkflowGroupNodeType>) {
  return (
    <div className={styles.groupNode} data-tone={data.tone}>
      <span>{data.title}</span>
    </div>
  )
}

export const WorkflowGroupNode = memo(WorkflowGroupNodeComponent)
