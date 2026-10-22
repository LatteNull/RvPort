import { useState } from 'react'
import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TableViewStateProvider from '@/components/BaseTable/TableViewStateProvider'
import { renderWithQueryClient } from '@/test/test-utils'

import { projectQueryKeys } from '../../../queryKeys'
import OrganizedReport from './OrganizedReport'
import {
  dependencyFixtures,
  fileFixture,
  findingFixture,
  moduleFixture,
  reportFixture
} from './report-list-fixtures'
import ReportDependencyList from './ReportDependencyList'
import ReportFileDetail from './ReportFileDetail'
import ReportModuleDetail from './ReportModuleDetail'
import ReportModuleIndex from './ReportModuleIndex'

const { modules, files, findings, inputs, types, context } = vi.hoisted(() => ({
  modules: vi.fn(),
  files: vi.fn(),
  findings: vi.fn(),
  inputs: vi.fn(),
  types: vi.fn(),
  context: vi.fn()
}))
vi.mock('@/api/project/assessment-report', () => ({
  getProjectEvaluationReportCodeModules: modules,
  getProjectEvaluationReportCodeFiles: files,
  getProjectEvaluationReportCodeFindings: findings,
  getProjectEvaluationReportFileContext: context,
  getProjectEvaluationReportFindingTypes: types
}))
vi.mock('../queries', () => ({ getAllEvaluationReportInputs: inputs }))
vi.mock('@/components/MonacoEditor', () => ({ default: () => null }))

