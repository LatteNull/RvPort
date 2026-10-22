import { LinkOutlined } from '@ant-design/icons'
import { Button, Tooltip } from 'antd'
import type { ReactNode } from 'react'

import PrerequisiteNotice from '../PrerequisiteNotice'

import styles from './index.module.scss'

export interface PrerequisitePanelItem {
  actionLabel?: string
  href?: string | null
  key: string
  label: string
  onAction?: () => void
  value: ReactNode
  valueTitle?: ReactNode
}

interface PrerequisitePanelProps {
  description?: string
  items: PrerequisitePanelItem[]
  ready: boolean
  title: string
}

export default function PrerequisitePanel({
  description,
  items,
  ready,
  title
}: PrerequisitePanelProps) {
  return (
    <div className={styles.panel} data-tone={ready ? 'ready' : 'blocked'}>
      <PrerequisiteNotice
        className={styles.notice}
        description={description}
        embedded
        title={title}
        tone={ready ? 'ready' : 'blocked'}
      />
      <div className={styles.grid}>
        {items.map((item) => (
          <div className={styles.item} key={item.key}>
            <span className={styles.label}>{item.label}</span>
            <div className={styles.valueRow}>
              <Tooltip title={item.valueTitle}>
                {item.href ? (
                  <a href={item.href} rel="noreferrer" target="_blank">
                    <span>{item.value}</span>
                    <LinkOutlined aria-hidden />
                  </a>
                ) : (
                  <strong>{item.value}</strong>
                )}
              </Tooltip>
              {item.actionLabel && item.onAction ? (
                <Button size="small" type="link" onClick={item.onAction}>
                  {item.actionLabel}
                </Button>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
