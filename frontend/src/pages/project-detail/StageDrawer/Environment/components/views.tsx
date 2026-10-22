import { Button, Flex, Tag } from 'antd'

import ContentState from '@/components/ContentState'
import type { ProjectEnvironmentScriptExecution } from '@/types/project'
import { formatDateTime, formatDisplayValue } from '@/utils/display'

import { TaskLogPanel } from '../../components/TaskLogPanel'
import { environmentScriptStatusConfig } from '../constants'

import styles from '../index.module.scss'

interface LogViewProps {
  loading?: boolean
  error?: boolean
  onRetry?: () => void
  execution?: ProjectEnvironmentScriptExecution
  onTaskCompleted?: () => void
}

export function LogView({
  execution,
  loading = false,
  error = false,
  onRetry,
  onTaskCompleted
}: LogViewProps) {
  if (error)
    return (
      <ContentState compact kind="error" description="执行详情加载失败">
        <Button type="primary" onClick={onRetry}>
          重试
        </Button>
      </ContentState>
    )
  if (!execution && !loading) return <ContentState description="暂无执行记录" />
  if (!execution) {
    return (
      <div className={styles.statePanel}>
        <ContentState kind="loading" description="正在加载执行详情" compact />
      </div>
    )
  }

  return (
    <div className={styles.logView}>
      <section className={styles.logSummary}>
        <div className={styles.logSummaryPrimary}>
          <Flex align="center" gap={8}>
            <h3>{execution.scriptName}</h3>
            <Tag color={environmentScriptStatusConfig[execution.status].color}>
              {environmentScriptStatusConfig[execution.status].text}
            </Tag>
          </Flex>
          <p>{formatDisplayValue(execution.message)}</p>
        </div>
        <div className={styles.logSummaryFacts}>
          <div>
            <span>提交时间</span>
            <strong>{formatDateTime(execution.submittedAt)}</strong>
          </div>
          <div>
            <span>退出码</span>
            <strong>{execution.exitCode ?? '--'}</strong>
          </div>
          <div>
            <span>日志事件</span>
            <strong>{execution.logEventCount} 条</strong>
          </div>
        </div>
      </section>
      <TaskLogPanel
        ariaLabel="环境脚本执行日志"
        className={styles.logEntries}
        editorClassName={styles.logEditor}
        status={execution.status}
        taskId={execution.id}
        title="执行日志"
        onTaskCompleted={onTaskCompleted}
      />
    </div>
  )
}
