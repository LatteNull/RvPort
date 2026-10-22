import { useState } from 'react'
import { DownloadOutlined, ReloadOutlined } from '@ant-design/icons'
import { useInfiniteQuery } from '@tanstack/react-query'
import { Button, Tabs, Tooltip } from 'antd'

import {
  getProjectTaskLogContent,
  getProjectTaskLogDownloadUrl
} from '@/api/project/build-validation'
import ContentState from '@/components/ContentState'
import MonacoEditor from '@/components/MonacoEditor'
import type { ProjectTaskLogContent, ProjectTaskLogContentType } from '@/types/project/task-log'

import { projectQueryKeys } from '../../queryKeys'
import { useTaskLogStream } from '../hooks/useTaskLogStream'
import { composeTaskLogContent, getTaskLogLineNumberOffset } from '../utils/taskLog'
import { isTerminalTaskLogStatus } from '../utils/taskLogStream'

import styles from './TaskLogPanel.module.scss'

interface TaskLogPanelProps {
  ariaLabel: string
  className: string
  editorClassName: string
  fallbackContent?: string | null
  status: string
  taskId: string
  title: string
  onTaskCompleted?: () => void
}

export function TaskLogPanel(props: TaskLogPanelProps) {
  const {
    ariaLabel,
    className,
    editorClassName,
    fallbackContent,
    status,
    taskId,
    title,
    onTaskCompleted
  } = props
  const [contentType, setContentType] = useState<ProjectTaskLogContentType>('merged')
  const terminal = isTerminalTaskLogStatus(status)
  const liveLogs = useTaskLogStream({
    enabled: !terminal,
    taskId,
    onCompleted: onTaskCompleted
  })
  const historical = terminal || liveLogs.completed
  const logsQuery = useInfiniteQuery({
    queryKey: projectQueryKeys.taskLog(taskId, contentType),
    queryFn: ({ pageParam }) =>
      getProjectTaskLogContent(taskId, {
        lines: 100,
        offset: pageParam,
        type: contentType
      }).then((response) => response.logs[contentType]),
    enabled: historical,
    initialPageParam: 0,
    getNextPageParam: (lastPage) =>
      lastPage?.hasMore ? lastPage.offset + lastPage.returnedLines : undefined,
    gcTime: 0
  })
  const pages =
    logsQuery.data?.pages.filter((page): page is ProjectTaskLogContent => Boolean(page)) ?? []
  const latestContent = pages[0]
  const fallback = contentType === 'merged' ? fallbackContent?.trim() : null
  const liveContent = liveLogs.buffers[contentType]
  const historicalContent = composeTaskLogContent(pages)
  const content = historicalContent || liveContent || fallback || ''
  const showEditor = Boolean(content || latestContent?.logId)
  const isLoading = historical
    ? logsQuery.isLoading && !liveContent
    : liveLogs.isFetching && !liveContent

  let connectionLabel: string | null = null
  if (!historical && liveLogs.connectionStatus === 'connecting') {
    connectionLabel = '正在连接实时日志'
  } else if (!historical && liveLogs.connectionStatus === 'reconnecting') {
    connectionLabel = '实时日志连接中断，正在重连'
  } else if (liveLogs.completed && !historicalContent && !logsQuery.isError) {
    connectionLabel = '正在整理最终日志'
  }

  return (
    <section className={`${styles.root} ${className}`}>
      <div className={styles.frame}>
        <div className={styles.toolbar}>
          <Tabs
            activeKey={contentType}
            className={styles.tabs}
            items={[
              { key: 'merged', label: '合并输出' },
              { key: 'stdout', label: '标准输出' },
              { key: 'stderr', label: '标准错误' }
            ]}
            onChange={(type) => setContentType(type as ProjectTaskLogContentType)}
          />
          {connectionLabel ? (
            <span aria-live="polite" className={styles.connectionStatus}>
              {connectionLabel}
            </span>
          ) : null}
          {historical && latestContent?.logId ? (
            <Tooltip title={`下载完整${title}`}>
              <Button
                aria-label={`下载完整${title}`}
                className={styles.refresh}
                icon={<DownloadOutlined />}
                type="text"
                onClick={() =>
                  window.open(
                    getProjectTaskLogDownloadUrl(taskId, latestContent.logId ?? ''),
                    '_blank',
                    'noopener,noreferrer'
                  )
                }
              />
            </Tooltip>
          ) : null}
          {historical ? (
            <Tooltip title={`刷新${title}`}>
              <Button
                aria-label={`刷新${title}`}
                className={styles.refresh}
                icon={<ReloadOutlined />}
                loading={logsQuery.isFetching}
                type="text"
                onClick={() => void logsQuery.refetch()}
              />
            </Tooltip>
          ) : null}
        </div>
        {liveLogs.truncated && !historical ? (
          <p className={styles.notice}>
            为保持页面流畅，部分较早实时日志已省略；任务结束后可查看完整日志。
          </p>
        ) : null}
        {liveLogs.error && !historical ? (
          <div className={styles.error} role="alert">
            <span>实时日志读取失败，已保留现有内容。</span>
            <Button size="small" type="link" onClick={liveLogs.retry}>
              立即重试
            </Button>
          </div>
        ) : null}
        {historical && logsQuery.isError && liveContent ? (
          <div className={styles.error} role="alert">
            <span>完整日志加载失败，下方保留的是实时日志，内容可能不完整。</span>
            <Button size="small" type="link" onClick={() => void logsQuery.refetch()}>
              重试
            </Button>
          </div>
        ) : null}
        <div className={styles.viewport}>
          {historical && logsQuery.isError && !liveContent ? (
            <ContentState kind="error" compact description={`${title}加载失败`}>
              <Button type="primary" onClick={() => void logsQuery.refetch()}>
                重试
              </Button>
            </ContentState>
          ) : isLoading ? (
            <ContentState kind="loading" compact description={`${title}加载中`} />
          ) : showEditor ? (
            <MonacoEditor
              ariaLabel={ariaLabel}
              className={`${styles.editor} ${editorClassName}`}
              hasEarlierContent={historical && logsQuery.hasNextPage}
              height="100%"
              isFetchingEarlierContent={historical && logsQuery.isFetchingNextPage}
              language="plaintext"
              lineNumberOffset={historical ? getTaskLogLineNumberOffset(pages) : 1}
              readOnly
              scrollToBottomOnValueChange
              totalLines={historical ? latestContent?.totalLines : undefined}
              value={content || '日志内容为空'}
              wordWrap="off"
              onLoadEarlierContent={historical ? () => logsQuery.fetchNextPage() : undefined}
            />
          ) : (
            <ContentState description={historical ? '暂未生成此类日志' : '等待任务输出日志'} />
          )}
        </div>
      </div>
    </section>
  )
}
