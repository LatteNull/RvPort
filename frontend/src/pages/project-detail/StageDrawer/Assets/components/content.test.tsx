import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Form } from 'antd'
import { describe, expect, it, vi } from 'vitest'

import type { ProjectSourceArtifact, UpdateProjectSourceFromGitRequest } from '@/types/project'

import type { UploadValues } from '../types'
import { AssetsOverview } from './content'

const artifact: ProjectSourceArtifact = {
  active: true,
  branch: 'main',
  id: 'source-1',
  ref: '8b3d2a1c85f36b0479fd2868cfc405646b73064f',
  repositoryUrl: 'https://example.com/rvport.git',
  type: 'GIT',
  updatedAt: '2026-08-27T08:00:00Z',
  version: 'source-version-8b3d2a1c85f36b0479fd2868cfc405646b73064f',
  versionNote: ''
}

function OverviewHarness({
  currentArtifact,
  onStartUpdate = vi.fn()
}: {
  currentArtifact?: ProjectSourceArtifact
  onStartUpdate?: () => void
}) {
  const [uploadForm] = Form.useForm<UploadValues>()
  const [gitForm] = Form.useForm<UpdateProjectSourceFromGitRequest>()

  return (
    <AssetsOverview
      artifact={currentArtifact}
      gitForm={gitForm}
      isEditing={false}
      isSaving={false}
      sourceMode="git"
      sourceModeLocked
      uploadForm={uploadForm}
      onCancel={vi.fn()}
      onGitSubmit={async () => undefined}
      onSourceModeChange={vi.fn()}
      onStartUpdate={onStartUpdate}
      onUploadSubmit={async () => undefined}
    />
  )
}

function EditableGitHarness({
  onSubmit,
  isSaving = false
}: {
  onSubmit: () => Promise<void>
  isSaving?: boolean
}) {
  const [uploadForm] = Form.useForm<UploadValues>()
  const [gitForm] = Form.useForm<UpdateProjectSourceFromGitRequest>()

  return (
    <AssetsOverview
      artifact={artifact}
      gitForm={gitForm}
      isEditing
      isSaving={isSaving}
      sourceMode="git"
      sourceModeLocked={false}
      uploadForm={uploadForm}
      onCancel={vi.fn()}
      onGitSubmit={onSubmit}
      onSourceModeChange={vi.fn()}
      onStartUpdate={vi.fn()}
      onUploadSubmit={async () => undefined}
    />
  )
}

describe('AssetsOverview', () => {
  it('locks source inputs, source mode and cancel while submitting, and unlocks when settled', () => {
    const onSubmit = vi.fn(async () => undefined)
    const { rerender } = render(<EditableGitHarness isSaving onSubmit={onSubmit} />)
    expect(screen.getByLabelText('仓库地址')).toBeDisabled()
    expect(screen.getByLabelText('Ref')).toBeDisabled()
    expect(screen.getByRole('button', { name: /取\s*消/ })).toBeDisabled()
    for (const option of screen.getAllByRole('radio')) expect(option).toBeDisabled()
    rerender(<EditableGitHarness onSubmit={onSubmit} />)
    expect(screen.getByLabelText('仓库地址')).toBeEnabled()
    expect(screen.getByRole('button', { name: /取\s*消/ })).toBeEnabled()
  })
  it('presents the active Git source as the source used by subsequent stages', () => {
    render(<OverviewHarness currentArtifact={artifact} />)

    expect(screen.getByText('当前有效源码')).toBeInTheDocument()
    expect(screen.getByText('后续扫描与构建将使用此版本。')).toBeInTheDocument()
    expect(screen.getByText('当前版本')).toBeInTheDocument()
    expect(screen.getByText(artifact.version)).toBeVisible()
    expect(screen.getByRole('link', { name: artifact.repositoryUrl! })).toHaveAttribute(
      'href',
      artifact.repositoryUrl
    )
    expect(screen.getByText('Git 分支')).toBeInTheDocument()
    expect(screen.getByText('Git Commit')).toBeInTheDocument()
    expect(screen.getByText(artifact.ref!)).toBeVisible()
  })

  it('labels the update action as replacing the current source', async () => {
    const onStartUpdate = vi.fn()
    const user = userEvent.setup()

    render(<OverviewHarness currentArtifact={artifact} onStartUpdate={onStartUpdate} />)

    await user.click(screen.getByRole('button', { name: '更新当前源码' }))
    expect(onStartUpdate).toHaveBeenCalledOnce()
  })

  it('rejects credentials embedded in an HTTP repository URL before submitting', async () => {
    const onSubmit = vi.fn(async () => undefined)
    const user = userEvent.setup()
    render(<EditableGitHarness onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText('仓库地址'), 'https://user:token@example.com/repo.git')
    await user.type(screen.getByLabelText('Ref'), 'main')
    await user.click(screen.getByRole('button', { name: /更\s*新/ }))

    await waitFor(() => {
      expect(
        screen.getByText('仓库地址中不能包含用户名、密码或 Token，请填写在下方凭据字段中')
      ).toBeVisible()
    })
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('contains a rejected submit promise after the request layer reports it', async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error('request failed'))
    const user = userEvent.setup()
    render(<EditableGitHarness onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText('仓库地址'), 'https://example.com/repo.git')
    await user.type(screen.getByLabelText('Ref'), 'main')
    await user.click(screen.getByRole('button', { name: /更\s*新/ }))

    expect(onSubmit).toHaveBeenCalledOnce()
    expect(await screen.findByText('request failed')).toBeVisible()
  })
})
