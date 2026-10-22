import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'
import type { WorkerInstance } from '@/types/admin/workers'

import ConcurrencyModal from './ConcurrencyModal'

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

describe('ConcurrencyModal', () => {
  it('keeps invalid values in the form without submitting and allows correction', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    renderWithQueryClient(
      <ConcurrencyModal
        loading={false}
        visible
        worker={worker}
        onCancel={vi.fn()}
        onSubmit={onSubmit}
      />
    )
    await userEvent.clear(screen.getByRole('spinbutton'))
    await userEvent.click(screen.getByRole('button', { name: '保存设置' }))
    expect(await screen.findByText('请输入任务消费并发')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
    await waitFor(() => expect(screen.getByRole('spinbutton')).toBeEnabled())
    await userEvent.type(screen.getByRole('spinbutton'), '2')
    await userEvent.click(screen.getByRole('button', { name: /保存设置/ }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledExactlyOnceWith(2))
  })

  it('populates the current limit and allows zero to pause new task intake', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    const user = userEvent.setup()

    renderWithQueryClient(
      <ConcurrencyModal
        loading={false}
        visible
        worker={worker}
        onCancel={vi.fn()}
        onSubmit={onSubmit}
      />
    )

    expect(screen.getByText('worker-1')).toBeInTheDocument()
    expect(screen.getByRole('spinbutton')).toHaveValue('4')
    expect(screen.getByText(/设置为 0 会暂停该 Worker 接收新任务/)).toBeInTheDocument()

    await user.clear(screen.getByRole('spinbutton'))
    await user.type(screen.getByRole('spinbutton'), '0')
    await user.click(screen.getByRole('button', { name: '保存设置' }))

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(0))
  })

  it('populates the limit when the modal is opened after its initial render', async () => {
    const { rerender } = renderWithQueryClient(
      <ConcurrencyModal
        loading={false}
        visible={false}
        worker={null}
        onCancel={vi.fn()}
        onSubmit={vi.fn()}
      />
    )

    rerender(
      <ConcurrencyModal
        loading={false}
        visible
        worker={worker}
        onCancel={vi.fn()}
        onSubmit={vi.fn()}
      />
    )

    expect(await screen.findByRole('spinbutton')).toHaveValue('4')
  })
})
