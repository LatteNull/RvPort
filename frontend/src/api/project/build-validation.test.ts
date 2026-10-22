import { beforeEach, describe, expect, it, vi } from 'vitest'

const { request } = vi.hoisted(() => ({
  request: {
    get: vi.fn(),
    post: vi.fn()
  }
}))

vi.mock('../request', () => ({ default: request }))

import { getProjectTaskLogContent, getProjectTaskLogIncrements } from './build-validation'

describe('task log API contract', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    request.get.mockResolvedValue({})
  })

  it('reads running log increments from the last consumed event cursor', () => {
    getProjectTaskLogIncrements('task-1', { afterEventId: 42, limit: 500 })

    expect(request.get).toHaveBeenCalledWith('/tasks/task-1/log-increments', {
      params: { afterEventId: 42, limit: 500 },
      suppressErrorToast: true
    })
  })

  it('keeps completed log history on the content endpoint', () => {
    getProjectTaskLogContent('task-1', { lines: 100, offset: 200, type: 'stderr' })

    expect(request.get).toHaveBeenCalledWith('/tasks/task-1/log-content', {
      params: {
        types: 'stderr',
        lines: 100,
        stderrOffset: 200
      }
    })
  })
})
