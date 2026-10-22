import { useEffect } from 'react'
import { createMemoryRouter, RouterProvider, useLocation, useNavigate } from 'react-router'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { useProjectPipelineData, subscribe, unsubscribe } = vi.hoisted(() => ({
  subscribe: vi.fn(),
  unsubscribe: vi.fn(),
  useProjectPipelineData: vi.fn()
}))

vi.mock('@/components/ProjectArchitectureFlow', () => ({ default: () => null }))
vi.mock('./useProjectPipelineData', () => ({ useProjectPipelineData }))
vi.mock('./useProjectTaskEvents', () => ({
  useProjectTaskEvents: () =>
    useEffect(() => {
      subscribe()
      return unsubscribe
    }, [])
}))
vi.mock('./Workflow', () => ({
  default: ({
    onStageClick,
    focusedStageId,
    focusRequest,
    selectedStageId
  }: {
    onStageClick: (stageId: string) => void
    focusedStageId?: string
    focusRequest?: number
    selectedStageId?: string
  }) => (
    <div
      aria-label="模拟 Workflow 画布"
      data-focused-stage={focusedStageId}
      data-focus-request={focusRequest}
      data-selected-stage={selectedStageId}
    >
      <button onClick={() => onStageClick('env')}>打开环境</button>
      <button onClick={() => onStageClick('assets')}>打开源码</button>
      <button onClick={() => onStageClick('report')}>打开报告</button>
    </div>
  )
}))
vi.mock('./StageDrawer', () => ({
  default: ({
    onClose,
    onDirtyChange,
    onStageChange,
    presentation,
    stage,
    visible
  }: {
    onClose: () => void
    onDirtyChange?: (dirty: boolean) => void
    onStageChange: (stageId: string) => void
    presentation?: 'drawer' | 'panel'
    stage?: { id: string; status: string } | null
    visible: boolean
  }) =>
    visible && stage && presentation === 'panel' ? (
      <section aria-label={stage.id === 'env' ? '环境内容' : '阶段内容'}>
        {stage.id === 'env' ? (
          <input
            aria-label="环境试填内容"
            onChange={(event) => onDirtyChange?.(Boolean(event.target.value))}
          />
        ) : null}
        <span>{`${stage.id}:${stage.status}`}</span>
        <button onClick={() => onStageChange('report')}>切换报告</button>
      </section>
    ) : visible && stage?.id === 'env' ? (
      <aside aria-label="阶段抽屉">
        <span>{`${stage.id}:${stage.status}`}</span>
        <input aria-label="抽屉局部输入" />
        <button onClick={onClose}>关闭抽屉</button>
      </aside>
    ) : visible && stage ? (
      <aside aria-label="阶段抽屉">
        <span>{`${stage.id}:${stage.status}`}</span>
        <button onClick={() => onStageChange('report')}>切换报告</button>
        <button onClick={onClose}>关闭抽屉</button>
      </aside>
    ) : null
}))
vi.mock('./StageDrawer/stageLoaders', () => ({
  preloadEnvironmentStage: vi.fn(() => Promise.resolve())
}))

import ProjectPipelineWorkbenchPage from './index'
import { preloadEnvironmentStage } from './StageDrawer/stageLoaders'

const overview = {
  project: {
    id: 'project-1',
    name: '迁移项目',
    sourceArch: 'x86_64',
    targetArch: 'riscv64'
  },
  currentContext: {
    activeSourceRevision: {
      active: true,
      id: 'source-1',
      type: 'GIT',
      version: 'main@abc123',
      versionNote: '',
      updatedAt: '2026-09-04T00:00:00Z',
      repositoryUrl: 'https://example.com/rvport.git'
    },
    runtimeEnvironments: {
      projectId: 'project-1',
      version: 3,
      sourceEnvironment: { id: 'env-x86', name: '构建机 A', architecture: 'x86_64' },
      targetEnvironment: { id: 'env-riscv', name: '验证机 B', architecture: 'riscv64' }
    }
  },
  workflow: {
    recommendedStageId: 'report',
    stages: [{ id: 'report', status: 'RUNNING', reasonCode: 'REPORT_RUNNING' }]
  },
  recentTasks: [
    {
      createdAt: '2026-09-10T01:00:00Z',
      id: 'task-1',
      message: '执行 KB Scanner',
      progress: 45,
      startedAt: '2026-09-10T01:02:00Z',
      status: 'RUNNING',
      type: 'KB_SCAN'
    },
    {
      createdAt: '2026-09-09T01:00:00Z',
      finishedAt: '2026-09-09T01:05:00Z',
      id: 'task-2',
      message: '源码部署完成',
      progress: 100,
      status: 'SUCCEEDED',
      type: 'SOURCE_DEPLOY'
    }
  ],
  latestTaskEventId: 42
}

