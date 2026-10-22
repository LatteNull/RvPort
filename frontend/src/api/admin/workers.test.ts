import { describe, expect, it, vi } from 'vitest'

const { request } = vi.hoisted(() => ({
  request: {
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
    put: vi.fn()
  }
}))

vi.mock('../request', () => ({
  default: request,
  LONG_RUNNING_REQUEST_TIMEOUT_MS: 3_600_000
}))

import {
  cancelAdminWorkerTask,
  getAdminWorker,
  getAdminWorkers,
  updateAdminWorkerConcurrency
} from '@/api/admin/workers'

describe('workers API contract', () => {
  it('uses the Worker management endpoints and preserves list filters', () => {
    getAdminWorkers({
      hasRunningTasks: true,
      hostname: 'build-host',
      instanceId: 'worker/one',
      page: 2,
      pageSize: 20,
      sortBy: 'lastHeartbeatAt',
      sortDirection: 'desc',
      status: 'ONLINE'
    })
    getAdminWorker('worker/one')
    cancelAdminWorkerTask('task/one')
    updateAdminWorkerConcurrency('worker/one', 0)

    expect(request.get).toHaveBeenCalledWith('/admin/workers', {
      params: {
        hasRunningTasks: true,
        hostname: 'build-host',
        instanceId: 'worker/one',
        page: 2,
        pageSize: 20,
        sortBy: 'lastHeartbeatAt',
        sortDirection: 'desc',
        status: 'ONLINE'
      }
    })
    expect(request.get).toHaveBeenCalledWith('/admin/workers/worker%2Fone')
    expect(request.post).toHaveBeenCalledWith('/tasks/task%2Fone/cancel')
    expect(request.put).toHaveBeenCalledWith('/admin/workers/worker%2Fone/concurrency', {
      concurrencyLimit: 0
    })
  })
})
