import { Tooltip } from 'antd'

import type { ProjectAutomatedTest } from '@/types/project'
import { formatDateTimeRange } from '@/utils/display'

import { TaskLogPanel } from '../../components/TaskLogPanel'
import { renderTestStatusTag } from '../presentation'

import styles from '../index.module.scss'
export default function TestRecordDetail({
  test,
  onTaskCompleted
}: {
  test: ProjectAutomatedTest
  onTaskCompleted: () => void
}) {
  return (
    <div className={styles.root}>
      <section aria-label="测试概要" className={styles.testSummary}>
        <div className={styles.summaryGrid}>
          <div className={styles.summaryItem}>
            <span>测试状态</span>
            {renderTestStatusTag(test.status)}
          </div>
          <div className={styles.summaryItem}>
            <span>退出码</span>
            <strong>{test.exitCode ?? '--'}</strong>
          </div>
          <div className={styles.summaryItem}>
            <span>测试记录 ID</span>
            <Tooltip title={test.id}>
              <strong>{test.id}</strong>
            </Tooltip>
          </div>
          <div className={styles.summaryItem}>
            <span>执行时间</span>
            <strong>{formatDateTimeRange(test)}</strong>
          </div>
          <div className={styles.summaryItem}>
            <span>测试目录</span>
            <Tooltip title={test.workingDirectory}>
              <strong>{test.workingDirectory ?? '--'}</strong>
            </Tooltip>
          </div>
        </div>
      </section>
      <TaskLogPanel
        ariaLabel="测试日志"
        className={styles.logSection}
        editorClassName={styles.logEditor}
        status={test.status}
        taskId={test.taskId}
        title="测试日志"
        onTaskCompleted={onTaskCompleted}
      />
    </div>
  )
}
