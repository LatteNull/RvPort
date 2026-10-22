import {
  type CSSProperties,
  isValidElement,
  type ReactNode,
  useEffect,
  useEffectEvent,
  useId,
  useLayoutEffect,
  useRef
} from 'react'
import { Skeleton } from 'antd'

import styles from './StagePanel.module.scss'

interface StagePanelProps {
  children?: ReactNode
  title?: ReactNode | { title: ReactNode; subTitle?: ReactNode }
  extra?: ReactNode
  footer?: ReactNode
  visible?: boolean
  loading?: boolean
  showTitle?: boolean
  scrollKey?: string
  onVisibleChange?: (visible: boolean) => void
  styles?: { body?: CSSProperties; header?: CSSProperties; footer?: CSSProperties }
}

export default function StagePanel({
  children,
  title,
  extra,
  footer,
  visible = true,
  loading,
  showTitle = true,
  scrollKey,
  onVisibleChange,
  styles: slots
}: StagePanelProps) {
  const titleId = useId()
  const bodyRef = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => {
    // Entering or leaving a detail view should reveal its overview, not inherit list scroll.
    if (bodyRef.current) bodyRef.current.scrollTop = 0
  }, [scrollKey, showTitle, visible])
  const notifyVisibility = useEffectEvent((value: boolean) => onVisibleChange?.(value))
  useEffect(() => {
    notifyVisibility(visible)
  }, [visible])

  if (!visible) return null
  const titleContent =
    title && typeof title === 'object' && !isValidElement(title) && 'title' in title ? (
      <div>
        <strong>{title.title}</strong>
        {title.subTitle ? <p>{title.subTitle}</p> : null}
      </div>
    ) : (
      (title as ReactNode)
    )

  return (
    <section aria-labelledby={titleContent ? titleId : undefined} className={styles.panel}>
      {titleContent && !showTitle ? (
        <div className={styles.screenReaderOnly} id={titleId}>
          {titleContent}
        </div>
      ) : null}
      {(showTitle && titleContent) || extra ? (
        <header className={styles.header} style={slots?.header}>
          {titleContent && showTitle ? (
            <div className={styles.title} id={titleId}>
              {titleContent}
            </div>
          ) : null}
          {extra ? <div className={styles.actions}>{extra}</div> : null}
        </header>
      ) : null}
      <div
        ref={bodyRef}
        aria-busy={loading || undefined}
        className={styles.body}
        style={slots?.body}
      >
        {loading ? (
          <div role="status" aria-label="正在加载阶段内容">
            <Skeleton active />
          </div>
        ) : (
          children
        )}
      </div>
      {footer ? (
        <footer className={styles.footer} style={slots?.footer}>
          {footer}
        </footer>
      ) : null}
    </section>
  )
}
