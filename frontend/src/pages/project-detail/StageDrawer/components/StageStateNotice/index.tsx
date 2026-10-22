import {
  CheckCircleFilled,
  CloseCircleFilled,
  DisconnectOutlined,
  ExclamationCircleFilled,
  FileAddOutlined,
  Loading3QuartersOutlined,
  LockOutlined
} from '@ant-design/icons'
import { Button, Flex, Popconfirm } from 'antd'
import clsx from 'clsx'
import type { ReactNode } from 'react'

import styles from './index.module.scss'

export type StageStateVariant =
  | 'prerequisite'
  | 'ready'
  | 'empty'
  | 'processing'
  | 'partial'
  | 'execution-error'
  | 'request-error'

export interface StageStateAction {
  href?: string
  confirmation?: {
    cancelText?: string
    description?: ReactNode
    okText?: string
    title: ReactNode
  }
  disabled?: boolean
  label: string
  loading?: boolean
  onClick: () => void
  type?: 'default' | 'link'
}

function StateActionButton({
  action,
  primary = false,
  size
}: {
  action: StageStateAction
  primary?: boolean
  size?: 'small'
}) {
  const button = (
    <Button
      href={action.href}
      disabled={action.disabled}
      loading={action.loading}
      size={size}
      type={primary ? 'primary' : action.type}
      onClick={action.confirmation ? undefined : action.onClick}
    >
      {action.label}
    </Button>
  )

  return action.confirmation ? (
    <Popconfirm
      cancelText={action.confirmation.cancelText}
      description={action.confirmation.description}
      okButtonProps={{ loading: action.loading }}
      okText={action.confirmation.okText}
      title={action.confirmation.title}
      onConfirm={action.onClick}
    >
      {button}
    </Popconfirm>
  ) : (
    button
  )
}

export interface StageStatePrerequisite {
  action?: StageStateAction
  key: string
  label: string
  ready: boolean
  value: ReactNode
}

interface StageStateNoticeProps {
  className?: string
  description: string
  details?: ReactNode
  footer?: ReactNode
  embedded?: boolean
  prerequisites?: StageStatePrerequisite[]
  primaryAction?: StageStateAction
  secondaryActions?: StageStateAction[]
  title: string
  variant: StageStateVariant
}

const variantPresentation = {
  prerequisite: { Icon: LockOutlined, tone: 'warning' },
  ready: { Icon: CheckCircleFilled, tone: 'success' },
  empty: { Icon: FileAddOutlined, tone: 'neutral' },
  processing: { Icon: Loading3QuartersOutlined, tone: 'processing' },
  partial: { Icon: ExclamationCircleFilled, tone: 'warning' },
  'execution-error': { Icon: CloseCircleFilled, tone: 'error' },
  'request-error': { Icon: DisconnectOutlined, tone: 'error' }
} as const

export default function StageStateNotice({
  className,
  description,
  details,
  footer,
  embedded = false,
  prerequisites = [],
  primaryAction,
  secondaryActions = [],
  title,
  variant
}: StageStateNoticeProps) {
  const { Icon, tone } = variantPresentation[variant]
  const hasActions = Boolean(primaryAction || secondaryActions.length)

  return (
    <section
      aria-live={variant === 'processing' ? 'polite' : undefined}
      className={clsx(styles.notice, embedded && styles.embedded, className)}
      data-tone={tone}
      data-variant={variant}
      role="status"
    >
      <div className={styles.statusMark}>
        <Icon aria-hidden className={styles.icon} />
      </div>
      <div className={styles.copy}>
        <strong>{title}</strong>
        <span>{description}</span>
        {details ? <div className={styles.details}>{details}</div> : null}
      </div>
      {prerequisites.length ? (
        <div className={styles.prerequisites}>
          {prerequisites.map((prerequisite) => (
            <div
              className={styles.prerequisite}
              data-ready={prerequisite.ready}
              key={prerequisite.key}
            >
              {prerequisite.ready ? (
                <CheckCircleFilled aria-hidden className={styles.prerequisiteIcon} />
              ) : (
                <ExclamationCircleFilled aria-hidden className={styles.prerequisiteIcon} />
              )}
              <div className={styles.prerequisiteCopy}>
                <span>{prerequisite.label}</span>
                <strong>{prerequisite.value}</strong>
              </div>
              {prerequisite.action ? (
                <StateActionButton action={{ ...prerequisite.action, type: 'link' }} size="small" />
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
      {hasActions ? (
        <Flex className={styles.actions} gap={8} justify="center" wrap>
          {primaryAction ? <StateActionButton action={primaryAction} primary /> : null}
          {secondaryActions.map((action) => (
            <StateActionButton action={action} key={action.label} />
          ))}
        </Flex>
      ) : null}
      {footer ? <div className={styles.footer}>{footer}</div> : null}
    </section>
  )
}
