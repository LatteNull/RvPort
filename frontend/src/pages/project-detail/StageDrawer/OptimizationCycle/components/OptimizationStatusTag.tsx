import { Tag } from 'antd'

import { getOptimizationStatusText } from '../presentation'

import styles from '../index.module.scss'

export function OptimizationStatusTag({ status }: { status?: string | null }) {
  const color =
    status === 'SUCCEEDED' ||
    status === 'ACTIVE' ||
    status === 'CONSISTENT' ||
    status === 'EQUIVALENT'
      ? 'success'
      : status === 'FAILED' ||
          status === 'CANCELLED' ||
          status === 'TIMEOUT' ||
          status === 'INCONSISTENT' ||
          status === 'DIFFERENT_BLOCKING'
        ? 'error'
        : status === 'INCONCLUSIVE' || status === 'DIFFERENT_ACCEPTABLE'
          ? 'warning'
          : status === 'RUNNING' || status === 'QUEUED' || status === 'PENDING'
            ? 'processing'
            : status === 'SUPERSEDED' || status === 'ARCHIVED'
              ? 'default'
              : undefined

  return (
    <Tag className={styles.statusTag} color={color}>
      {getOptimizationStatusText(status)}
    </Tag>
  )
}
