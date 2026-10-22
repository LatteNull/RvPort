import { Fragment } from 'react'
import {
  ArrowRightOutlined,
  CloudServerOutlined,
  CodeOutlined,
  DownOutlined,
  ProjectOutlined,
  ThunderboltOutlined
} from '@ant-design/icons'
import { Popover, Tooltip } from 'antd'

import { getProjectTaskTypeText, projectTaskStatusText } from '@/config/project-status'
import type { ProjectOverview, ProjectOverviewTask } from '@/types/project'
import { formatDateTime } from '@/utils/display'

import styles from '../index.module.scss'
const activeTaskStatuses: ProjectOverviewTask['status'][] = ['RUNNING', 'QUEUED', 'PENDING']

function getSourceLabel(source: ProjectOverview['currentContext']['activeSourceRevision']) {
  if (!source) return null
  if (source.type === 'ARCHIVE') return source.fileName ?? source.version

  const repositoryUrl = source.repositoryUrl?.replace(/[\\/]+$/, '')
  const repositoryName = repositoryUrl?.split(/[/:]/).filter(Boolean).at(-1)
  return repositoryName?.replace(/\.git$/i, '') || source.version
}

function getCurrentTask(tasks: ProjectOverviewTask[]) {
  for (const status of activeTaskStatuses) {
    const task = tasks.find((item) => item.status === status)
    if (task) return task
  }
  return tasks[0]
}

function getTaskStatusClass(status: ProjectOverviewTask['status']) {
  if (status === 'FAILED' || status === 'TIMEOUT') return styles.taskStatusError
  if (status === 'RUNNING' || status === 'QUEUED') return styles.taskStatusRunning
  if (status === 'SUCCEEDED') return styles.taskStatusSuccess
  return styles.taskStatusPending
}

function getTaskTone(task?: ProjectOverviewTask) {
  if (!task) return 'empty'
  if (task.status === 'FAILED' || task.status === 'TIMEOUT') return 'error'
  if (task.status === 'RUNNING' || task.status === 'QUEUED') return 'running'
  if (task.status === 'SUCCEEDED') return 'success'
  return 'pending'
}

function isActiveTask(task: ProjectOverviewTask) {
  return activeTaskStatuses.includes(task.status)
}

function getTaskDisplayTime(task: ProjectOverviewTask) {
  if (isActiveTask(task)) {
    return task.startedAt ?? task.queuedAt ?? task.createdAt
  }
  return task.finishedAt ?? task.startedAt ?? task.createdAt
}

