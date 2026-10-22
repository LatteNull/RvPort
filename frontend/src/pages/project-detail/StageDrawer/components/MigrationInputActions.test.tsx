import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { advanceAuthSession } from '@/store/authSession'
import { renderWithQueryClient } from '@/test/test-utils'

import { MigrationInputActions, MigrationInputDetailFooter } from './MigrationInputActions'

const { updateProjectMigrationInput, importProjectMigrationInputs, getProjectMigrationInputs } =
  vi.hoisted(() => ({
    importProjectMigrationInputs: vi.fn(),
    getProjectMigrationInputs: vi.fn(),
    updateProjectMigrationInput: vi.fn()
  }))

vi.mock('@/api/project/migration-input', () => ({
  getProjectMigrationInputs,
  importProjectMigrationInputs,
  updateProjectMigrationInput
}))

const defaultProps = {
  migrationInputRefId: 'migration-input-1',
  projectId: 'project-1',
  sourceRefId: 'result-1',
  sourceRevisionId: 'source-1',
  sourceType: 'DEPENDENCY_RESULT' as const
}

describe('MigrationInputActions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('refreshes report readiness and optimization even from a detail without supplied keys', async () => {
    updateProjectMigrationInput.mockResolvedValue({ id: 'migration-input-1', status: 'CONFIRMED' })
    const { queryClient } = renderWithQueryClient(<MigrationInputActions {...defaultProps} />)
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    await userEvent.click(screen.getByRole('button', { name: '纳入报告' }))
    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({
        queryKey: ['project-stage-readiness', 'project-1', 'report']
      })
    )
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: ['project-optimization-cycles', 'project-1']
    })
  })

  it('only offers inclusion for an unprocessed item', () => {
    renderWithQueryClient(<MigrationInputActions {...defaultProps} initialStatus="CANDIDATE" />)

    expect(screen.getByRole('button', { name: '纳入报告' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '排除' })).not.toBeInTheDocument()
  })

  it('only offers exclusion for an included item', async () => {
    const user = userEvent.setup()
    updateProjectMigrationInput.mockResolvedValue({
      id: 'migration-input-1',
      status: 'EXCLUDED'
    })
    renderWithQueryClient(<MigrationInputActions {...defaultProps} initialStatus="CONFIRMED" />)

    expect(screen.queryByRole('button', { name: '纳入报告' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '排除' }))
    await user.click(await screen.findByRole('button', { name: '确认排除' }))

    expect(updateProjectMigrationInput).toHaveBeenCalledWith('migration-input-1', {
      status: 'EXCLUDED'
    })
  })

  it('only offers inclusion for an excluded item', async () => {
    const user = userEvent.setup()
    updateProjectMigrationInput.mockResolvedValue({
      id: 'migration-input-1',
      status: 'CONFIRMED'
    })
    renderWithQueryClient(<MigrationInputActions {...defaultProps} initialStatus="EXCLUDED" />)

    expect(screen.queryByRole('button', { name: '排除' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '纳入报告' }))

    expect(updateProjectMigrationInput).toHaveBeenCalledWith('migration-input-1', {
      status: 'CONFIRMED'
    })
  })

  it('synchronizes cached list and detail status after exclusion', async () => {
    const user = userEvent.setup()
    updateProjectMigrationInput.mockResolvedValue({
      id: 'migration-input-1',
      status: 'EXCLUDED'
    })
    const detailKey = ['dependency-analysis-result', 'result-1']
    const listKey = ['dependency-analysis-results', 'analysis-1']
    const { queryClient } = renderWithQueryClient(
      <MigrationInputActions
        {...defaultProps}
        initialStatus="CONFIRMED"
        invalidateQueryKeys={[detailKey, listKey]}
      />
    )
    queryClient.setQueryData(detailKey, {
      id: 'result-1',
      migrationInputRefId: 'migration-input-1',
      migrationInputStatus: 'CONFIRMED'
    })
    queryClient.setQueryData(listKey, {
      items: [{ id: 'result-1', migrationInputStatus: 'CONFIRMED' }]
    })

    await user.click(screen.getByRole('button', { name: '排除' }))
    await user.click(await screen.findByRole('button', { name: '确认排除' }))

    await waitFor(() => {
      expect(queryClient.getQueryData(detailKey)).toMatchObject({
        migrationInputStatus: 'EXCLUDED'
      })
      expect(queryClient.getQueryData(listKey)).toMatchObject({
        items: [expect.objectContaining({ migrationInputStatus: 'EXCLUDED' })]
      })
    })
  })

  it('uses the default button size in a detail footer', () => {
    renderWithQueryClient(<MigrationInputDetailFooter {...defaultProps} status="CONFIRMED" />)

    expect(screen.getByText('报告状态')).toBeInTheDocument()
    expect(screen.getByText('已纳入报告')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /排\s*除/ })).not.toHaveClass('ant-btn-sm')
  })
  it('does not issue the second write after auth changes between import and update', async () => {
    let finish!: (value: unknown) => void
    importProjectMigrationInputs.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve
      })
    )
    renderWithQueryClient(<MigrationInputActions {...defaultProps} migrationInputRefId={null} />)
    fireEvent.click(screen.getByRole('button', { name: '纳入报告' }))
    await waitFor(() => expect(importProjectMigrationInputs).toHaveBeenCalledOnce())
    await act(async () => {
      finish({ items: [{ id: 'imported' }] })
      advanceAuthSession()
    })
    expect(updateProjectMigrationInput).not.toHaveBeenCalled()
    expect(getProjectMigrationInputs).not.toHaveBeenCalled()
  })
  it('does not carry a local status override to a different source record', async () => {
    updateProjectMigrationInput.mockResolvedValue({ id: 'migration-input-1', status: 'CONFIRMED' })
    const { rerender } = renderWithQueryClient(
      <MigrationInputActions {...defaultProps} initialStatus="CANDIDATE" />
    )
    fireEvent.click(screen.getByRole('button', { name: '纳入报告' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '排除' })).toBeInTheDocument())
    rerender(
      <MigrationInputActions
        {...defaultProps}
        sourceRefId="different-result"
        initialStatus="CANDIDATE"
      />
    )
    expect(screen.getByRole('button', { name: '纳入报告' })).toBeInTheDocument()
  })

  it('releases the visible pending state when switching records during a write', async () => {
    let finish!: (value: unknown) => void
    updateProjectMigrationInput.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve
      })
    )
    const { rerender } = renderWithQueryClient(<MigrationInputActions {...defaultProps} />)
    fireEvent.click(screen.getByRole('button', { name: '纳入报告' }))
    await waitFor(() => expect(updateProjectMigrationInput).toHaveBeenCalledOnce())
    rerender(
      <MigrationInputActions
        {...defaultProps}
        sourceRefId="result-2"
        migrationInputRefId="input-2"
      />
    )
    expect(screen.getByRole('button', { name: /纳入报告/ })).toBeEnabled()
    expect(screen.getByRole('button', { name: /纳入报告/ })).not.toHaveClass('ant-btn-loading')
    await act(async () => {
      finish({ id: 'migration-input-1', status: 'CONFIRMED' })
    })
    expect(screen.getByRole('button', { name: /纳入报告/ })).toBeEnabled()
  })

  it('looks up the matching input instead of modifying the first unrelated import', async () => {
    importProjectMigrationInputs.mockResolvedValue({
      items: [{ id: 'wrong-input', sourceRefId: 'other-result' }]
    })
    getProjectMigrationInputs.mockResolvedValue({
      items: [{ id: 'matching-input', sourceRefId: 'result-1' }],
      page: 1,
      pageSize: 200,
      total: 1,
      hasMore: false
    })
    updateProjectMigrationInput.mockResolvedValue({ id: 'matching-input', status: 'CONFIRMED' })
    renderWithQueryClient(<MigrationInputActions {...defaultProps} migrationInputRefId={null} />)
    fireEvent.click(screen.getByRole('button', { name: '纳入报告' }))
    await waitFor(() =>
      expect(updateProjectMigrationInput).toHaveBeenCalledWith('matching-input', {
        status: 'CONFIRMED'
      })
    )
    expect(updateProjectMigrationInput).toHaveBeenCalledOnce()
  })

  it('discards the optimistic status when the authentication session changes', async () => {
    updateProjectMigrationInput.mockResolvedValue({ id: 'migration-input-1', status: 'CONFIRMED' })
    renderWithQueryClient(<MigrationInputActions {...defaultProps} initialStatus="CANDIDATE" />)
    fireEvent.click(screen.getByRole('button', { name: '纳入报告' }))
    await screen.findByRole('button', { name: '排除' })
    act(() => advanceAuthSession())
    expect(screen.getByRole('button', { name: '纳入报告' })).toBeEnabled()
  })
})
