import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'

const { cancelAdminWorkerTask, getAdminWorker } = vi.hoisted(() => ({
  cancelAdminWorkerTask: vi.fn(),
  getAdminWorker: vi.fn()
}))

vi.mock('@/api/admin/workers', () => ({ cancelAdminWorkerTask, getAdminWorker }))
vi.mock('@/components/BaseDrawer', () => ({
  default: ({
    children,
    footer,
    title,
    visible
  }: {
    children: ReactNode
    footer?: ReactNode
    title?: ReactNode
    visible?: boolean
  }) =>
    visible ? (
      <section>
        <h2>{title}</h2>
        {children}
        {footer}
      </section>
    ) : null
}))

import WorkerDetailDrawer from './WorkerDetailDrawer'

describe('WorkerDetailDrawer', () => {
  it('shows full instance information and current running tasks', async () => {
    getAdminWorker.mockResolvedValue({
      runningTasks: [
        {
          message: '正在执行测试',
          progress: 35,
          projectId: 'project-1',
          projectName: 'RISC-V 迁移项目',
          startedAt: '2026-09-02T08:05:00Z',
          status: 'RUNNING',
          taskId: 'task-1',
          type: 'AUTOMATED_TEST'
        }
      ],
      worker: {
        activeConcurrency: 1,
        activeTaskCount: 1,
        appVersion: '1.2.0',
        concurrencyLimit: 4,
        createdAt: '2026-09-01T08:00:00Z',
        hostname: 'build-host',
        instanceId: 'worker-1-full-instance-id',
        lastHeartbeatAt: '2026-09-02T08:10:00Z',
        processId: 1024,
        startedAt: '2026-09-01T08:00:00Z',
        status: 'ONLINE',
        updatedAt: '2026-09-02T08:10:00Z'
      }
    })

    renderWithQueryClient(
      <WorkerDetailDrawer
        workerInstanceId="worker-1-full-instance-id"
        onClose={vi.fn()}
        onConfigure={vi.fn()}
      />
    )

    expect(await screen.findByText('worker-1-full-instance-id')).toBeInTheDocument()
    expect(screen.getByText('build-host')).toBeInTheDocument()
    expect(screen.getByText('期望 4 / 实际 1')).toBeInTheDocument()
    expect(screen.getByText('RISC-V 迁移项目')).toBeInTheDocument()
    expect(screen.getByText('正在执行测试')).toBeInTheDocument()
    expect(getAdminWorker).toHaveBeenCalledWith('worker-1-full-instance-id')
  })

  it('cancels a running task and refreshes Worker details', async () => {
    const user = userEvent.setup()
    getAdminWorker.mockResolvedValue({
      runningTasks: [
        {
          message: '正在执行测试',
          progress: 35,
          projectId: 'project-1',
          projectName: 'RISC-V 迁移项目',
          startedAt: '2026-09-02T08:05:00Z',
          status: 'RUNNING',
          taskId: 'task-1',
          type: 'AUTOMATED_TEST'
        }
      ],
      worker: {
        activeConcurrency: 1,
        activeTaskCount: 1,
        appVersion: '1.2.0',
        concurrencyLimit: 4,
        createdAt: '2026-09-01T08:00:00Z',
        hostname: 'build-host',
        instanceId: 'worker-1-full-instance-id',
        lastHeartbeatAt: '2026-09-02T08:10:00Z',
        processId: 1024,
        startedAt: '2026-09-01T08:00:00Z',
        status: 'ONLINE',
        updatedAt: '2026-09-02T08:10:00Z'
      }
    })
    cancelAdminWorkerTask.mockResolvedValue({ id: 'task-1', status: 'CANCELLED' })

    renderWithQueryClient(
      <WorkerDetailDrawer
        workerInstanceId="worker-1-full-instance-id"
        onClose={vi.fn()}
        onConfigure={vi.fn()}
      />
    )

    await user.click(await screen.findByRole('button', { name: '取消' }))
    await user.click(await screen.findByRole('button', { name: '确认取消' }))

    expect(cancelAdminWorkerTask.mock.calls[0]?.[0]).toBe('task-1')
    await waitFor(() => expect(getAdminWorker).toHaveBeenCalledTimes(2))
  })
})