function RecentTasksList({
  currentTaskId,
  tasks
}: {
  currentTaskId?: string
  tasks: ProjectOverviewTask[]
}) {
  return (
    <div className={styles.recentTasksPopover}>
      <div className={styles.recentTasksPopoverHeading}>
        <strong>最近任务</strong>
        <span>最多 5 条</span>
      </div>
      <ol aria-label="最近任务列表" className={styles.recentTasksList}>
        {tasks.slice(0, 5).map((task) => {
          const active = isActiveTask(task)
          const progress = Math.min(100, Math.max(0, task.progress ?? 0))

          return (
            <li className={styles.recentTaskItem} data-task-tone={getTaskTone(task)} key={task.id}>
              <div className={styles.recentTaskTitleLine}>
                <span aria-hidden="true" className={styles.recentTaskDot} />
                <strong>{getProjectTaskTypeText(task.type)}</strong>
                {active && task.id === currentTaskId ? (
                  <span className={styles.recentTaskCurrent}>当前</span>
                ) : null}
                <span className={styles.recentTaskStatus}>
                  {projectTaskStatusText[task.status]}
                </span>
              </div>
              <div className={styles.recentTaskDetailLine}>
                <time dateTime={getTaskDisplayTime(task)}>
                  {formatDateTime(getTaskDisplayTime(task))}
                </time>
                <span aria-hidden="true" className={styles.recentTaskSeparator}>
                  ·
                </span>
                <span className={styles.recentTaskMessage} title={task.message ?? undefined}>
                  {task.message || (active ? '任务正在执行' : '任务已结束')}
                </span>
                {active && task.progress !== null ? (
                  <span className={styles.recentTaskProgressValue}>{task.progress}%</span>
                ) : null}
              </div>
              {active && task.progress !== null ? (
                <progress
                  aria-label={`${getProjectTaskTypeText(task.type)}进度`}
                  max={100}
                  value={progress}
                />
              ) : null}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

export default function SummaryCards({
  compact = false,
  overview
}: {
  compact?: boolean
  overview: ProjectOverview
}) {
  const activeSource = overview.currentContext.activeSourceRevision
  const sourceLabel = getSourceLabel(activeSource)
  const sourceRepositoryUrl = activeSource?.type === 'GIT' ? activeSource.repositoryUrl : undefined
  const runtimeEnvironments = overview.currentContext.runtimeEnvironments
  const { sourceEnvironment, targetEnvironment } = runtimeEnvironments
  const currentTask = getCurrentTask(overview.recentTasks)
  const hasActiveTask = currentTask ? activeTaskStatuses.includes(currentTask.status) : false

  if (compact) {
    return (
      <section aria-label="项目紧凑摘要" className={styles.compactSummary}>
        <article
          aria-label="当前迁移上下文"
          className={`${styles.compactSummaryItem} ${styles.compactSummaryOverview} ${styles.compactSummaryContext}`}
        >
          <div className={styles.compactProjectIdentity}>
            <div className={styles.compactSummaryValue}>
              <Tooltip title={overview.project.name}>
                <strong>{overview.project.name}</strong>
              </Tooltip>
            </div>
          </div>
          {sourceRepositoryUrl ? (
            <a
              className={styles.compactSourceIdentity}
              href={sourceRepositoryUrl}
              rel="noreferrer"
              target="_blank"
              title={`打开 Git 仓库：${sourceRepositoryUrl}`}
            >
              <CodeOutlined
                aria-hidden="true"
                className={`${styles.compactSummaryIcon} ${styles.compactSourceIcon}`}
              />
              <Tooltip title={sourceLabel ?? '源码待配置'}>
                <strong>{sourceLabel ?? '源码待配置'}</strong>
              </Tooltip>
            </a>
          ) : (
            <div className={styles.compactSourceIdentity}>
              <CodeOutlined
                aria-hidden="true"
                className={`${styles.compactSummaryIcon} ${styles.compactSourceIcon}`}
              />
              <Tooltip title={sourceLabel ?? '源码待配置'}>
                <strong>{sourceLabel ?? '源码待配置'}</strong>
              </Tooltip>
            </div>
          )}
          <div className={styles.compactEnvironmentContext} aria-label="当前迁移环境">
            <span
              aria-label="环境配置"
              className={`${styles.compactSummaryIcon} ${styles.compactEnvironmentHeading}`}
            >
              <CloudServerOutlined aria-hidden="true" />
            </span>
            <div className={styles.compactMigrationRoute}>
              <span>
                <small>源端</small>
                <strong>{overview.project.sourceArch}</strong>
                <Tooltip title={sourceEnvironment?.name ?? '环境待配置'}>
                  <small>{sourceEnvironment?.name ?? '环境待配置'}</small>
                </Tooltip>
              </span>
              <ArrowRightOutlined aria-hidden="true" />
              <span>
                <small>目标端</small>
                <strong>{overview.project.targetArch}</strong>
                <Tooltip title={targetEnvironment?.name ?? '环境待配置'}>
                  <small>{targetEnvironment?.name ?? '环境待配置'}</small>
                </Tooltip>
              </span>
              <small className={styles.compactConfigVersion}>v{runtimeEnvironments.version}</small>
            </div>
          </div>
        </article>
        <article
          aria-label="执行上下文"
          className={`${styles.compactSummaryItem} ${styles.compactSummaryTask}`}
          data-task-tone={getTaskTone(currentTask)}
        >
          <ThunderboltOutlined aria-hidden="true" className={styles.compactSummaryIcon} />
          <div>
            <div className={styles.compactSummaryValue}>
              <Tooltip title={currentTask ? getProjectTaskTypeText(currentTask.type) : '暂无任务'}>
                <strong>
                  {currentTask ? getProjectTaskTypeText(currentTask.type) : '暂无任务'}
                </strong>
              </Tooltip>
              {currentTask ? (
                <small className={getTaskStatusClass(currentTask.status)}>
                  {projectTaskStatusText[currentTask.status]}
                </small>
              ) : null}
            </div>
          </div>
        </article>
      </section>
    )
  }

  return (
    <section className={styles.summaryRow} aria-label="项目流水线摘要">
      <div className={styles.contextPanel}>
        <div
          className={`${styles.summaryCard} ${styles.migrationContext}`}
          aria-label="项目与当前迁移上下文"
        >
          <div className={styles.cardHeading}>
            <span>当前迁移上下文</span>
            <small>配置版本 v{runtimeEnvironments.version}</small>
          </div>
          <div className={styles.migrationSummaryBody}>
            <div className={styles.projectContextBlock}>
              <ProjectOutlined aria-hidden="true" className={styles.projectContextIcon} />
              <div>
                <small>项目</small>
                <strong title={overview.project.name}>{overview.project.name}</strong>
              </div>
            </div>
            <div className={styles.sourceContextBlock}>
              <CodeOutlined aria-hidden="true" className={styles.sourceContextIcon} />
              <div>
                <small>当前源码</small>
                {sourceRepositoryUrl ? (
                  <a
                    className={styles.sourceRepositoryLink}
                    href={sourceRepositoryUrl}
                    rel="noreferrer"
                    target="_blank"
                    title={`打开 Git 仓库：${sourceRepositoryUrl}`}
                  >
                    {sourceLabel ?? '源码待配置'}
                  </a>
                ) : (
                  <strong title={sourceLabel ?? undefined}>{sourceLabel ?? '源码待配置'}</strong>
                )}
              </div>
            </div>
            <div className={styles.environmentContextBlock}>
              <CloudServerOutlined aria-hidden="true" className={styles.environmentContextIcon} />
              <div className={styles.environmentContextContent}>
                <small>环境配置</small>
                <div className={styles.migrationRoute}>
                  <article className={styles.migrationEndpoint} data-role="source">
                    <small>源端</small>
                    <div>
                      <strong>{overview.project.sourceArch}</strong>
                      <span title={sourceEnvironment?.name}>
                        {sourceEnvironment?.name ?? '源环境待配置'}
                      </span>
                    </div>
                  </article>
                  <span className={styles.migrationConnector} aria-hidden="true">
                    <ArrowRightOutlined />
                  </span>
                  <article className={styles.migrationEndpoint} data-role="target">
                    <small>目标端</small>
                    <div>
                      <strong>{overview.project.targetArch}</strong>
                      <span title={targetEnvironment?.name}>
                        {targetEnvironment?.name ?? '目标环境待配置'}
                      </span>
                    </div>
                  </article>
                </div>
              </div>
            </div>
          </div>
        </div>

        <article
          className={`${styles.summaryCard} ${styles.taskSummaryCard}`}
          data-task-tone={getTaskTone(currentTask)}
        >
          <div className={styles.cardHeading}>
            <span>执行上下文</span>
            {overview.recentTasks.length > 0 ? (
              <Popover
                arrow={false}
                content={
                  <RecentTasksList currentTaskId={currentTask?.id} tasks={overview.recentTasks} />
                }
                placement="bottomRight"
                trigger="click"
              >
                <button
                  aria-label={`查看最近 ${overview.recentTasks.length} 条任务`}
                  className={styles.recentTasksTrigger}
                  type="button"
                >
                  最近任务 {overview.recentTasks.length}
                  <DownOutlined aria-hidden="true" />
                </button>
              </Popover>
            ) : null}
          </div>
          <div className={styles.endpointBody}>
            <span className={`${styles.endpointIcon} ${styles.taskIcon}`}>
              <ThunderboltOutlined aria-hidden="true" />
            </span>
            <div className={styles.endpointContent}>
              <span>当前任务</span>
              {currentTask ? (
                <Fragment>
                  <div
                    aria-label={hasActiveTask ? '当前执行任务' : '最近任务'}
                    className={styles.taskPrimaryLine}
                  >
                    <strong>{getProjectTaskTypeText(currentTask.type)}</strong>
                    <div className={styles.taskHeadingMeta}>
                      <span className={getTaskStatusClass(currentTask.status)}>
                        {projectTaskStatusText[currentTask.status]}
                      </span>
                      {hasActiveTask && currentTask.progress !== null ? (
                        <span>{currentTask.progress}%</span>
                      ) : null}
                    </div>
                  </div>
                  <small className={styles.taskMessage} title={currentTask.message ?? undefined}>
                    {currentTask.message || (hasActiveTask ? '任务正在执行' : '最近任务已结束')}
                  </small>
                </Fragment>
              ) : (
                <Fragment>
                  <strong>暂无任务记录</strong>
                  <small className={styles.taskMessage}>该项目尚未创建异步任务</small>
                </Fragment>
              )}
            </div>
          </div>
        </article>
      </div>
    </section>
  )
}
