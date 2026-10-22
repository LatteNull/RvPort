import { useRef, useState } from 'react'
import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from 'antd'
import type { Key } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { createTestQueryClient, renderWithQueryClient } from '@/test/test-utils'
import type { PageResponse } from '@/types'

import BaseTable from './index'
import TableViewStateProvider from './TableViewStateProvider'
import type { BaseTableHandle, BaseTableRequest } from './types'

interface RecordItem {
  id: string
  name: string
  status: 'ACTIVE' | 'DISABLED'
}

interface Filters {
  keyword?: string
  status?: RecordItem['status']
}

type SortField = 'name'

const records: RecordItem[] = [
  { id: 'record-1', name: 'alpha', status: 'ACTIVE' },
  { id: 'record-2', name: 'beta', status: 'DISABLED' }
]

function createResponse(
  items: RecordItem[],
  page: number,
  pageSize: number,
  total = items.length
): PageResponse<RecordItem> {
  return { hasMore: page * pageSize < total, items, page, pageSize, total }
}

function createRequest() {
  return vi.fn<BaseTableRequest<RecordItem, Filters, SortField>>(async (query) => {
    const keyword = query.keyword?.toLowerCase()
    const items = keyword ? records.filter((record) => record.name.includes(keyword)) : records
    const sortedItems = [...items].sort((left, right) => {
      if (query.sortBy !== 'name') {
        return 0
      }

      const result = left.name.localeCompare(right.name)
      return query.sortOrder === 'descend' ? -result : result
    })

    return createResponse(sortedItems, query.page, query.pageSize, 40)
  })
}

function TestTable({
  request,
  onOpenDetail,
  initialFilters
}: {
  request: BaseTableRequest<RecordItem, Filters, SortField>
  onOpenDetail?: () => void
  initialFilters?: Filters
}) {
  const tableRef = useRef<BaseTableHandle>(null)

  return (
    <>
      <Button onClick={() => void tableRef.current?.reload()}>刷新列表</Button>
      <div style={{ height: 520 }}>
        <BaseTable<RecordItem, Filters, SortField>
          ref={tableRef}
          columns={[
            { dataIndex: 'name', title: '名称', sorter: true },
            { dataIndex: 'status', title: '状态' },
            ...(onOpenDetail
              ? [
                  {
                    title: '操作',
                    key: 'actions',
                    render: (_value: unknown, record: RecordItem) => (
                      <Button onClick={onOpenDetail}>详情 {record.name}</Button>
                    )
                  }
                ]
              : [])
          ]}
          pagination={{ initialPageSize: 20 }}
          queryKey={['base-table-test']}
          request={request}
          rowKey="id"
          toolbar={{
            filters: {
              initialValues: initialFilters,
              fields: [
                { name: 'keyword', placeholder: '搜索名称', type: 'search' },
                {
                  name: 'status',
                  options: [
                    { label: '启用', value: 'ACTIVE' },
                    { label: '停用', value: 'DISABLED' }
                  ],
                  placeholder: '状态',
                  type: 'select'
                },
                {
                  key: 'custom-filter',
                  name: 'keyword',
                  render: () => <span>自定义筛选</span>,
                  type: 'custom'
                }
              ]
            },
            actions: <Button type="primary">新建记录</Button>
          }}
        />
      </div>
    </>
  )
}

function DetailHarness({
  request,
  initialFilters
}: {
  request: BaseTableRequest<RecordItem, Filters, SortField>
  initialFilters?: Filters
}) {
  const [detail, setDetail] = useState(false)
  return (
    <TableViewStateProvider>
      <button onClick={() => setDetail((value) => !value)}>切换详情</button>
      {detail ? (
        <p>详情</p>
      ) : (
        <TestTable
          request={request}
          initialFilters={initialFilters}
          onOpenDetail={() => setDetail(true)}
        />
      )}
    </TableViewStateProvider>
  )
}

