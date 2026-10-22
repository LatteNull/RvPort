import { type ReactNode, useId } from 'react'
import { BulbOutlined } from '@ant-design/icons'

import styles from './index.module.scss'

export default function FindingNextSteps({
  suggestion,
  reportActions,
  children
}: {
  suggestion: string
  reportActions?: ReactNode
  children?: ReactNode
}) {
  const titleId = useId()
  return (
    <section className={styles.findingNextSteps} aria-labelledby={titleId}>
      <div className={styles.findingSectionHeading}>
        <div>
          <div>
            <h3 id={titleId}>
              <BulbOutlined aria-hidden="true" />
              建议下一步
            </h3>
            <p>根据静态证据决定是否纳入本轮评估报告</p>
          </div>
        </div>
        {reportActions ? <div className={styles.findingReportActions}>{reportActions}</div> : null}
      </div>
      <p className={styles.findingSuggestion}>{suggestion}</p>
      {children}
    </section>
  )
}
