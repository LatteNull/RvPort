import { Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { useTableViewState } from '@/components/BaseTable/TableViewStateContext'

export default function TestHistory<T extends { id: string }>({
  columns,
  data,
  projectId
}: {
  columns: ColumnsType<T>
  data: T[]
  projectId?: string
}) {
  const [pagination, updatePagination] = useTableViewState(
    ['automated-test-batch-history', projectId],
    { current: 1, pageSize: 10 }
  )
  return (
    <Table
      columns={columns}
      dataSource={data}
      locale={{ emptyText: '暂无自动化测试记录' }}
      pagination={{
        ...pagination,
        onChange: (current, pageSize) => updatePagination(() => ({ current, pageSize }))
      }}
      rowKey="id"
      size="small"
    />
  )
}
