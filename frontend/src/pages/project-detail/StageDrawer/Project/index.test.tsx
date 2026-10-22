import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { type BackendProject, getProject, updateProject } from '@/api/project/projects'
import { renderWithQueryClient } from '@/test/test-utils'

import { StagePresentationContext } from '../components/StagePresentationContext'
import Project from './index'

vi.mock('@/api/project/projects', () => ({ getProject: vi.fn(), updateProject: vi.fn() }))

const project: BackendProject = {
  id: 'project-1',
  name: '迁移项目',
  description: '原描述',
  sourceArch: 'x86_64',
  targetArch: 'riscv64',
  stage: 'PROJECT_CREATED',
  status: 'ACTIVE',
  sourceInputType: null,
  createdBy: 'admin',
  createdAt: '2026-09-29T00:00:00Z',
  updatedAt: null
}

describe('Project description submission', () => {
  it('locks editing while saving and displays the submitted description after success', async () => {
    const user = userEvent.setup()
    let resolveRequest!: (value: BackendProject) => void
    vi.mocked(getProject).mockResolvedValue(project)
    vi.mocked(updateProject).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve
        })
    )
    renderWithQueryClient(
      <StagePresentationContext.Provider value="panel">
        <Project projectId="project-1" visible presentation="panel" onClose={vi.fn()} />
      </StagePresentationContext.Provider>
    )
    await user.click(await screen.findByRole('button', { name: '编辑项目描述' }))
    const input = screen.getByRole('textbox')
    await user.clear(input)
    await user.type(input, '已提交描述')
    await user.click(screen.getByRole('button', { name: /保\s*存/ }))
    await user.click(await screen.findByRole('button', { name: '确认保存' }))
    await waitFor(() => expect(input).toBeDisabled())
    expect(within(input.closest('form')!).getByRole('button', { name: /取\s*消/ })).toBeDisabled()
    expect(updateProject).toHaveBeenCalledWith('project-1', { description: '已提交描述' })
    resolveRequest({ ...project, description: '已提交描述' })
    await waitFor(() => expect(screen.queryByRole('textbox')).not.toBeInTheDocument())
    expect(screen.getByText('已提交描述')).toBeVisible()
  })
})