type View = 'modules' | 'files' | 'findings' | 'dependencies' | 'report'
let total = 45
function response<T>(item: T, params: { page?: number; pageSize?: number }) {
  const page = params.page ?? 1
  const pageSize = params.pageSize ?? 10
  return {
    items: page <= Math.ceil(total / pageSize) ? [item] : [],
    page,
    pageSize,
    total,
    hasMore: page * pageSize < total
  }
}
function Harness({ view = 'report' }: { view?: View }) {
  const [detail, setDetail] = useState(false)
  const showDetail = () => setDetail(true)
  const content =
    view === 'modules' ? (
      <ReportModuleIndex reportId="report-1" onSelect={showDetail} />
    ) : view === 'files' ? (
      <ReportModuleDetail reportId="report-1" module={moduleFixture} onSelectFile={showDetail} />
    ) : view === 'findings' ? (
      <ReportFileDetail reportId="report-1" module={moduleFixture} file={fileFixture} />
    ) : view === 'dependencies' ? (
      <ReportDependencyList reportId="report-1" onOpenIssue={showDetail} />
    ) : (
      <OrganizedReport
        report={reportFixture}
        canGenerate={false}
        isCreating={false}
        onCreate={() => {}}
        onDownload={() => {}}
        onSelectModule={showDetail}
        onSelectFile={showDetail}
        onOpenIssue={showDetail}
      />
    )
  return (
    <TableViewStateProvider>
      <button onClick={() => setDetail((v) => !v)}>Toggle detail</button>
      {detail ? <p>Inside detail</p> : content}
    </TableViewStateProvider>
  )
}
beforeEach(() => {
  total = 45
  modules.mockImplementation(async (_id, params) => response(moduleFixture, params))
  files.mockImplementation(async (_id, _module, params) => response(fileFixture, params))
  findings.mockImplementation(async (_id, _module, _file, _type, params) =>
    response(findingFixture, params)
  )
  inputs.mockImplementation(async () => dependencyFixtures(total))
  types.mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 200, hasMore: false })
  context.mockResolvedValue({ contextAvailable: false, unavailableReason: 'No context' })
})
describe('report list navigation', () => {
  it('clears a pending module search without reapplying it and retains subsequent drafts', async () => {
    const user = userEvent.setup()
    modules.mockImplementation(async (_id, params) => ({
      items: params.riskLevel ? [] : [moduleFixture],
      page: params.page,
      pageSize: params.pageSize,
      total: params.riskLevel ? 0 : 1,
      hasMore: false
    }))
    renderWithQueryClient(<Harness view="modules" />)
    await screen.findByText('SIMD core')
    await user.click(screen.getByRole('combobox', { name: '模块风险等级' }))
    await user.click(await screen.findByText('高', { selector: '.ant-select-item-option-content' }))
    const clear = await screen.findByRole('button', { name: '清除筛选' })
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'stale' } })
    fireEvent.click(clear)
    expect(screen.getByRole('textbox')).toHaveValue('')
    await screen.findByText('SIMD core')
    await act(() => new Promise((resolve) => setTimeout(resolve, 350)))
    expect(modules.mock.calls.some(([, params]) => params.keyword === 'stale')).toBe(false)
    await waitFor(() =>
      expect(modules.mock.lastCall?.[1]).toEqual(
        expect.objectContaining({ page: 1, keyword: undefined, riskLevel: undefined })
      )
    )
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'fresh' } })
    fireEvent.click(screen.getByRole('button', { name: /SIMD core/ }))
    await screen.findByText('Inside detail')
    fireEvent.click(screen.getByText('Toggle detail'))
    expect(screen.getByRole('textbox')).toHaveValue('fresh')
    await waitFor(() => expect(modules.mock.lastCall?.[1].keyword).toBe('fresh'))
  })

  it.each(['modules', 'files', 'findings', 'dependencies'] as const)(
    'corrects retained %s pagination after fresh data shrinks',
    async (view) => {
      const user = userEvent.setup()
      const { container, queryClient } = renderWithQueryClient(<Harness view={view} />)
      const lastPage = view === 'findings' ? 3 : 5
      await user.click(await screen.findByTitle(String(lastPage)))
      await waitFor(() =>
        expect(container.querySelector('.ant-pagination-item-active')).toHaveTextContent(
          String(lastPage)
        )
      )
      // Wait for the selected page result before opening detail.
      const request =
        view === 'modules'
          ? modules
          : view === 'files'
            ? files
            : view === 'findings'
              ? findings
              : inputs
      if (view !== 'dependencies')
        await waitFor(() =>
          expect(request.mock.lastCall?.at(-1)).toEqual(expect.objectContaining({ page: lastPage }))
        )
      await user.click(screen.getByText('Toggle detail'))
      total = view === 'findings' ? 25 : 15
      queryClient.clear()
      await user.click(screen.getByText('Toggle detail'))
      await waitFor(() =>
        expect(container.querySelector('.ant-pagination-item-active')).toHaveTextContent('2')
      )
      if (view !== 'dependencies')
        expect(request.mock.lastCall?.at(-1)).toEqual(expect.objectContaining({ page: 2 }))
    }
  )

  it.each(['modules', 'files', 'findings', 'dependencies'] as const)(
    'resets retained %s pagination to page one when the total becomes zero',
    async (view) => {
      const user = userEvent.setup()
      const { queryClient } = renderWithQueryClient(<Harness view={view} />)
      await user.click(await screen.findByTitle('2'))
      await user.click(screen.getByText('Toggle detail'))
      total = 0
      queryClient.clear()
      await user.click(screen.getByText('Toggle detail'))
      const request = view === 'modules' ? modules : view === 'files' ? files : findings
      if (view === 'dependencies') {
        await screen.findByText('这份报告没有依赖分析结果')
        // The restored local page is tested by growing the list without remounting.
        total = 15
        await queryClient.invalidateQueries()
        await screen.findByText('Dependency issue 1')
      } else {
        await waitFor(() =>
          expect(request.mock.lastCall?.at(-1)).toEqual(expect.objectContaining({ page: 1 }))
        )
      }
    }
  )

  it('restores the actual dependency details expansion after returning', async () => {
    const user = userEvent.setup()
    const { container } = renderWithQueryClient(<Harness />)
    await screen.findByText('SIMD core')
    await user.click(screen.getByText('依赖清单'))
    await screen.findByText('Dependency issue 1')
    expect(container.querySelector('details')).toHaveAttribute('open')
    await user.click(screen.getByText('Dependency issue 1'))
    await screen.findByText('Inside detail')
    await user.click(screen.getByText('Toggle detail'))
    await screen.findByText('Dependency issue 1')
    expect(container.querySelector('details')).toHaveAttribute('open')
    // Closing is also synchronized, rather than reopening due to a stale saved value.
    await user.click(screen.getByText('依赖清单'))
    await waitFor(() => expect(container.querySelector('details')).not.toHaveAttribute('open'))
    await user.click(screen.getByText('Toggle detail'))
    await user.click(screen.getByText('Toggle detail'))
    expect(container.querySelector('details')).not.toHaveAttribute('open')
  })

  it('does not swallow a module click when pending search starts a slow request', async () => {
    const user = userEvent.setup()
    renderWithQueryClient(<Harness />)
    await screen.findByText('SIMD core')
    modules.mockImplementation(() => new Promise(() => {}))
    const input = screen.getByRole('textbox', { name: '搜索模块、文件或问题' })
    await user.click(input)
    fireEvent.change(input, { target: { value: 'simd' } })
    await user.click(screen.getByRole('button', { name: /SIMD core/ }))
    await screen.findByText('Inside detail')
    await user.click(screen.getByText('Toggle detail'))
    expect(screen.getByRole('textbox', { name: '搜索模块、文件或问题' })).toHaveValue('simd')
    await waitFor(() =>
      expect(modules).toHaveBeenLastCalledWith(
        'report-1',
        expect.objectContaining({ keyword: 'simd', page: 1 })
      )
    )
  })

  it.each([
    'uncached-slow',
    'uncached-fast-empty',
    'uncached-error',
    'cached-empty',
    'cached-other-module'
  ])('preserves a module pointer click and the pending search for %s', async (mode) => {
    const user = userEvent.setup()
    const { queryClient } = renderWithQueryClient(<Harness />)
    await screen.findByText('SIMD core')
    if (mode.startsWith('cached'))
      queryClient.setQueryData(
        projectQueryKeys.evaluationReportCodeModules('report-1', {
          keyword: 'missing',
          page: 1,
          pageSize: 10,
          riskLevel: undefined,
          sortBy: 'highestRisk',
          sortDirection: 'asc'
        }),
        {
          items:
            mode === 'cached-empty'
              ? []
              : [{ ...moduleFixture, moduleKey: 'other', moduleName: 'Other module' }],
          total: mode === 'cached-empty' ? 0 : 1,
          page: 1,
          pageSize: 10,
          hasMore: false
        }
      )
    const input = screen.getByRole('textbox', { name: '搜索模块、文件或问题' })
    await user.click(input)
    fireEvent.change(input, { target: { value: 'missing' } })
    const callsBefore = modules.mock.calls.length
    if (mode === 'uncached-fast-empty')
      modules.mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 10, hasMore: false })
    else if (mode === 'uncached-error') modules.mockRejectedValue(new Error('Request failed'))
    else modules.mockImplementation(() => new Promise(() => {}))
    await user.click(screen.getByRole('button', { name: /SIMD core/ }))
    await screen.findByText('Inside detail')
    expect(modules).toHaveBeenCalledTimes(callsBefore)
    await user.click(screen.getByText('Toggle detail'))
    expect(screen.getByRole('textbox', { name: '搜索模块、文件或问题' })).toHaveValue('missing')
    await waitFor(() =>
      expect(modules).toHaveBeenLastCalledWith(
        'report-1',
        expect.objectContaining({ keyword: 'missing' })
      )
    )
  })

  it('keeps a keyboard-focused module available with a cached empty search', async () => {
    const user = userEvent.setup()
    const { queryClient } = renderWithQueryClient(<Harness />)
    await screen.findByText('SIMD core')
    queryClient.setQueryData(
      projectQueryKeys.evaluationReportCodeModules('report-1', {
        keyword: 'missing',
        page: 1,
        pageSize: 10,
        sortBy: 'highestRisk',
        sortDirection: 'asc'
      }),
      { items: [], total: 0, page: 1, pageSize: 10, hasMore: false }
    )
    const input = screen.getByRole('textbox', { name: '搜索模块、文件或问题' })
    await user.click(input)
    fireEvent.change(input, { target: { value: 'missing' } })
    const moduleButton = screen.getByRole('button', { name: /SIMD core/ })
    // Move focus as Tab would, then activate with Enter.
    fireEvent.blur(input, { relatedTarget: moduleButton })
    moduleButton.focus()
    await user.keyboard('{Enter}')
    await screen.findByText('Inside detail')
    await user.click(screen.getByText('Toggle detail'))
    expect(screen.getByRole('textbox', { name: '搜索模块、文件或问题' })).toHaveValue('missing')
  })

  it('does not reuse clickable modules from another report while the new report loads', async () => {
    const onSelect = vi.fn()
    const { rerender } = renderWithQueryClient(
      <ReportModuleIndex reportId="report-1" onSelect={onSelect} />
    )
    await screen.findByText('SIMD core')
    modules.mockImplementation(() => new Promise(() => {}))
    rerender(<ReportModuleIndex reportId="report-2" onSelect={onSelect} />)
    expect(screen.queryByRole('button', { name: /SIMD core/ })).not.toBeInTheDocument()
    expect(modules).toHaveBeenLastCalledWith('report-2', expect.objectContaining({ page: 1 }))
  })
})
