import { Tag, Tooltip } from 'antd'

import type { ProjectBuildValidation } from '@/types/project'
import { formatDateTimeRange, getTaskStatusPresentation } from '@/utils/display'

import { TaskLogPanel } from '../../components/TaskLogPanel'
import { BitcodeResult } from './BitcodeResult'

import styles from '../index.module.scss'
function taskStatusTag(status: ProjectBuildValidation['status']) {
  const { color, label } = getTaskStatusPresentation(status)
  return (
    <Tag className={styles.statusTag} color={color}>
      {label}
    </Tag>
  )
}
export default function BuildLogView({
  build,
  onTaskCompleted
}: {
  build: ProjectBuildValidation
  onTaskCompleted: () => void
}) {
  return (
    <div className={styles.logContent}>
      <section aria-label="构建概要" className={styles.buildSummary}>
        <div className={styles.summaryGrid}>
          <div className={styles.summaryItem}>
            <span>构建状态</span>
            {taskStatusTag(build.status)}
          </div>
          <div className={styles.summaryItem}>
            <span>退出码</span>
            <strong>{build.exitCode ?? '--'}</strong>
          </div>
          <div className={styles.summaryItem}>
            <span>构建记录 ID</span>
            <Tooltip title={build.id}>
              <strong>{build.id}</strong>
            </Tooltip>
          </div>
          <div className={styles.summaryItem}>
            <span>执行时间</span>
            <strong>{formatDateTimeRange(build)}</strong>
          </div>
          <div className={styles.summaryItem}>
            <span>构建目录</span>
            <Tooltip title={build.workingDirectory}>
              <strong>{build.workingDirectory}</strong>
            </Tooltip>
          </div>
        </div>
      </section>
      <BitcodeResult build={build} />
      <TaskLogPanel
        ariaLabel="x86 构建日志"
        className={`${styles.section} ${styles.logSection}`}
        editorClassName={styles.logEditor}
        status={build.status}
        taskId={build.taskId}
        title="构建日志"
        onTaskCompleted={onTaskCompleted}
      />
    </div>
  )
}
