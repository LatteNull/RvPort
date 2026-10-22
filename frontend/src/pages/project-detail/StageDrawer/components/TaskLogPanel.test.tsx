import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'

const { getProjectTaskLogContent, retry, useTaskLogStream } = vi.hoisted(() => ({
  getProjectTaskLogContent: vi.fn(),
  retry: vi.fn(),
  useTaskLogStream: vi.fn()
}))

vi.mock('@/api/project/build-validation', () => ({
  getProjectTaskLogContent,
  getProjectTaskLogDownloadUrl: vi.fn(() => '/download')
}))
vi.mock('../hooks/useTaskLogStream', () => ({ useTaskLogStream }))
vi.mock('@/components/MonacoEditor', () => ({
  default: ({ ariaLabel, value }: { ariaLabel: string; value: string }) => (
    <pre aria-label={ariaLabel}>{value}</pre>
  )
}))

import { TaskLogPanel } from './TaskLogPanel'

function liveResult(overrides: Record<string, unknown> = {}) {
  return {
    buffers: { merged: '', stdout: '', stderr: '' },
    completed: false,
    connectionStatus: 'connected',
    cursor: 0,
    error: null,
    isFetching: false,
    retry,
    truncated: false,
    ...overrides
  }
}

describe('TaskLogPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useTaskLogStream.mockReturnValue(liveResult())
  })

  it('uses local increment buffers while the task is running', async () => {
    useTaskLogStream.mockReturnValue(
      liveResult({
        buffers: {
          merged: '[STDOUT] build\n[STDERR] warning\n',
          stdout: 'build\n',
          stderr: 'warning\n'
        },
        cursor: 8
      })
    )

    renderWithQueryClient(
      <TaskLogPanel
        ariaLabel="构建日志"
        className="panel"
        editorClassName="editor"
        status="RUNNING"
        taskId="task-1"
        title="构建日志"
      />
    )

    expect(screen.getByLabelText('构建日志')).toHaveTextContent('[STDOUT] build')
    await userEvent.click(screen.getByRole('tab', { name: '标准错误' }))
    expect(screen.getByLabelText('构建日志')).toHaveTextContent('warning')
    expect(getProjectTaskLogContent).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: '刷新构建日志' })).not.toBeInTheDocument()
    expect(useTaskLogStream).toHaveBeenCalledWith(
      expect.objectContaining({ enabled: true, taskId: 'task-1' })
    )
  })

  it('loads authoritative paged content directly for a terminal task', async () => {
    getProjectTaskLogContent.mockResolvedValue({
      logs: {
        merged: {
          type: 'merged',
          logId: 'log-1',
          offset: 0,
          lines: 100,
          returnedLines: 1,
          totalLines: 1,
          hasMore: false,
          content: 'finished'
        }
      }
    })

    renderWithQueryClient(
      <TaskLogPanel
        ariaLabel="构建日志"
        className="panel"
        editorClassName="editor"
        status="SUCCEEDED"
        taskId="task-1"
        title="构建日志"
      />
    )

    await waitFor(() => expect(screen.getByLabelText('构建日志')).toHaveTextContent('finished'))
    expect(getProjectTaskLogContent).toHaveBeenCalledWith('task-1', {
      lines: 100,
      offset: 0,
      type: 'merged'
    })
    expect(useTaskLogStream).toHaveBeenCalledWith(
      expect.objectContaining({ enabled: false, taskId: 'task-1' })
    )
    expect(screen.getByRole('button', { name: '下载完整构建日志' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '刷新构建日志' })).toBeInTheDocument()
  })

  it('keeps existing output visible and exposes retry after a live read error', async () => {
    useTaskLogStream.mockReturnValue(
      liveResult({
        buffers: { merged: 'kept output', stdout: 'kept output', stderr: '' },
        error: new Error('offline')
      })
    )

    renderWithQueryClient(
      <TaskLogPanel
        ariaLabel="测试日志"
        className="panel"
        editorClassName="editor"
        status="RUNNING"
        taskId="task-1"
        title="测试日志"
      />
    )

    expect(screen.getByLabelText('测试日志')).toHaveTextContent('kept output')
    await userEvent.click(screen.getByRole('button', { name: '立即重试' }))
    expect(retry).toHaveBeenCalledOnce()
  })
})
