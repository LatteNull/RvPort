import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createTestQueryClient, renderWithQueryClient } from '@/test/test-utils'
import type { ProjectArchive } from '@/types/project'

const {
  createProjectArchive,
  getProjectArchive,
  getProjectArchiveLatest,
  getProjectArchives,
  getProjectStageReadiness
} = vi.hoisted(() => ({
  createProjectArchive: vi.fn(),
  getProjectArchive: vi.fn(),
  getProjectArchiveLatest: vi.fn(),
  getProjectArchives: vi.fn(),
  getProjectStageReadiness: vi.fn()
}))

vi.mock('@/api/project/archive', () => ({
  createProjectArchive,
  getProjectArchive,
  getProjectArchiveDownloadUrl: (archiveId: string) => `/api/archives/${archiveId}/download`,
  getProjectArchiveItemDownloadUrl: (archiveId: string, itemId: string, format: string) =>
    `/api/archives/${archiveId}/items/${itemId}?format=${format}`,
  getProjectArchiveLatest,
  getProjectArchives
}))
vi.mock('@/api/project/workflow', () => ({ getProjectStageReadiness }))

vi.mock('@/components/BaseDrawer', () => ({
  default: ({
    children,
    extra,
    footer,
    title,
    onClose
  }: {
    children: React.ReactNode
    extra?: React.ReactNode
    footer?: React.ReactNode
    title: React.ReactNode
    onClose: () => void
  }) => (
    <div>
      {title}
      {extra}
      {children}
      {footer ? <div data-testid="drawer-footer">{footer}</div> : null}
      <button onClick={onClose}>关闭归档 Drawer</button>
    </div>
  )
}))

vi.mock('@/components/BaseTable', () => ({
  default: ({
    columns,
    request
  }: {
    columns: Array<{
      key?: string
      render?: (value: unknown, record: { id: string }) => React.ReactNode
    }>
    request: (query: { page: number; pageSize: number }) => Promise<unknown>
  }) => {
    const action = columns.find((column) => column.key === 'action')
    void request({ page: 1, pageSize: 10 })
    return <div>归档历史表格{action?.render?.(null, { id: 'archive-history-1' })}</div>
  }
}))

import Archive from '.'
import { useArchiveDrawer } from './useArchiveDrawer'

const stage = {
  id: 'archive',
  order: 23,
  status: 'pending' as const,
  subtitle: '交付记录',
  title: '归档'
}
const archive: ProjectArchive = {
  createdAt: '2026-08-18T09:00:00Z',
  id: 'archive-current',
  items: [
    {
      artifactRefs: [
        {
          artifactType: 'REPORT',
          contentType: 'text/html',
          filename: 'report.html',
          format: 'HTML',
          storedArtifactId: 'artifact-1'
        }
      ],
      candidateId: 'candidate-1',
      candidateKey: 'report-1',
      candidateType: 'REPORT',
      createdAt: '2026-08-18T09:00:00Z',
      id: 'item-1',
      metadata: { total: 1 },
      nodeType: 'MIGRATION_REPORT',
      resourceId: 'report-1',
      resourceType: 'REPORT',
      title: '迁移评估报告'
    }
  ],
  name: '项目归档 - fix-1',
  projectId: 'project-1',
  sha256: 'abc',
  sizeBytes: 1024,
  sourceRevision: {
    active: true,
    createdAt: '2026-08-18T08:00:00Z',
    createdBy: 'user-1',
    gitBranch: null,
    gitCommit: null,
    gitUrl: null,
    id: 'source-1',
    projectId: 'project-1',
    revisionType: 'ARCHIVE' as const,
    sourceUri: '/uploads/fix-1.zip',
    versionLabel: 'fix-1',
    versionNote: '修复后的源码'
  },
  sourceRevisionId: 'source-1',
  status: 'SUCCEEDED' as const,
  storedArtifactId: 'artifact-package',
  summary: {},
  taskId: 'task-1',
  updatedAt: '2026-08-18T09:01:00Z'
}

function renderDrawer(onStageChange = vi.fn()) {
  return {
    onStageChange,
    ...renderWithQueryClient(
      <Archive
        projectId="project-1"
        stage={stage}
        visible
        onClose={vi.fn()}
        onStageChange={onStageChange}
      />
    )
  }
}

function mockArchiveState({
  freshness = 'CURRENT',
  prerequisiteStatus = 'SATISFIED',
  result = archive,
  sourceRevisionId = 'source-1'
}: {
  freshness?: 'CURRENT' | 'STALE' | 'EMPTY'
  prerequisiteStatus?: 'SATISFIED' | 'MISSING'
  result?: ProjectArchive | null
  sourceRevisionId?: string | null
} = {}) {
  const context = { runtimeEnvironmentVersion: 1, sourceRevisionId }
  getProjectStageReadiness.mockResolvedValue({
    context,
    prerequisites: [
      {
        details: { count: prerequisiteStatus === 'SATISFIED' ? 1 : 0 },
        key: 'ARCHIVE_CANDIDATES',
        reasonCode:
          sourceRevisionId === null
            ? 'ACTIVE_SOURCE_MISSING'
            : prerequisiteStatus === 'SATISFIED'
              ? 'ARCHIVE_CANDIDATES_READY'
              : 'ARCHIVE_CANDIDATES_MISSING',
        referenceId: null,
        status: prerequisiteStatus
      }
    ],
    stageId: 'archive'
  })
  getProjectArchiveLatest.mockResolvedValue({
    context,
    execution: null,
    freshness,
    result
  })
}

