import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'
import type { ProjectArchive } from '@/types/project'

import { projectQueryKeys } from '../../queryKeys'
import Archive from '.'

const api = vi.hoisted(() => ({
  createProjectArchive: vi.fn(),
  getProjectArchive: vi.fn(),
  getProjectArchiveLatest: vi.fn(),
  getProjectStageReadiness: vi.fn(),
  getProjectArchiveDownloadUrl: vi.fn((id: string) => `/archive/${id}`)
}))
vi.mock('@/api/project/archive', () => api)
vi.mock('@/api/project/workflow', () => ({
  getProjectStageReadiness: api.getProjectStageReadiness
}))
vi.mock('../components/StageSurface', () => ({
  default: ({
    children,
    title,
    extra,
    onHistory,
    onClose,
    afterOpenChange
  }: {
    children: ReactNode
    title: ReactNode
    extra: ReactNode
    onHistory?: () => void
    onClose: () => void
    afterOpenChange: (open: boolean) => void
  }) => (
    <div>
      {title}
      {extra}
      {children}
      {onHistory && <button onClick={onHistory}>历史入口</button>}
      <button onClick={onClose}>关闭归档</button>
      <button onClick={() => afterOpenChange(false)}>关闭结束</button>
    </div>
  )
}))
vi.mock('./components/ArchiveHistory', () => ({
  ArchiveHistory: ({ projectId, onOpen }: { projectId: string; onOpen: (id: string) => void }) => (
    <button onClick={() => onOpen('old-archive')}>历史归档 {projectId}</button>
  )
}))
const archive: ProjectArchive = {
  id: 'archive-1',
  projectId: 'project-1',
  taskId: 'task-1',
  sourceRevisionId: 'source-1',
  sourceRevision: null,
  name: 'release',
  status: 'SUCCEEDED',
  storedArtifactId: 'stored-1',
  summary: {},
  sizeBytes: 1024,
  sha256: 'hash-1',
  items: [],
  createdAt: '2026-10-28T00:00:00Z',
  updatedAt: '2026-10-28T00:00:00Z'
}
const latest = (result: ProjectArchive | null = archive) => ({
  result,
  execution: null,
  freshness: result ? 'CURRENT' : 'EMPTY'
})

beforeEach(() => {
  api.getProjectStageReadiness.mockResolvedValue({
    context: { sourceRevisionId: 'source-1', runtimeEnvironmentVersion: 1 },
    prerequisites: [{ key: 'ACTIVE_SOURCE', status: 'SATISFIED', details: {} }]
  })
  api.getProjectArchiveLatest.mockResolvedValue(latest())
  api.getProjectArchive.mockResolvedValue({ ...archive, id: 'old-archive', name: '历史包' })
  api.createProjectArchive.mockResolvedValue({ ...archive, status: 'QUEUED' })
})

describe('archive current and historical boundaries', () => {
  it('refreshes current archives and downloads only the selected immutable archive', async () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    const close = vi.fn()
    const view = renderWithQueryClient(<Archive visible projectId="project-1" onClose={close} />)
    await screen.findByText('归档已就绪')
    fireEvent.click(screen.getByRole('button', { name: '下载归档包' }))
    expect(open).toHaveBeenLastCalledWith('/archive/archive-1', '_blank', 'noopener,noreferrer')
    fireEvent.click(screen.getByRole('button', { name: '刷新归档信息' }))
    await waitFor(() => expect(api.getProjectArchiveLatest).toHaveBeenCalledTimes(2))
    fireEvent.click(screen.getByRole('button', { name: '历史入口' }))
    fireEvent.click(await screen.findByRole('button', { name: '历史归档 project-1' }))
    expect(await screen.findByText('历史包')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '下载归档包' }))
    expect(open).toHaveBeenLastCalledWith('/archive/old-archive', '_blank', 'noopener,noreferrer')
    expect(screen.queryByRole('button', { name: '创建项目归档' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '返回归档记录' }))
    const invalidate = vi.spyOn(view.queryClient, 'invalidateQueries')
    fireEvent.click(screen.getByRole('button', { name: '刷新归档记录' }))
    expect(invalidate).toHaveBeenCalledWith({ queryKey: projectQueryKeys.archives('project-1') })
    fireEvent.click(screen.getByRole('button', { name: '关闭归档' }))
    expect(close).toHaveBeenCalledOnce()
    fireEvent.click(screen.getByRole('button', { name: '关闭结束' }))
    expect(screen.getByText('归档已就绪')).toBeInTheDocument()
    open.mockRestore()
  })

  it('retries a failed historical read without discarding its return route', async () => {
    api.getProjectArchive.mockRejectedValueOnce(new Error('read failed'))
    renderWithQueryClient(<Archive visible projectId="project-1" onClose={vi.fn()} />)
    await screen.findByText('归档已就绪')
    fireEvent.click(screen.getByRole('button', { name: '历史入口' }))
    fireEvent.click(await screen.findByRole('button', { name: '历史归档 project-1' }))
    expect(await screen.findByText('归档详情加载失败')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '重新加载' }))
    expect(await screen.findByText('历史包')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '返回归档记录' }))
    expect(screen.getByRole('button', { name: '历史归档 project-1' })).toBeInTheDocument()
  })

  it('offers regeneration for missing stored artifacts and uses execution state from the latest envelope', async () => {
    api.getProjectArchiveLatest.mockResolvedValue(latest({ ...archive, storedArtifactId: null }))
    const view = renderWithQueryClient(<Archive visible projectId="project-1" onClose={vi.fn()} />)
    const create = await screen.findByRole('button', { name: '重新生成归档包' })
    expect(screen.queryByRole('button', { name: '下载归档包' })).not.toBeInTheDocument()
    fireEvent.click(create)
    fireEvent.click(await screen.findByRole('button', { name: '确认创建' }))
    await waitFor(() => expect(api.createProjectArchive).toHaveBeenCalledWith('project-1'))
    act(() =>
      view.queryClient.setQueryData(projectQueryKeys.archiveLatest('project-1'), {
        ...latest(archive),
        execution: { id: 'next-execution', status: 'RUNNING', taskId: 'task-next' }
      })
    )
    expect(await screen.findByText('项目归档正在执行')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '下载归档包' })).not.toBeInTheDocument()
    act(() =>
      view.queryClient.setQueryData(projectQueryKeys.archiveLatest('project-1'), latest(null))
    )
    expect(await screen.findByRole('button', { name: '创建项目归档' })).toBeInTheDocument()
  })
})
