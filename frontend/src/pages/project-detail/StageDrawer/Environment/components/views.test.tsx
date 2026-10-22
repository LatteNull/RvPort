import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'

const { taskLogPanel } = vi.hoisted(() => ({ taskLogPanel: vi.fn() }))

vi.mock('../../components/TaskLogPanel', () => ({
  TaskLogPanel: (props: Record<string, unknown>) => {
    taskLogPanel(props)
    return <div>统一任务日志面板</div>
  }
}))

import { LogView } from './views'

describe('environment execution log view', () => {
  it('delegates running and completed log behavior to the shared task log panel', () => {
    const onTaskCompleted = vi.fn()
    renderWithQueryClient(
      <LogView
        execution={{
          id: 'task-env-1',
          environmentId: 'env-1',
          scriptType: 'CUSTOM',
          scriptName: '检查工具链',
          submittedAt: '2026-09-11T00:00:00Z',
          startedAt: '2026-09-11T00:00:01Z',
          finishedAt: null,
          progress: 50,
          message: '执行中',
          scriptSha256: null,
          scriptLength: 10,
          logEventCount: 2,
          exitCode: null,
          status: 'RUNNING',
          stdout: '',
          stderr: ''
        }}
        onTaskCompleted={onTaskCompleted}
      />
    )

    expect(screen.getByText('统一任务日志面板')).toBeInTheDocument()
    expect(taskLogPanel).toHaveBeenCalledWith(
      expect.objectContaining({
        status: 'RUNNING',
        taskId: 'task-env-1',
        onTaskCompleted
      })
    )
  })
})
