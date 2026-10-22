import { Spin } from 'antd'
import clsx from 'clsx'
import type { ReactNode } from 'react'

import StateIllustration from './StateIllustration'

import styles from './index.module.scss'

interface ContentStateProps {
  children?: ReactNode
  className?: string
  compact?: boolean
  description?: ReactNode
  details?: ReactNode
  kind?: 'empty' | 'error' | 'filtered' | 'loading'
}

/** Shared data feedback; domain readiness and execution facts stay in stage components. */
export default function ContentState({
  children,
  className,
  compact = false,
  description = '暂无数据',
  details,
  kind = 'empty'
}: ContentStateProps) {
  const loading = kind === 'loading'
  return (
    <div
      aria-busy={loading || undefined}
      aria-label={typeof description === 'string' ? description : undefined}
      aria-live="polite"
      className={clsx(styles.state, compact && styles.compact, className)}
      data-state={kind}
      role={kind === 'error' ? 'alert' : 'status'}
    >
      {loading ? <Spin size={compact ? 'medium' : 'large'} /> : <StateIllustration kind={kind} />}
      <div className={styles.copy}>
        <strong>{description}</strong>
        {details ? <span>{details}</span> : null}
      </div>
      {children ? <div className={styles.actions}>{children}</div> : null}
    </div>
  )
}
