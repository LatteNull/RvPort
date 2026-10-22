import { CheckCircleFilled, ExclamationCircleFilled } from '@ant-design/icons'
import { Button } from 'antd'
import clsx from 'clsx'

import styles from './index.module.scss'

interface PrerequisiteNoticeProps {
  actionLabel?: string
  actionLoading?: boolean
  className?: string
  description?: string
  embedded?: boolean
  onAction?: () => void
  title: string
  tone?: 'blocked' | 'ready'
}

export default function PrerequisiteNotice({
  actionLabel,
  actionLoading = false,
  className,
  description,
  embedded = false,
  onAction,
  title,
  tone = 'blocked'
}: PrerequisiteNoticeProps) {
  const Icon = tone === 'ready' ? CheckCircleFilled : ExclamationCircleFilled

  return (
    <div
      className={clsx(styles.notice, embedded && styles.embedded, className)}
      data-tone={tone}
      role="status"
    >
      <Icon aria-hidden className={styles.icon} />
      <div className={styles.copy}>
        <strong>{title}</strong>
        {description ? <span>{description}</span> : null}
      </div>
      {actionLabel && onAction ? (
        <Button
          className={styles.action}
          loading={actionLoading}
          size="small"
          type="link"
          onClick={onAction}
        >
          {actionLabel}
        </Button>
      ) : null}
    </div>
  )
}
