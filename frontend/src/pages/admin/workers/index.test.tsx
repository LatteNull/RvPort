import { Fragment, type ReactNode } from 'react'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'
import type { WorkerInstance } from '@/types/admin/workers'

const { api, table } = vi.hoisted(() => ({
  api: {
    getAdminWorkers: vi.fn(),
    updateAdminWorkerConcurrency: vi.fn()
  },
  table: {
    props: null as Record<string, unknown> | null,
    reload: vi.fn()
  }
}))

const worker: WorkerInstance = {
  activeConcurrency: 2,
  activeTaskCount: 2,
  appVersion: '1.2.0',
  concurrencyLimit: 4,
  createdAt: '2026-09-01T08:00:00Z',
  hostname: 'build-host',
  instanceId: 'worker-1',
  lastHeartbeatAt: '2026-09-02T08:00:00Z',
  processId: 1024,
  startedAt: '2026-09-01T08:00:00Z',
  status: 'ONLINE',
  updatedAt: '2026-09-02T08:00:00Z'
}

vi.mock('@/api/admin/workers', () => api)
vi.mock('@/components/BaseTable', async () => {
  const React = await import('react')
  return {
    default: React.forwardRef((props: Record<string, unknown>, ref) => {
      table.props = props
      React.useImperativeHandle(ref, () => ({ reload: table.reload }))
      const columns = props.columns as Array<{
        key?: string
        render?: (value: unknown, record: WorkerInstance) => ReactNode
      }>
      const actions = columns.find((column) => column.key === 'actions')
      const toolbar = props.toolbar as { actions?: ReactNode }
      return (
        <Fragment>
          {toolbar.actions}
          {actions?.render?.(undefined, worker)}
        </Fragment>
      )
    })
  }
})
vi.mock('./components/WorkerDetailDrawer', () => ({ default: () => null }))
vi.mock('./components/ConcurrencyModal', () => ({
  default: ({
    onSubmit,
    visible
  }: {
    onSubmit: (value: number) => Promise<void>
    visible: boolean
  }) => (visible ? <button onClick={() => void onSubmit(0)}>确认并发为 0</button> : null)
}))

import AdminWorkersPage from '.'

describe('AdminWorkersPage', () => {
  it('maps list filters to the backend contract and updates Worker concurrency', async () => {
    api.getAdminWorkers.mockResolvedValue({ items: [], page: 2, pageSize: 20, total: 0 })
    api.updateAdminWorkerConcurrency.mockResolvedValue({ ...worker, concurrencyLimit: 0 })
    table.reload.mockResolvedValue(undefined)
    const user = userEvent.setup()

    renderWithQueryClient(<AdminWorkersPage />)

    expect(table.props?.autoHeight).toBeUndefined()
    const request = table.props?.request as (query: Record<string, unknown>) => Promise<unknown>
    await request({
      hasRunningTasks: 'true',
      hostname: 'build-host',
      instanceId: 'worker-1',
      page: 2,
      pageSize: 20,
      sortBy: 'lastHeartbeatAt',
      sortOrder: 'descend',
      status: 'ONLINE'
    })
    expect(api.getAdminWorkers).toHaveBeenCalledWith({
      hasRunningTasks: true,
      hostname: 'build-host',
      instanceId: 'worker-1',
      page: 2,
      pageSize: 20,
      sortBy: 'lastHeartbeatAt',
      sortDirection: 'desc',
      status: 'ONLINE'
    })

    await user.hover(screen.getByRole('button', { name: '查看 Worker 详情' }))
    expect(await screen.findByRole('tooltip')).toHaveTextContent('查看 Worker 详情')

    await user.click(screen.getByRole('button', { name: '设置 Worker 并发' }))
    await user.click(screen.getByRole('button', { name: '确认并发为 0' }))

    await waitFor(() => {
      expect(api.updateAdminWorkerConcurrency).toHaveBeenCalledWith('worker-1', 0)
      expect(table.reload).toHaveBeenCalled()
    })
  })
})
