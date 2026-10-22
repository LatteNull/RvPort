import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'
import type { ProjectListItem } from '@/types/project'

const { createProject, feedback } = vi.hoisted(() => ({
  createProject: vi.fn(),
  feedback: { success: vi.fn(), error: vi.fn() }
}))

vi.mock('@/api/project/projects', () => ({ createProject }))
vi.mock('@/utils/feedback', () => ({ feedback }))

import CreateProjectModal, { type CreateProjectAction } from './index'

const project: ProjectListItem = {
  activeTask: null,
  attention: null,
  buildSummary: null,
  createdAt: '2026-08-31T00:00:00Z',
  currentBaseline: null,
  id: 'project-1',
  lastActivityAt: null,
  latestBuildStatus: null,
  latestScanAt: null,
  latestTestStatus: null,
  name: '新迁移项目',
  primaryAction: null,
  reportSummary: null,
  riskSummary: null,
  sourceArch: 'x86_64',
  stage: 'PROJECT_CREATED',
  status: 'ACTIVE',
  summaryAvailable: false,
  targetArch: 'riscv64',
  testSummary: null
}

describe('CreateProjectModal', () => {
  it.each([
    ['创建并进入工作台', 'open-workbench'],
    ['创建并开始配置环境', 'configure-environment']
  ] as const)('keeps the %s label aligned with its destination action', async (label, action) => {
    createProject.mockResolvedValue(project)
    const onCreated = vi.fn<(project: ProjectListItem, action: CreateProjectAction) => void>()
    const user = userEvent.setup()

    renderWithQueryClient(<CreateProjectModal visible onCancel={vi.fn()} onCreated={onCreated} />)

    await user.type(screen.getByLabelText('项目名称'), '新迁移项目')
    await user.click(screen.getByRole('button', { name: label }))

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(project, action))
    expect(createProject.mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({ name: '新迁移项目', sourceArch: 'x86_64', targetArch: 'riscv64' })
    )
  })
  it('locks validation and captures the first destination before a repeated click', async () => {
    let finish!: (value: ProjectListItem) => void
    createProject.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve
      })
    )
    const onCreated = vi.fn()
    const user = userEvent.setup()
    renderWithQueryClient(<CreateProjectModal visible onCancel={vi.fn()} onCreated={onCreated} />)
    await user.type(screen.getByLabelText('项目名称'), 'protected')
    fireEvent.click(screen.getByRole('button', { name: '创建并进入工作台' }))
    fireEvent.click(screen.getByRole('button', { name: /创建并开始配置环境/ }))
    await waitFor(() => expect(createProject).toHaveBeenCalledOnce())
    expect(screen.getByLabelText('项目名称')).toBeDisabled()
    await act(async () => {
      finish(project)
    })
    expect(onCreated).toHaveBeenCalledWith(project, 'open-workbench')
  })
  it('ignores a delayed creation after the modal closes and reopens', async () => {
    let finish!: (value: ProjectListItem) => void
    createProject.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve
      })
    )
    const onCreated = vi.fn(),
      onCancel = vi.fn()
    const { rerender } = renderWithQueryClient(
      <CreateProjectModal visible onCancel={onCancel} onCreated={onCreated} />
    )
    fireEvent.change(screen.getByLabelText('项目名称'), { target: { value: 'old' } })
    fireEvent.click(screen.getByRole('button', { name: '创建并进入工作台' }))
    await waitFor(() => expect(createProject).toHaveBeenCalledOnce())
    rerender(<CreateProjectModal visible={false} onCancel={onCancel} onCreated={onCreated} />)
    rerender(<CreateProjectModal visible onCancel={onCancel} onCreated={onCreated} />)
    await act(async () => {
      finish(project)
    })
    expect(onCreated).not.toHaveBeenCalled()
    expect(feedback.success).not.toHaveBeenCalled()
  })
})
