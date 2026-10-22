import type { ReactNode } from 'react'

import styles from './index.module.scss'

export default function ResultOverview({
  status,
  metadata,
  children
}: {
  status: ReactNode
  metadata: Array<{ label: string; value: ReactNode }>
  children: ReactNode
}) {
  return (
    <div className={styles.overview}>
      <div className={styles.header}>
        <div className={styles.item}>
          <span>分析状态</span>
          {status}
        </div>
        {metadata.map(({ label, value }) => (
          <div className={styles.item} key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      {children}
    </div>
  )
}
