import { useMemo, useState } from 'react'
import { hashKey, useQuery } from '@tanstack/react-query'
import type { SorterResult, TablePaginationConfig } from 'antd/es/table/interface'

import { useTableViewState } from '../TableViewStateContext'
import type { BaseTableQuery, BaseTableRequest, BaseTableSortOrder } from '../types'
import { usePageBounds } from './usePageBounds'

interface UseBaseTableQueryOptions<TRecord, TFilters extends object, TSortField extends string> {
  initialFilters?: TFilters
  initialPageSize: number
  queryKey: readonly unknown[]
  request: BaseTableRequest<TRecord, TFilters, TSortField>
}

export function useBaseTableQuery<TRecord, TFilters extends object, TSortField extends string>({
  initialFilters,
  initialPageSize,
  queryKey,
  request
}: UseBaseTableQueryOptions<TRecord, TFilters, TSortField>) {
  const [tableInstanceKey] = useState(
    () => `base-table-${Date.now()}-${Math.random().toString(36).slice(2)}`
  )
  const [{ filters, page, pageSize, sortBy, sortOrder, searchResetVersion = 0 }, updateState] =
    useTableViewState<{
      filters: TFilters
      page: number
      pageSize: number
      sortBy?: TSortField
      sortOrder?: BaseTableSortOrder
      searchResetVersion: number
    }>(queryKey, {
      filters: initialFilters ?? ({} as TFilters),
      page: 1,
      pageSize: initialPageSize,
      searchResetVersion: 0
    })

  const requestParams = useMemo<BaseTableQuery<TFilters, TSortField>>(
    () => ({ ...filters, page, pageSize, sortBy, sortOrder }),
    [filters, page, pageSize, sortBy, sortOrder]
  )
  const query = useQuery({
    queryKey: [...queryKey, tableInstanceKey, requestParams],
    queryFn: () => request(requestParams),
    gcTime: 0,
    placeholderData: (previousData, previousQuery) =>
      hashKey(previousQuery?.queryKey.slice(0, -2) ?? []) === hashKey(queryKey)
        ? previousData
        : undefined,
    refetchOnMount: 'always',
    refetchOnReconnect: false,
    refetchOnWindowFocus: false,
    staleTime: 0
  })

  usePageBounds({
    page,
    pageSize,
    total: query.data?.total,
    ready: query.isSuccess && !query.isFetching && !query.isPlaceholderData,
    onCorrectPage: (lastPage) =>
      updateState((current) =>
        current.page === page &&
        current.pageSize === pageSize &&
        current.filters === filters &&
        current.sortBy === sortBy &&
        current.sortOrder === sortOrder
          ? { ...current, page: lastPage }
          : current
      )
  })

  const updateFilters = (updater: (current: TFilters) => TFilters) => {
    updateState((current) => ({ ...current, filters: updater(current.filters), page: 1 }))
  }
  const resetFilters = (filters: TFilters) => {
    updateState((current) => ({
      ...current,
      filters,
      page: 1,
      searchResetVersion: (current.searchResetVersion ?? 0) + 1
    }))
  }
  const updatePagination = (nextPage: number, nextPageSize: number) => {
    updateState((current) => ({ ...current, page: nextPage, pageSize: nextPageSize }))
  }
  const updateFromTable = (
    pagination: TablePaginationConfig,
    sorter: SorterResult<TRecord> | SorterResult<TRecord>[]
  ) => {
    const activeSorter = Array.isArray(sorter) ? sorter[0] : sorter
    const field = activeSorter?.field
    const nextSortBy = typeof field === 'string' ? (field as TSortField) : undefined
    const nextSortOrder =
      activeSorter?.order === 'ascend' || activeSorter?.order === 'descend'
        ? activeSorter.order
        : undefined

    updateState((current) => ({
      ...current,
      page: pagination.current ?? 1,
      pageSize: pagination.pageSize ?? current.pageSize,
      sortBy: nextSortBy,
      sortOrder: nextSortOrder
    }))
  }

  return {
    displayedData: query.data,
    filters,
    query,
    requestParams,
    resetFilters,
    searchResetVersion,
    updateFilters,
    updateFromTable,
    updatePagination
  }
}