describe('Archive drawer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getProjectArchives.mockResolvedValue({
      hasMore: false,
      items: [],
      page: 1,
      pageSize: 10,
      total: 0
    })
  })

  it('maps archive candidate recovery by key rather than reason code', async () => {
    mockArchiveState({
      freshness: 'EMPTY',
      prerequisiteStatus: 'MISSING',
      result: null,
      sourceRevisionId: null
    })
    const { onStageChange } = renderDrawer()

    expect(await screen.findByText('暂不能执行项目归档')).toBeInTheDocument()
    expect(screen.getByText('可归档内容')).toBeInTheDocument()
    expect(screen.getByText('未满足')).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: '前往优化闭环' }))
    expect(onStageChange).toHaveBeenCalledWith('optimize')
    expect(getProjectStageReadiness).toHaveBeenCalledWith('project-1', 'archive')
    expect(getProjectArchiveLatest).toHaveBeenCalledWith('project-1')
  })

  it('renders every readiness prerequisite by key', async () => {
    mockArchiveState({ freshness: 'EMPTY', prerequisiteStatus: 'MISSING', result: null })
    getProjectStageReadiness.mockResolvedValue({
      context: { runtimeEnvironmentVersion: 1, sourceRevisionId: 'source-1' },
      prerequisites: [
        {
          details: {},
          key: 'ACTIVE_SOURCE',
          reasonCode: 'ACTIVE_SOURCE_READY',
          referenceId: 'source-1',
          status: 'SATISFIED'
        },
        {
          details: { count: 0 },
          key: 'ARCHIVE_CANDIDATES',
          reasonCode: 'ARCHIVE_CANDIDATES_MISSING',
          referenceId: null,
          status: 'MISSING'
        }
      ],
      stageId: 'archive'
    })
    renderDrawer()

    expect(await screen.findByText('当前源码')).toBeInTheDocument()
    expect(screen.getByText('可归档内容')).toBeInTheDocument()
    expect(screen.getByText('已满足')).toBeInTheDocument()
    expect(screen.getByText('未满足')).toBeInTheDocument()
  })

  it('creates an archive without eagerly refreshing current or history queries', async () => {
    mockArchiveState({ freshness: 'EMPTY', result: null })
    createProjectArchive.mockResolvedValue({
      archiveId: 'archive-new',
      sourceRevisionId: 'source-1',
      task: { id: 'task-new', status: 'QUEUED', type: 'ARCHIVE_PROJECT' }
    })
    const queryClient = createTestQueryClient()
    const { result } = renderHook(() => useArchiveDrawer('project-1', true), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      )
    })

    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries')
    await waitFor(() => expect(result.current.canCreate).toBe(true))
    await result.current.create()
    await waitFor(() => expect(createProjectArchive).toHaveBeenCalledWith('project-1'))
    expect(getProjectArchiveLatest).toHaveBeenCalledTimes(1)
    expect(getProjectStageReadiness).toHaveBeenCalledTimes(1)
    expect(invalidateQueries).not.toHaveBeenCalled()
  })

  it('shows a ready prerequisite state before the first archive is created', async () => {
    mockArchiveState({ freshness: 'EMPTY', result: null })
    renderDrawer()

    expect(await screen.findByText('已满足项目归档条件')).toBeInTheDocument()
    expect(screen.getByText('可归档内容')).toBeInTheDocument()
    expect(screen.getByText('已满足（1 项）')).toBeInTheDocument()
    expect(screen.getByRole('status')).toContainElement(
      screen.getByRole('button', { name: '创建项目归档' })
    )
    expect(screen.queryByTestId('drawer-footer')).not.toBeInTheDocument()
  })

  it('shows archive history, opens detail in the drawer, and exposes downloads', async () => {
    mockArchiveState()
    getProjectArchive.mockResolvedValue({ ...archive, id: 'archive-history-1' })
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    renderDrawer()

    expect(await screen.findByText('归档已就绪')).toBeInTheDocument()
    expect(screen.getByText('项目交付归档')).toBeInTheDocument()
    expect(screen.getByText('校验与追溯')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '交付内容' })).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: '下载归档包' }))
    expect(open).toHaveBeenCalledWith(
      '/api/archives/archive-current/download',
      '_blank',
      'noopener,noreferrer'
    )
    await userEvent.setup().click(screen.getByRole('button', { name: '查看历史记录' }))
    expect(await screen.findByText('归档历史表格')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '返回当前归档' })).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: '查看详情' }))
    expect(await screen.findByText('归档记录概览')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '返回归档记录' })).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: '下载 迁移评估报告' }))
    expect(await screen.findByRole('link', { name: 'HTML 文件' })).toHaveAttribute(
      'href',
      '/api/archives/archive-history-1/items/item-1?format=HTML'
    )
  })

  it('identifies missing archive data instead of displaying ambiguous placeholders', async () => {
    mockArchiveState({
      result: {
        ...archive,
        items: [],
        sha256: null,
        sizeBytes: null,
        sourceRevision: null,
        storedArtifactId: null
      }
    })
    renderDrawer()

    expect(await screen.findByText('归档包数据缺失')).toBeInTheDocument()
    expect(screen.getByText('缺失源码版本数据')).toBeInTheDocument()
    expect(screen.getByText('缺失归档包大小数据')).toBeInTheDocument()
    expect(screen.getByText('缺失完整性校验数据')).toBeInTheDocument()
    expect(screen.getByText('缺失归档交付项数据')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重新生成归档包' })).toBeInTheDocument()
  })

  it('presents archive items with business labels and progressive technical details', async () => {
    mockArchiveState({
      result: {
        ...archive,
        items: [
          {
            ...archive.items[0],
            artifactRefs: [],
            candidateType: 'TEST_SUMMARY',
            id: 'item-test-source',
            metadata: {
              durationMs: 1200,
              status: 'SUCCEEDED',
              testBatchRole: 'SOURCE'
            },
            nodeType: 'AUTOMATED_TEST',
            title: '自动化测试 - environment-uuid'
          }
        ]
      }
    })
    renderDrawer()

    expect(await screen.findByText('源端自动化测试')).toBeInTheDocument()
    expect(screen.getAllByText('测试摘要')).toHaveLength(2)
    const details = screen.getByText('查看归档详情').closest('details')
    expect(details).not.toHaveAttribute('open')
    await userEvent.setup().click(screen.getByText('查看归档详情'))
    expect(details).toHaveAttribute('open')
    expect(screen.getByText('测试端')).toBeInTheDocument()
    expect(screen.getByText('源端')).toBeInTheDocument()
    expect(screen.getByText('成功')).toBeInTheDocument()
    expect(screen.getByText('1.2 秒')).toBeInTheDocument()
  })

  it('distinguishes the latest archive from the current source', async () => {
    mockArchiveState({ freshness: 'STALE', sourceRevisionId: 'source-2' })
    renderDrawer()

    expect(
      await screen.findByText('当前版本暂无有效结果，旧结果可从历史记录查看。')
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '创建项目归档' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '下载此归档' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '查看历史记录' })).toBeInTheDocument()
  })

  it('routes users back to the optimization cycle when archive candidates are missing', async () => {
    mockArchiveState({ freshness: 'EMPTY', prerequisiteStatus: 'MISSING', result: null })
    const { onStageChange } = renderDrawer()

    expect(await screen.findByText('暂不能执行项目归档')).toBeInTheDocument()
    expect(screen.getByText('可归档内容')).toBeInTheDocument()
    expect(screen.getByText('未满足')).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: '前往优化闭环' }))
    expect(onStageChange).toHaveBeenCalledWith('optimize')
    expect(screen.queryByRole('button', { name: '创建项目归档' })).not.toBeInTheDocument()
  })

  it('stops current queries in history and while closing', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    mockArchiveState()
    const { queryClient } = renderWithQueryClient(
      <Archive
        projectId="project-1"
        stage={stage}
        visible
        onClose={onClose}
        onStageChange={vi.fn()}
      />
    )

    await user.click(await screen.findByRole('button', { name: '查看历史记录' }))
    const latestCalls = getProjectArchiveLatest.mock.calls.length
    const readinessCalls = getProjectStageReadiness.mock.calls.length
    await user.click(screen.getByRole('button', { name: '刷新归档记录' }))
    await queryClient.invalidateQueries({
      queryKey: ['project-archives', 'project-1', 'latest']
    })
    await queryClient.invalidateQueries({
      queryKey: ['project-stage-readiness', 'project-1', 'archive']
    })
    expect(getProjectArchiveLatest).toHaveBeenCalledTimes(latestCalls)
    expect(getProjectStageReadiness).toHaveBeenCalledTimes(readinessCalls)

    await user.click(screen.getByRole('button', { name: '返回当前归档' }))
    await waitFor(() =>
      expect(getProjectArchiveLatest.mock.calls.length).toBeGreaterThan(latestCalls)
    )
    const closingLatestCalls = getProjectArchiveLatest.mock.calls.length
    const closingReadinessCalls = getProjectStageReadiness.mock.calls.length
    await user.click(screen.getByRole('button', { name: '关闭归档 Drawer' }))
    await queryClient.invalidateQueries({
      queryKey: ['project-archives', 'project-1', 'latest']
    })
    await queryClient.invalidateQueries({
      queryKey: ['project-stage-readiness', 'project-1', 'archive']
    })
    expect(onClose).toHaveBeenCalledOnce()
    expect(getProjectArchiveLatest).toHaveBeenCalledTimes(closingLatestCalls)
    expect(getProjectStageReadiness).toHaveBeenCalledTimes(closingReadinessCalls)
  })
})
