import type { QueryKey } from '@tanstack/react-query'
import type { PaginationProps, TableProps } from 'antd'
import type { ReactNode } from 'react'

import type { PageResponse } from '@/types'

export type BaseTableSortOrder = 'ascend' | 'descend'
export type BaseTableSize = NonNullable<TableProps<unknown>['size']>

export type BaseTableQuery<
  TFilters extends object,
  TSortField extends string = string
> = TFilters & {
  page: number
  pageSize: number
  sortBy?: TSortField
  sortOrder?: BaseTableSortOrder
}

export type BaseTableRequest<
  TRecord,
  TFilters extends object,
  TSortField extends string = string
> = (query: BaseTableQuery<TFilters, TSortField>) => Promise<PageResponse<TRecord>>

export type BaseTableFilterType = 'search' | 'input' | 'select' | 'custom'

export interface BaseTableFilterRenderContext<TFilters extends object> {
  filters: TFilters
  onChange: (value: unknown) => void
  value: unknown
}

export interface BaseTableFilterField<TFilters extends object> {
  ariaLabel?: string
  controlProps?: Record<string, unknown>
  key?: string
  name: Extract<keyof TFilters, string>
  normalize?: (value: unknown) => unknown
  options?: Array<{ label: ReactNode; value: string | number }>
  placeholder?: string
  render?: (context: BaseTableFilterRenderContext<TFilters>) => ReactNode
  type: BaseTableFilterType
}

export interface BaseTableFilters<TFilters extends object> {
  fields: BaseTableFilterField<TFilters>[]
  initialValues?: TFilters
  onChange?: (filters: TFilters) => void
}

export interface BaseTableToolbar<TFilters extends object> {
  actions?: ReactNode
  filters?: BaseTableFilters<TFilters>
}

export interface BaseTableSelectionContext {
  clear: () => void
  selectedCount: number
}

export type BaseTableSelection = ReactNode | ((context: BaseTableSelectionContext) => ReactNode)

export type BaseTablePagination = Omit<
  PaginationProps,
  'current' | 'defaultCurrent' | 'defaultPageSize' | 'onChange' | 'pageSize' | 'total'
> & {
  initialPageSize?: number
}

export interface BaseTableHandle {
  reload: () => Promise<unknown>
}

export type BaseTableProps<
  TRecord,
  TFilters extends object,
  TSortField extends string = string
> = Omit<TableProps<TRecord>, 'dataSource' | 'loading' | 'onChange' | 'pagination' | 'size'> & {
  autoHeight?: boolean
  emptyAction?: ReactNode
  emptyDescription?: ReactNode
  emptyPresentation?: 'table' | 'standalone'
  errorDescription?: ReactNode
  filteredEmptyDescription?: ReactNode
  onChange?: TableProps<TRecord>['onChange']
  pagination?: BaseTablePagination | false
  queryKey: QueryKey
  request: BaseTableRequest<TRecord, TFilters, TSortField>
  selection?: BaseTableSelection
  size?: BaseTableSize
  stickyFooter?: boolean
  toolbar?: BaseTableToolbar<TFilters>
}