function SelectionTable({
  request
}: {
  request: BaseTableRequest<RecordItem, Filters, SortField>
}) {
  const [selectedRowKeys, setSelectedRowKeys] = useState<Key[]>([])

  return (
    <div style={{ height: 400 }}>
      <BaseTable<RecordItem, Filters, SortField>
        columns={[{ dataIndex: 'name', title: '名称' }]}
        queryKey={['base-table-selection']}
        request={request}
        rowKey="id"
        rowSelection={{ onChange: setSelectedRowKeys, selectedRowKeys }}
        selection={<Button>批量处理</Button>}
      />
    </div>
  )
}

describe('BaseTable', () => {
  it.each(['', 'old'])(
    'clears pending search and retains new drafts after clear (applied keyword: %s)',
    async (keyword) => {
      const request = vi.fn<BaseTableRequest<RecordItem, Filters, SortField>>(async (query) =>
        createResponse(query.status ? [] : records, query.page, query.pageSize)
      )
      renderWithQueryClient(
        <DetailHarness request={request} initialFilters={{ keyword, status: 'DISABLED' }} />
      )
      const clear = await screen.findByRole('button', { name: '清空筛选' })
      fireEvent.change(screen.getByPlaceholderText('搜索名称'), { target: { value: 'stale' } })
      fireEvent.click(clear)
      expect(screen.getByPlaceholderText('搜索名称')).toHaveValue('')
      await screen.findByText('alpha')
      await act(() => new Promise((resolve) => setTimeout(resolve, 350)))
      expect(request.mock.calls.some(([query]) => query.keyword === 'stale')).toBe(false)
      expect(request.mock.lastCall?.[0]).toEqual(expect.objectContaining({ page: 1 }))
      expect(request.mock.lastCall?.[0].status).toBeUndefined()
      fireEvent.change(screen.getByPlaceholderText('搜索名称'), { target: { value: 'beta' } })
      fireEvent.click(screen.getByRole('button', { name: '详情 alpha' }))
      fireEvent.click(screen.getByText('切换详情'))
      expect(screen.getByPlaceholderText('搜索名称')).toHaveValue('beta')
      await waitFor(() => expect(request.mock.lastCall?.[0].keyword).toBe('beta'))
    }
  )

  it('retains a search entered immediately before clicking into detail', async () => {
    const user = userEvent.setup()
    const request = createRequest()
    renderWithQueryClient(<DetailHarness request={request} />)
    await screen.findByText('alpha')
    const input = screen.getByPlaceholderText('搜索名称')
    await user.click(input)
    fireEvent.change(input, { target: { value: 'beta' } })
    // The unapplied draft is retained without a blur-triggered query before navigation.
    await user.click(screen.getByText('切换详情'))
    await user.click(screen.getByText('切换详情'))
    expect(screen.getByPlaceholderText('搜索名称')).toHaveValue('beta')
    await waitFor(() =>
      expect(request).toHaveBeenLastCalledWith(
        expect.objectContaining({ keyword: 'beta', page: 1 })
      )
    )
    await screen.findByText('beta')
  })

  it.each([40, 0])('corrects a restored page after the total shrinks to %i', async (nextTotal) => {
    const user = userEvent.setup()
    let total = 45
    const request = vi.fn<BaseTableRequest<RecordItem, Filters, SortField>>(async (query) =>
      createResponse(
        query.page <= Math.ceil(total / query.pageSize) ? records : [],
        query.page,
        query.pageSize,
        total
      )
    )
    const { container } = renderWithQueryClient(<DetailHarness request={request} />)
    await screen.findByText('alpha')
    await user.type(screen.getByPlaceholderText('搜索名称'), 'alpha')
    await waitFor(() =>
      expect(request).toHaveBeenLastCalledWith(expect.objectContaining({ keyword: 'alpha' }))
    )
    await user.click(screen.getByRole('columnheader', { name: '名称' }))
    await user.click(screen.getAllByRole('combobox').at(-1)!)
    await user.click(await screen.findByText('10 / page'))
    await user.click(screen.getByTitle('5'))
    await waitFor(() =>
      expect(request).toHaveBeenLastCalledWith(expect.objectContaining({ page: 5 }))
    )
    await screen.findByText('alpha')
    await user.click(screen.getByText('切换详情'))
    const pageOneRequests = request.mock.calls.filter(([query]) => query.page === 1).length
    total = nextTotal
    await user.click(screen.getByText('切换详情'))
    await waitFor(() =>
      expect(request).toHaveBeenLastCalledWith(
        expect.objectContaining({
          keyword: 'alpha',
          page: nextTotal === 0 ? 1 : 4,
          pageSize: 10,
          sortBy: 'name',
          sortOrder: 'ascend'
        })
      )
    )
    if (nextTotal > 0) {
      await screen.findByText('alpha')
      expect(container.querySelector('.ant-pagination-item-active')).toHaveTextContent('4')
    } else {
      await screen.findByText('暂无符合条件的数据')
      expect(request.mock.calls.filter(([query]) => query.page === 1)).toHaveLength(
        pageOneRequests + 1
      )
    }
  })

  it.each(['fast-empty', 'slow', 'failure'])(
    'preserves an actual row detail click with pending search and %s responses',
    async (mode) => {
      const user = userEvent.setup()
      const request = createRequest()
      renderWithQueryClient(<DetailHarness request={request} />)
      await screen.findByText('alpha')
      const input = screen.getByPlaceholderText('搜索名称')
      await user.click(input)
      const detailButton = screen.getByRole('button', { name: '详情 alpha' })
      fireEvent.change(input, { target: { value: 'missing' } })
      const callsBefore = request.mock.calls.length
      if (mode === 'fast-empty')
        request.mockImplementation(async (params) =>
          createResponse([], params.page, params.pageSize, 0)
        )
      else if (mode === 'failure') request.mockRejectedValue(new Error('Request failed'))
      else request.mockImplementation(() => new Promise(() => {}))
      // 同一事件轮次点击，明确验证防抖尚未到期的场景，不依赖机器执行速度。
      fireEvent.click(detailButton)
      expect(screen.getByText('详情')).toBeInTheDocument()
      expect(request).toHaveBeenCalledTimes(callsBefore)
      await user.click(screen.getByText('切换详情'))
      expect(screen.getByPlaceholderText('搜索名称')).toHaveValue('missing')
      await waitFor(() =>
        expect(request).toHaveBeenLastCalledWith(
          expect.objectContaining({ keyword: 'missing', page: 1 })
        )
      )
    }
  )

  it('restores filter controls, pagination and the visible sort direction after returning from detail', async () => {
    const user = userEvent.setup()
    const request = createRequest()
    renderWithQueryClient(<DetailHarness request={request} />)
    await screen.findByText('alpha')
    await user.type(screen.getByPlaceholderText('搜索名称'), 'beta')
    await waitFor(() =>
      expect(request).toHaveBeenLastCalledWith(expect.objectContaining({ keyword: 'beta' }))
    )
    await user.click(screen.getAllByRole('combobox').at(-1)!)
    await user.click(await screen.findByText('10 / page'))
    await waitFor(() =>
      expect(request).toHaveBeenLastCalledWith(expect.objectContaining({ pageSize: 10 }))
    )
    await user.click(screen.getByRole('columnheader', { name: '名称' }))
    await user.click(screen.getByTitle('2'))
    await waitFor(() =>
      expect(request).toHaveBeenLastCalledWith(
        expect.objectContaining({
          keyword: 'beta',
          page: 2,
          pageSize: 10,
          sortBy: 'name',
          sortOrder: 'ascend'
        })
      )
    )
    await user.click(screen.getByText('切换详情'))
    await user.click(screen.getByText('切换详情'))
    expect(screen.getByPlaceholderText('搜索名称')).toHaveValue('beta')
    await waitFor(() =>
      expect(request).toHaveBeenLastCalledWith(
        expect.objectContaining({
          keyword: 'beta',
          page: 2,
          pageSize: 10,
          sortBy: 'name',
          sortOrder: 'ascend'
        })
      )
    )
    expect(screen.getByRole('columnheader', { name: '名称' })).toHaveAttribute(
      'aria-sort',
      'ascending'
    )
    await user.click(screen.getByRole('columnheader', { name: '名称' }))
    await waitFor(() =>
      expect(request).toHaveBeenLastCalledWith(expect.objectContaining({ sortOrder: 'descend' }))
    )
  })
  it('requests remote data for initial state, filters, sorting, pagination and reload', async () => {
    const request = createRequest()
    const user = userEvent.setup()
    renderWithQueryClient(<TestTable request={request} />)

    await waitFor(() => expect(screen.getByText('alpha')).toBeInTheDocument())
    expect(screen.getByText('自定义筛选')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: '搜索名称' })).toHaveAttribute('name', 'keyword')
    expect(screen.getByRole('combobox', { name: '状态' })).toHaveAttribute('id', 'filter-status')

    await user.type(screen.getByPlaceholderText('搜索名称'), 'beta')
    await waitFor(() => {
      expect(request).toHaveBeenLastCalledWith(
        expect.objectContaining({ keyword: 'beta', page: 1 })
      )
    })

    await user.click(screen.getByRole('columnheader', { name: '名称' }))
    await waitFor(() => {
      expect(request).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: 'name', sortOrder: 'ascend' })
      )
    })

    await user.click(screen.getByTitle('2'))
    await waitFor(() => {
      expect(request).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }))
    })

    const callsBeforeReload = request.mock.calls.length
    await user.click(screen.getByRole('button', { name: '刷新列表' }))
    await waitFor(() => expect(request.mock.calls.length).toBeGreaterThan(callsBeforeReload))
  })

  it('renders selection actions and clears controlled selection', async () => {
    const request = createRequest()
    const user = userEvent.setup()
    renderWithQueryClient(<SelectionTable request={request} />)

    await waitFor(() => expect(screen.getByText('alpha')).toBeInTheDocument())
    await user.click(screen.getAllByRole('checkbox')[1])

    expect(screen.getByLabelText('已选择 1 条')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '批量处理' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '清空选择' }))
    expect(screen.getByText('选择记录后可批量操作')).toBeInTheDocument()
  })

  it('uses the shared small density for the table and pagination by default', async () => {
    const request = createRequest()
    const { container } = renderWithQueryClient(
      <div style={{ height: 400 }}>
        <BaseTable<RecordItem, Filters, SortField>
          columns={[{ dataIndex: 'name', title: '名称' }]}
          queryKey={['base-table-size']}
          request={request}
          rowKey="id"
        />
      </div>
    )

    await waitFor(() => expect(screen.getByText('alpha')).toBeInTheDocument())
    expect(screen.getByText('共 40 条')).toBeInTheDocument()
    expect(container.querySelector('.ant-table-small')).toBeInTheDocument()
    expect(container.querySelector('.ant-pagination-mini')).toBeInTheDocument()
  })

  it('requests fresh data when a table instance is remounted', async () => {
    let resolveSecondRequest: (response: PageResponse<RecordItem>) => void
    const secondRequest = new Promise<PageResponse<RecordItem>>((resolve) => {
      resolveSecondRequest = resolve
    })
    const request = vi
      .fn<BaseTableRequest<RecordItem, Filters, SortField>>()
      .mockResolvedValueOnce(createResponse(records, 1, 20))
      .mockImplementationOnce(() => secondRequest)
    const queryClient = createTestQueryClient()
    const firstRender = renderWithQueryClient(<TestTable request={request} />, queryClient)

    await screen.findByText('alpha')
    firstRender.unmount()

    renderWithQueryClient(<TestTable request={request} />, queryClient)
    await waitFor(() => expect(request).toHaveBeenCalledTimes(2))
    expect(screen.queryByText('alpha')).not.toBeInTheDocument()

    resolveSecondRequest!(
      createResponse([{ id: 'record-3', name: 'fresh', status: 'ACTIVE' }], 1, 20)
    )
    expect(await screen.findByText('fresh')).toBeInTheDocument()
  })

  it('distinguishes request failure and retries the request', async () => {
    const request = vi
      .fn<BaseTableRequest<RecordItem, Filters, SortField>>()
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValue(createResponse(records, 1, 20))
    const user = userEvent.setup()
    renderWithQueryClient(
      <div style={{ height: 400 }}>
        <BaseTable<RecordItem, Filters, SortField>
          columns={[{ dataIndex: 'name', title: '名称' }]}
          errorDescription="请求失败"
          queryKey={['base-table-error']}
          request={request}
          rowKey="id"
        />
      </div>
    )

    await waitFor(() => expect(screen.getByText('请求失败')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: '重新加载' }))
    await waitFor(() => expect(screen.getByText('alpha')).toBeInTheDocument())
  })

  it('replaces table chrome and pagination with a standalone empty state by default', async () => {
    const request = vi
      .fn<BaseTableRequest<RecordItem, Filters, SortField>>()
      .mockResolvedValue(createResponse([], 1, 20, 0))
    const { container } = renderWithQueryClient(
      <div style={{ height: 400 }}>
        <BaseTable<RecordItem, Filters, SortField>
          columns={[{ dataIndex: 'name', title: '名称' }]}
          emptyDescription="暂无执行记录"
          queryKey={['base-table-standalone-empty']}
          request={request}
          rowKey="id"
        />
      </div>
    )

    await waitFor(() =>
      expect(screen.queryByRole('columnheader', { name: '名称' })).not.toBeInTheDocument()
    )
    expect(screen.getByText('暂无执行记录')).toBeInTheDocument()
    expect(screen.getByText('当前列表还没有可展示的内容')).toBeInTheDocument()
    expect(screen.queryByText('共 0 条')).not.toBeInTheDocument()
    expect(container.querySelector('.ant-table')).not.toBeInTheDocument()
  })

  it('clears active filters from the filtered empty state', async () => {
    const request = createRequest()
    const user = userEvent.setup()
    const { container } = renderWithQueryClient(<TestTable request={request} />)

    await screen.findByText('alpha')
    await user.type(screen.getByRole('textbox', { name: '搜索名称' }), 'missing')
    await screen.findByText('暂无符合条件的数据')

    expect(screen.getByText('没有找到与当前筛选条件匹配的记录')).toBeInTheDocument()
    expect(container.querySelector('.ant-table')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '清空筛选' }))
    await screen.findByText('alpha')
    expect(screen.getByRole('textbox', { name: '搜索名称' })).toHaveValue('')
  })

  it('can preserve table chrome for an explicit table empty state', async () => {
    const request = vi
      .fn<BaseTableRequest<RecordItem, Filters, SortField>>()
      .mockResolvedValue(createResponse([], 1, 20, 0))
    renderWithQueryClient(
      <div style={{ height: 400 }}>
        <BaseTable<RecordItem, Filters, SortField>
          columns={[{ dataIndex: 'name', title: '名称' }]}
          emptyPresentation="table"
          queryKey={['base-table-table-empty']}
          request={request}
          rowKey="id"
        />
      </div>
    )

    expect(await screen.findByRole('columnheader', { name: '名称' })).toBeInTheDocument()
    expect(screen.getByText('暂无数据')).toBeInTheDocument()
  })
})

