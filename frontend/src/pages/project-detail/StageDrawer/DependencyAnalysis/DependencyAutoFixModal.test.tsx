import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'

import DependencyAutoFixModal from './DependencyAutoFixModal'

const { createProjectDependencyAutoFix, getProjectDependencyAutoFixCandidates } = vi.hoisted(
  () => ({
    createProjectDependencyAutoFix: vi.fn(),
    getProjectDependencyAutoFixCandidates: vi.fn()
  })
)

vi.mock('@/api/project/dependency-analysis', () => ({
  createProjectDependencyAutoFix,
  getProjectDependencyAutoFixCandidates
}))

describe('DependencyAutoFixModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    createProjectDependencyAutoFix.mockResolvedValue({
      autoFixRunId: 'fix-1',
      selectedCount: 1,
      taskId: 'task-1'
    })
  })

  it('disables submission when the analysis has no repairable candidates', async () => {
    getProjectDependencyAutoFixCandidates.mockResolvedValue({
      hasMore: false,
      items: [],
      page: 1,
      pageSize: 200,
      total: 0
    })

    renderWithQueryClient(<DependencyAutoFixModal analysisId="analysis-1" open onClose={vi.fn()} />)

    expect(await screen.findByText('本次分析没有可自动修复的依赖')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '修复选中的依赖' })).toBeDisabled()
  })

  it('shows a retry action when candidate loading fails', async () => {
    getProjectDependencyAutoFixCandidates
      .mockRejectedValueOnce(new Error('network error'))
      .mockResolvedValueOnce({ hasMore: false, items: [], page: 1, pageSize: 200, total: 0 })

    renderWithQueryClient(<DependencyAutoFixModal analysisId="analysis-1" open onClose={vi.fn()} />)

    expect(await screen.findByText('自动修复候选项加载失败')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '重新加载' }))

    expect(getProjectDependencyAutoFixCandidates).toHaveBeenCalledTimes(2)
  })
})
