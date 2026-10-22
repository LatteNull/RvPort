import type { ReactNode } from 'react'

import styles from './index.module.scss'

interface CurrentExecutionResultProps {
  actions?: ReactNode
  children?: ReactNode
  status: ReactNode
  subtitle?: ReactNode
  title: ReactNode
}

export function CurrentExecutionResultGrid({ children }: { children: ReactNode }) {
  return <div className={styles.grid}>{children}</div>
}

export default function CurrentExecutionResult({
  actions,
  children,
  status,
  subtitle,
  title
}: CurrentExecutionResultProps) {
  return (
    <article className={styles.card}>
      <div className={styles.header}>
        <strong>{title}</strong>
        {status}
      </div>
      {subtitle ? <div className={styles.subtitle}>{subtitle}</div> : null}
      {children != null || actions != null ? (
        <div className={styles.details}>
          {children}
          {actions ? <div className={styles.actions}>{actions}</div> : null}
        </div>
      ) : null}
    </article>
  )
}
