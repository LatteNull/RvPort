import { beforeEach, describe, expect, it, vi } from 'vitest'
const { request } = vi.hoisted(() => ({ request: { get: vi.fn(), post: vi.fn() } }))
vi.mock('../request', () => ({ default: request }))
import {
  createSpecializedAnalysis,
  getSpecializedAnalyses,
  getSpecializedAnalysis,
  getSpecializedAnalysisLatest,
  getSpecializedArtifactDownloadUrl,
  getSpecializedFinding,
  getSpecializedFindings
} from './specialized-analysis'
beforeEach(() => vi.clearAllMocks())
describe('specialized API contract', () => {
  it.each([
    ['memory-order-analysis', 'memory-order'],
    ['floating-point-analysis', 'floating-point']
  ] as const)('uses project-scoped paths for %s', (stage, prefix) => {
    const base = `/projects/p/${prefix}-analyses`
    createSpecializedAnalysis('p', stage)
    expect(request.post).toHaveBeenLastCalledWith(base)
    getSpecializedAnalysisLatest('p', stage)
    expect(request.get).toHaveBeenLastCalledWith(`${base}/latest`)
    getSpecializedAnalyses('p', stage, { page: 2, pageSize: 20 })
    expect(request.get).toHaveBeenLastCalledWith(base, { params: { page: 2, pageSize: 20 } })
    getSpecializedAnalysis('p', stage, 'r')
    expect(request.get).toHaveBeenLastCalledWith(`${base}/r`)
    getSpecializedFindings('p', stage, 'r', {
      page: 3,
      pageSize: 8,
      severity: 'HIGH',
      keyword: 'release'
    })
    expect(request.get).toHaveBeenLastCalledWith(`${base}/r/findings`, {
      params: { page: 3, pageSize: 8, severity: 'HIGH', keyword: 'release' }
    })
    getSpecializedFinding('p', stage, 'f')
    expect(request.get).toHaveBeenLastCalledWith(`/projects/p/${prefix}-findings/f`)
    expect(getSpecializedArtifactDownloadUrl('p', stage, 'r', 'audit')).toBe(
      `/api${base}/r/artifacts:download?format=audit`
    )
  })
})

import { cancelProjectTask } from './task'
it('cancels the official task ID through the shared task endpoint', () => {
  cancelProjectTask('task/one')
  expect(request.post).toHaveBeenLastCalledWith('/tasks/task%2Fone/cancel')
})
