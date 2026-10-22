import { useState } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { useTableViewState } from './TableViewStateContext'
import TableViewStateProvider from './TableViewStateProvider'

const initial = { keyword: '', status: '', page: 1, pageSize: 10, sortOrder: '' }

function Controls({ listId }: { listId: string }) {
  const [state, update] = useTableViewState(['list', { id: listId }], initial)
  return (
    <>
      <output aria-label="查询状态">{JSON.stringify(state)}</output>
      <button
        onClick={() =>
          update(() => ({
            keyword: 'src/',
            status: 'DETECTED',
            page: 3,
            pageSize: 20,
            sortOrder: 'descend'
          }))
        }
      >
        修改查询
      </button>
    </>
  )
}

function Harness({
  scope = 'project-1:kb',
  active = true,
  listId = 'scan-1'
}: {
  scope?: string
  active?: boolean
  listId?: string
}) {
  const [detail, setDetail] = useState(false)
  return (
    <TableViewStateProvider key={scope} active={active}>
      <button onClick={() => setDetail((value) => !value)}>切换详情</button>
      {detail ? <p>详情</p> : <Controls listId={listId} />}
    </TableViewStateProvider>
  )
}

describe('table view state scope', () => {
  it('retains all query controls across list unmount and remount', () => {
    render(<Harness />)
    fireEvent.click(screen.getByText('修改查询'))
    const saved = screen.getByLabelText('查询状态').textContent
    fireEvent.click(screen.getByText('切换详情'))
    expect(screen.queryByLabelText('查询状态')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('切换详情'))
    expect(screen.getByLabelText('查询状态').textContent).toBe(saved)
  })

  it('isolates datasets and restores each dataset independently, including a mounted key change', () => {
    const { rerender } = render(<Harness />)
    fireEvent.click(screen.getByText('修改查询'))
    const saved = screen.getByLabelText('查询状态').textContent
    rerender(<Harness listId="scan-2" />)
    expect(screen.getByLabelText('查询状态')).toHaveTextContent(JSON.stringify(initial))
    rerender(<Harness listId="scan-1" />)
    expect(screen.getByLabelText('查询状态').textContent).toBe(saved)
  })

  it('resets on closing the stage and isolates projects and stages', () => {
    const { rerender } = render(<Harness />)
    fireEvent.click(screen.getByText('修改查询'))
    rerender(<Harness active={false} />)
    rerender(<Harness />)
    expect(screen.getByLabelText('查询状态')).toHaveTextContent(JSON.stringify(initial))
    fireEvent.click(screen.getByText('修改查询'))
    rerender(<Harness scope="project-2:kb" />)
    expect(screen.getByLabelText('查询状态')).toHaveTextContent(JSON.stringify(initial))
    fireEvent.click(screen.getByText('修改查询'))
    rerender(<Harness scope="project-2:build" />)
    expect(screen.getByLabelText('查询状态')).toHaveTextContent(JSON.stringify(initial))
  })
})
