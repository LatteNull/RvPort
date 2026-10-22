import { memo } from 'react'
import {
  CheckCircleFilled,
  ClockCircleOutlined,
  ExclamationCircleFilled,
  LoadingOutlined
} from '@ant-design/icons'
import { Handle, type Node, type NodeProps, Position } from '@xyflow/react'

import { getStageStatusStyleVars, getStageStatusText } from '../../stageStatus'
import type { WorkflowStageStatus } from '../topology'

import styles from './node.module.scss'

export type PipelineStageStatus = WorkflowStageStatus

export interface PipelineStageData extends Record<string, unknown> {
  flowBlocked: boolean
  focused: boolean
  selected?: boolean
  hint: string
  order: number
  title: string
  status?: PipelineStageStatus
}

export type PipelineStageNodeType = Node<PipelineStageData, 'pipeline-stage'>

const statusIcon = {
  done: <CheckCircleFilled />,
  running: <LoadingOutlined spin />,
  pending: <ClockCircleOutlined />,
  blocked: <ExclamationCircleFilled />
}

function PipelineStageNodeComponent({ data }: NodeProps<PipelineStageNodeType>) {
  const status = data.status ?? 'done'

  return (
    <div
      aria-current={data.focused ? 'step' : undefined}
      className={styles.stageNode}
      data-current-stage={data.focused || undefined}
      data-flow-blocked={data.flowBlocked || undefined}
      data-selected={data.selected || undefined}
      data-status={status}
      style={getStageStatusStyleVars(status)}
      title={data.focused ? `当前阶段：${data.title}` : undefined}
    >
      {data.focused ? <span className={styles.currentLabel}>当前阶段</span> : null}
      <span aria-label={getStageStatusText(status)} className={styles.stageStatusIcon}>
        {statusIcon[status]}
      </span>
      <div className={styles.content}>
        <div className={styles.title}>{data.title}</div>
        <div className={styles.stageHint} title={data.hint}>
          {data.hint}
        </div>
      </div>
      <Handle className={styles.stageHandle} type="source" position={Position.Right} />
      <Handle className={styles.stageHandle} type="target" position={Position.Left} />
      <Handle
        className={styles.stageHandle}
        id="branch-source"
        type="source"
        position={Position.Bottom}
      />
      <Handle
        className={styles.stageHandle}
        id="branch-target"
        type="target"
        position={Position.Top}
      />
      <Handle
        className={styles.stageHandle}
        id="feedback-source"
        type="source"
        position={Position.Bottom}
      />
      <Handle
        className={styles.stageHandle}
        id="feedback-target"
        type="target"
        position={Position.Bottom}
      />
    </div>
  )
}

export const PipelineStageNode = memo(PipelineStageNodeComponent)
