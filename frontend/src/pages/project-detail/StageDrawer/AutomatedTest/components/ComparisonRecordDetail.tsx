import { Tooltip } from 'antd'

import type { ProjectTestComparison } from '@/types/project'
import { formatDateTimeRange } from '@/utils/display'

import { TaskLogPanel } from '../../components/TaskLogPanel'
import { renderComparisonStatusTag, renderTestRiskTag } from '../presentation'

import styles from '../index.module.scss'
export default function ComparisonRecordDetail({
  comparison,
  onTaskCompleted
}: {
  comparison: ProjectTestComparison
  onTaskCompleted: () => void
}) {
  return (
    <div className={styles.root}>
      <section aria-label="对比概要" className={styles.testSummary}>
        <div className={styles.summaryGrid}>
          <div className={styles.summaryItem}>
            <span>对比状态</span>
            {renderComparisonStatusTag(comparison.overallStatus ?? comparison.status)}
          </div>
          <div className={styles.summaryItem}>
            <span>风险</span>
            {renderTestRiskTag(comparison.riskLevel) ?? <strong>--</strong>}
          </div>
          <div className={styles.summaryItem}>
            <span>对比记录 ID</span>
            <Tooltip title={comparison.id}>
              <strong>{comparison.id}</strong>
            </Tooltip>
          </div>
          <div className={styles.summaryItem}>
            <span>执行时间</span>
            <strong>{formatDateTimeRange(comparison)}</strong>
          </div>
          <div className={styles.summaryItem}>
            <span>测试批次</span>
            <Tooltip title={comparison.testBatchId}>
              <strong>{comparison.testBatchId}</strong>
            </Tooltip>
          </div>
        </div>
      </section>
      <TaskLogPanel
        ariaLabel="测试结果对比日志"
        className={styles.logSection}
        editorClassName={styles.logEditor}
        fallbackContent={comparison.errorMessage}
        status={comparison.status}
        taskId={comparison.taskId}
        title="对比日志"
        onTaskCompleted={onTaskCompleted}
      />
    </div>
  )
}
