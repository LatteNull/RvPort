import type { ColumnsType } from 'antd/es/table'

import type { BaseTableSortOrder } from './types'

export function sortColumns<T>(
  columns: ColumnsType<T> | undefined,
  sortBy?: string,
  sortOrder?: BaseTableSortOrder
): ColumnsType<T> | undefined {
  return columns?.map((column) => {
    if ('children' in column) {
      return { ...column, children: sortColumns(column.children, sortBy, sortOrder)! }
    }
    if (!column.sorter) return column
    return { ...column, sortOrder: column.dataIndex === sortBy ? (sortOrder ?? null) : null }
  })
}