function LocationProbe() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <div>
      <output aria-label="当前地址">{`${location.pathname}${location.search}`}</output>
      <button onClick={() => void navigate(-1)}>后退</button>
      <button onClick={() => void navigate(1)}>前进</button>
      <button onClick={() => void navigate('/projects/project-2/workflow/env')}>切换项目</button>
    </div>
  )
}

function renderPage(initialEntry: string) {
  const router = createMemoryRouter(
    [
      { path: '/home', element: <div>项目列表页</div> },
      {
        path: '/projects/:projectId/*',
        element: (
          <>
            <LocationProbe />
            <ProjectPipelineWorkbenchPage />
          </>
        )
      }
    ],
    { initialEntries: [initialEntry] }
  )
  return render(<RouterProvider router={router} />)
}

describe('ProjectPipelineWorkbenchPage view navigation', () => {
  beforeEach(() => {
    subscribe.mockClear()
    unsubscribe.mockClear()
    useProjectPipelineData.mockReturnValue({
      currentStageTitle: '项目基础配置',
      isError: false,
      isLoading: false,
      overview,
      refetch: vi.fn(),
      workflowStatus: {
        activeEdgeIds: [],
        currentStageId: 'project',
        projectId: 'project-1',
        stages: [
          { id: 'assets', status: 'DONE' },
          { id: 'report', status: 'RUNNING' }
        ],
        updatedAt: '2026-08-31T00:00:00Z'
      }
    })
  })

  it('switches between the workflow drawer and environment step view', async () => {
    renderPage('/projects/project-1/workflow')
    const overviewRegion = screen.getByRole('region', { name: '项目总览' })
    const fullSummary = screen.getByRole('region', { name: '项目流水线摘要' })
    expect(fullSummary).toBeVisible()
    expect(within(overviewRegion).getByRole('group', { name: '视图切换' })).toBeVisible()
    expect(within(fullSummary).queryByRole('group', { name: '视图切换' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '项目总览' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '项目紧凑摘要' })).not.toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: '打开环境' }))
    await waitFor(() => expect(screen.getByLabelText('阶段抽屉')).toHaveTextContent('env:pending'))
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/workflow/env')
    fireEvent.click(screen.getByText('Step'))
    expect(await screen.findByRole('region', { name: '阶段工作区' })).toBeVisible()
    expect(screen.getByRole('region', { name: '项目紧凑摘要' })).toBeVisible()
    const stepNavigation = screen.getByRole('navigation', { name: '阶段导航' })
    expect(stepNavigation).toBeVisible()
    expect(within(stepNavigation).getByRole('group', { name: '视图切换' })).toBeVisible()
    expect(
      within(screen.getByLabelText('项目页头')).queryByRole('group', { name: '视图切换' })
    ).not.toBeInTheDocument()
    expect(overviewRegion).toHaveAttribute('aria-hidden', 'true')
    expect(overviewRegion).toHaveAttribute('inert')
    expect(screen.queryByLabelText('阶段抽屉')).not.toBeInTheDocument()
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/steps/env')
    fireEvent.click(screen.getByText('Workflow'))
    expect(screen.getByRole('region', { name: '项目总览' })).toBe(overviewRegion)
    expect(overviewRegion).not.toHaveAttribute('aria-hidden')
    expect(overviewRegion).not.toHaveAttribute('inert')
    expect(screen.queryByRole('region', { name: '阶段工作区' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('阶段抽屉')).not.toBeInTheDocument()
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/workflow')
    expect(screen.getByLabelText('模拟 Workflow 画布')).toHaveAttribute('data-focused-stage', 'env')
    fireEvent.click(screen.getByRole('button', { name: '打开报告' }))
    expect(screen.getByLabelText('模拟 Workflow 画布')).toHaveAttribute(
      'data-selected-stage',
      'report'
    )
    expect(screen.getByLabelText('模拟 Workflow 画布')).toHaveAttribute('data-focused-stage', 'env')
    expect(subscribe).toHaveBeenCalledTimes(1)
    expect(unsubscribe).not.toHaveBeenCalled()
  })

  it('isolates Workflow drawer state when changing projects with immediately available data', async () => {
    renderPage('/projects/project-1/workflow/env')
    const input = await screen.findByRole('textbox', { name: '抽屉局部输入' })
    fireEvent.change(input, { target: { value: '旧项目的局部内容' } })
    expect(input).toHaveValue('旧项目的局部内容')
    fireEvent.click(screen.getByRole('button', { name: '切换项目' }))
    await waitFor(() =>
      expect(screen.getByLabelText('当前地址')).toHaveTextContent(
        '/projects/project-2/workflow/env'
      )
    )
    expect(screen.getByRole('textbox', { name: '抽屉局部输入' })).toHaveValue('')
  })

  it('opens and closes a drawer without changing the canvas focus target', async () => {
    renderPage('/projects/project-1/workflow')
    const canvas = screen.getByLabelText('模拟 Workflow 画布')
    expect(canvas).not.toHaveAttribute('data-focused-stage')

    fireEvent.click(screen.getByRole('button', { name: '打开环境' }))
    await waitFor(() => expect(screen.getByLabelText('阶段抽屉')).toBeVisible())
    expect(canvas).toHaveAttribute('data-selected-stage', 'env')
    expect(canvas).not.toHaveAttribute('data-focused-stage')

    fireEvent.click(screen.getByRole('button', { name: '关闭抽屉' }))
    await waitFor(() => expect(screen.queryByLabelText('阶段抽屉')).not.toBeInTheDocument())
    expect(canvas).not.toHaveAttribute('data-selected-stage')
    expect(canvas).not.toHaveAttribute('data-focused-stage')
  })

  it('keeps all stage navigation in Step view and restores it with browser history', async () => {
    renderPage('/projects/project-1/steps/env')
    expect(screen.getByLabelText('环境内容')).toBeVisible()
    expect(screen.getByLabelText('项目页头')).toBeVisible()
    expect(screen.getByRole('heading', { name: '迁移项目' })).toBeInTheDocument()
    const compactSummary = screen.getByRole('region', { name: '项目紧凑摘要' })
    expect(
      within(compactSummary).queryByRole('button', { name: '返回项目总览' })
    ).not.toBeInTheDocument()
    expect(within(compactSummary).getByLabelText('当前迁移上下文')).toBeVisible()
    expect(within(compactSummary).getByLabelText('执行上下文')).toBeVisible()
    expect(within(compactSummary).queryByText('项目总览')).not.toBeInTheDocument()
    const navigation = screen.getByRole('navigation', { name: '阶段导航' })
    expect(within(navigation).getByRole('button', { name: /^环境管理/ })).toHaveAttribute(
      'aria-current',
      'step'
    )
    fireEvent.click(within(navigation).getByRole('button', { name: /^源码管理/ }))
    expect(screen.getByLabelText('阶段内容')).toHaveTextContent('assets:done')
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/steps/assets')
    expect(screen.queryByLabelText('环境内容')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '后退' }))
    await waitFor(() => expect(screen.getByLabelText('环境内容')).toBeVisible())
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/steps/env')
    fireEvent.click(screen.getByRole('button', { name: '前进' }))
    await waitFor(() => expect(screen.getByLabelText('阶段内容')).toHaveTextContent('assets:done'))
    expect(subscribe).toHaveBeenCalledTimes(1)
  })

  it('opens the same stage when switching from a Workflow drawer to Step', async () => {
    renderPage('/projects/project-1/workflow/report')
    expect(screen.getByLabelText('阶段抽屉')).toHaveTextContent('report:running')

    fireEvent.click(screen.getByText('Step'))

    expect(await screen.findByLabelText('阶段内容')).toHaveTextContent('report:running')
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/steps/report')
    expect(screen.queryByLabelText('阶段抽屉')).not.toBeInTheDocument()
  })

  it('opens the current stage when switching from the Workflow overview', async () => {
    renderPage('/projects/project-1/workflow')

    fireEvent.click(screen.getByText('Step'))

    expect(await screen.findByLabelText('阶段内容')).toHaveTextContent('project:pending')
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/steps/project')
  })

  it('keeps in-content stage links in Step view', () => {
    renderPage('/projects/project-1/steps/assets')

    fireEvent.click(screen.getByRole('button', { name: '切换报告' }))

    expect(screen.getByLabelText('阶段内容')).toHaveTextContent('report:running')
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/steps/report')
  })

  it('issues a new focus request every time the same Step stage returns to Workflow', async () => {
    renderPage('/projects/project-1/steps/report')
    fireEvent.click(screen.getByText('Workflow'))
    const canvas = await screen.findByLabelText('模拟 Workflow 画布')
    expect(canvas).toHaveAttribute('data-focus-request', '1')
    fireEvent.click(screen.getByText('Step'))
    fireEvent.click(screen.getByRole('button', { name: /^评估报告/ }))
    fireEvent.click(screen.getByText('Workflow'))
    expect(canvas).toHaveAttribute('data-focused-stage', 'report')
    expect(canvas).toHaveAttribute('data-focus-request', '2')
  })

  it('blocks a view switch while environment changes are unsaved', async () => {
    renderPage('/projects/project-1/steps/env')
    fireEvent.change(screen.getByRole('textbox', { name: '环境试填内容' }), {
      target: { value: '尚未保存' }
    })

    fireEvent.click(screen.getByText('Workflow'))
    expect((await screen.findAllByText('放弃未保存的更改？')).length).toBeGreaterThan(0)
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/steps/env')

    fireEvent.click(screen.getByRole('button', { name: '继续编辑' }))
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/steps/env')

    fireEvent.click(screen.getByText('Workflow'))
    fireEvent.click(await screen.findByRole('button', { name: '放弃更改' }))
    await waitFor(() => expect(screen.getByLabelText('当前地址')).toHaveTextContent('/workflow'))
  })

  it('uses the navigation heading switcher as the only overview return entry', () => {
    renderPage('/projects/project-1/steps/env')
    const summary = screen.getByRole('region', { name: '项目紧凑摘要' })
    const navigation = screen.getByRole('navigation', { name: '阶段导航' })
    expect(within(navigation).getByRole('group', { name: '视图切换' })).toBeVisible()
    expect(within(summary).queryByRole('group', { name: '视图切换' })).not.toBeInTheDocument()
    expect(within(summary).getByText('迁移项目')).toBeVisible()
    expect(within(summary).queryByRole('button', { name: '返回项目总览' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /项目菜单/ })).not.toBeInTheDocument()
  })

  it('restores a drawer from a copied or refreshed backend stage panel URL', () => {
    renderPage('/projects/project-1/workflow/assets')

    expect(screen.getByLabelText('阶段抽屉')).toHaveTextContent('assets:done')
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/workflow/assets')
  })

  it('shows the current source and environments without stage or next-step summaries', () => {
    renderPage('/projects/project-1/workflow')

    expect(screen.getByText('当前迁移上下文')).toBeInTheDocument()
    expect(screen.getByText('执行上下文')).toBeInTheDocument()
    expect(screen.getByText('当前源码')).toBeInTheDocument()
    const sourceLink = screen.getByRole('link', { name: 'rvport' })
    expect(sourceLink).toHaveAttribute('href', 'https://example.com/rvport.git')
    expect(sourceLink).toHaveAttribute('target', '_blank')
    expect(screen.getByText('构建机 A')).toBeInTheDocument()
    expect(screen.getByText('验证机 B')).toBeInTheDocument()
    expect(screen.queryByText('当前阶段')).not.toBeInTheDocument()
    expect(screen.queryByText('下一步')).not.toBeInTheDocument()
  })

  it('shows the active task from the V2 overview', () => {
    renderPage('/projects/project-1/workflow')

    const task = screen.getByLabelText('当前执行任务')
    expect(task).toHaveTextContent('知识库扫描')
    expect(task).toHaveTextContent('执行中')
    expect(task).toHaveTextContent('45%')
    expect(screen.getByText('执行 KB Scanner')).toBeInTheDocument()
  })

  it('opens the recent task history without replacing the primary task summary', async () => {
    renderPage('/projects/project-1/workflow')

    fireEvent.click(screen.getByRole('button', { name: '查看最近 2 条任务' }))

    const list = await screen.findByRole('list', { name: '最近任务列表' })
    expect(list.children).toHaveLength(2)
    expect(list.children[0]).toHaveTextContent('知识库扫描')
    expect(list.children[0]).toHaveTextContent('当前')
    expect(list.children[0]).toHaveTextContent('45%')
    expect(list.children[1]).toHaveTextContent('源码部署')
    expect(list.children[1]).toHaveTextContent('已完成')
  })

  it('falls back to the latest terminal task when no task is active', () => {
    useProjectPipelineData.mockReturnValue({
      ...useProjectPipelineData(),
      overview: {
        ...overview,
        recentTasks: [
          {
            id: 'task-2',
            message: 'KB Scanner 执行失败',
            progress: 15,
            status: 'FAILED',
            type: 'KB_SCAN'
          }
        ]
      }
    })

    renderPage('/projects/project-1/workflow')

    const task = screen.getByLabelText('最近任务')
    expect(task).toHaveTextContent('知识库扫描')
    expect(task).toHaveTextContent('失败')
    expect(screen.getByText('KB Scanner 执行失败')).toBeInTheDocument()
  })

  it('uses push for module changes so browser back and forward restore the drawer', async () => {
    renderPage('/projects/project-1/workflow/assets')

    fireEvent.click(screen.getByRole('button', { name: '切换报告' }))
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/workflow/report')
    expect(screen.getByLabelText('阶段抽屉')).toHaveTextContent('report:running')

    fireEvent.click(screen.getByRole('button', { name: '后退' }))
    await waitFor(() => expect(screen.getByLabelText('阶段抽屉')).toHaveTextContent('assets:done'))

    fireEvent.click(screen.getByRole('button', { name: '前进' }))
    await waitFor(() =>
      expect(screen.getByLabelText('阶段抽屉')).toHaveTextContent('report:running')
    )
  })

  it('closes the drawer with replace navigation', async () => {
    renderPage('/projects/project-1/workflow/assets')

    fireEvent.click(screen.getByRole('button', { name: '关闭抽屉' }))

    await waitFor(() => expect(screen.queryByLabelText('阶段抽屉')).not.toBeInTheDocument())
    expect(screen.getByLabelText('当前地址')).toHaveTextContent('/projects/project-1/workflow')
  })

  it.each(['missing-panel', 'sbom'])(
    'corrects unavailable stage %s to the workflow overview',
    async (panel) => {
      renderPage(`/projects/project-1/workflow/${panel}`)

      await waitFor(() =>
        expect(screen.getByLabelText('当前地址')).toHaveTextContent('/projects/project-1/workflow')
      )
      expect(screen.queryByLabelText('阶段抽屉')).not.toBeInTheDocument()
    }
  )

  it('keeps a blocked but viewable panel open as navigation state', () => {
    useProjectPipelineData.mockReturnValue({
      ...useProjectPipelineData(),
      workflowStatus: {
        ...useProjectPipelineData().workflowStatus,
        stages: [{ id: 'assets', status: 'BLOCKED' }]
      }
    })

    renderPage('/projects/project-1/workflow/assets')

    expect(screen.getByLabelText('阶段抽屉')).toHaveTextContent('assets:blocked')
  })
  it.each(['resolve', 'reject'])(
    'does not navigate after old environment preload %s',
    async (outcome) => {
      let finish!: () => void
      vi.mocked(preloadEnvironmentStage).mockImplementation(
        () =>
          new Promise<void>((yes, no) => {
            finish = () => (outcome === 'resolve' ? yes() : no(new Error('chunk failed')))
          })
      )
      renderPage('/projects/project-1/workflow')
      fireEvent.click(await screen.findByText('打开环境'))
      await waitFor(() =>
        expect(screen.getByLabelText('当前地址')).toHaveTextContent('/workflow/env')
      )
      fireEvent.click(screen.getByText('打开报告'))
      await waitFor(() =>
        expect(screen.getByLabelText('当前地址')).toHaveTextContent('/workflow/report')
      )
      await (
        await import('@testing-library/react')
      ).act(async () => {
        finish()
      })
      expect(screen.getByLabelText('当前地址')).toHaveTextContent('/workflow/report')
    }
  )
})
