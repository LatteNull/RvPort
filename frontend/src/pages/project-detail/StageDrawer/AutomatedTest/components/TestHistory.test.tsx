import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import TableViewStateProvider from '@/components/BaseTable/TableViewStateProvider'

import TestHistory from './TestHistory'

const rows = Array.from({ length: 25 }, (_, index) => ({ id: `batch-${index + 1}` }))

function Harness() {
  const [detail, setDetail] = useState(false)
  return (
    <TableViewStateProvider>
      <button onClick={() => setDetail((value) => !value)}>切换详情</button>
      {detail ? (
        <p>批次详情</p>
      ) : (
        <TestHistory
          columns={[{ title: '批次', dataIndex: 'id' }]}
          data={rows}
          projectId="project-1"
        />
      )}
    </TableViewStateProvider>
  )
}

describe('automated test history', () => {
  it('restores the client-side page when returning from a batch detail', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByTitle('2'))
    expect(screen.getByText('batch-11')).toBeVisible()
    await user.click(screen.getByText('切换详情'))
    await user.click(screen.getByText('切换详情'))
    expect(screen.getByText('batch-11')).toBeVisible()
    expect(screen.queryByText('batch-1')).not.toBeInTheDocument()
    expect(screen.getByTitle('2')).toHaveClass('ant-pagination-item-active')
  })
})