describe('StrictMode filter notifications', () => {
  it('notifies once per edit and once on clear with the final consecutive conditions', async () => {
    const { StrictMode } = await import('react')
    const onChange = vi.fn()
    const request = vi.fn(async (query) => createResponse([], query.page, query.pageSize))
    renderWithQueryClient(
      <StrictMode>
        <BaseTable<RecordItem, Filters>
          autoHeight
          columns={[]}
          queryKey={['strict-filters']}
          request={request}
          rowKey="id"
          toolbar={{
            filters: {
              onChange,
              fields: [{ name: 'keyword', type: 'input', placeholder: '关键词' }]
            }
          }}
        />
      </StrictMode>
    )
    const input = screen.getByPlaceholderText('关键词')
    fireEvent.change(input, { target: { value: 'a' } })
    expect(onChange).toHaveBeenCalledTimes(1)
    fireEvent.change(input, { target: { value: 'ab' } })
    expect(onChange).toHaveBeenCalledTimes(2)
    expect(onChange).toHaveBeenLastCalledWith({ keyword: 'ab' })
    await waitFor(() => expect(screen.getByText('清空筛选')).toBeInTheDocument())
    fireEvent.click(screen.getByText('清空筛选'))
    expect(onChange).toHaveBeenCalledTimes(3)
    expect(onChange).toHaveBeenLastCalledWith({})
  })
})
