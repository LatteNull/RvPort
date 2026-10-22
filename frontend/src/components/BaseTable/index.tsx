import { forwardRef, Fragment, useEffect, useImperativeHandle, useRef } from 'react'
import type { TableProps } from 'antd'
import { Button, Pagination, Table } from 'antd'
import type { ForwardedRef, ReactElement, RefAttributes } from 'react'

import ContentState from '@/components/ContentState'

import FilterForm from './FilterForm'
import { useBaseTableQuery } from './hooks/useBaseTableQuery'
import { useTableViewportHeight } from './hooks/useTableViewportHeight'
import { sortColumns } from './sortColumns'
import type { BaseTableHandle, BaseTableProps, BaseTableSelectionContext } from './types'

import styles from './index.module.scss'

const tableStyles = {
  root: {},

  header: {
    cell: {
      fontWeight: 500,
      color: 'var(--ant-color-text-secondary)',
      padding: '8px 16px'
    }
  },
  body: {
    cell: {
      color: 'var(--ant-color-text)',
      padding: '8px 16px'
    }
  }
}

function showPaginationTotal(total: number) {
  return `共 ${total} 条`
}

function BaseTableInner<TRecord, TFilters extends object, TSortField extends string>(
  {
    autoHeight = false,
    className,
    emptyAction,
    emptyDescription = '暂无数据',
    emptyPresentation = 'standalone',
    errorDescription = '列表加载失败',
    filteredEmptyDescription = '暂无符合条件的数据',
    locale,
    onChange,
    pagination = {},
    queryKey,
    request,
    rowSelection,
    selection,
    size = 'small',
    scroll,
    stickyFooter = false,
    toolbar,
    ...tableProps
  }: BaseTableProps<TRecord, TFilters, TSortField>,
  ref: ForwardedRef<BaseTableHandle>
) {
  const rootRef = useRef<HTMLDivElement>(null)
  const toolbarRef = useRef<HTMLDivElement>(null)
  const footerRef = useRef<HTMLDivElement>(null)
  const viewportRef = useRef<HTMLDivElement>(null)
  const paginationConfig = pagination === false ? undefined : pagination
  const {
    displayedData,
    filters,
    query,
    requestParams,
    resetFilters,
    searchResetVersion,
    updateFilters,
    updateFromTable,
    updatePagination
  } = useBaseTableQuery<TRecord, TFilters, TSortField>({
    initialFilters: toolbar?.filters?.initialValues,
    initialPageSize: paginationConfig?.initialPageSize ?? 20,
    queryKey,
    request
  })
  const viewportHeight = useTableViewportHeight({
    enabled: !autoHeight,
    footerRef,
    rootRef,
    toolbarRef,
    viewportRef
  })
  const selectedCount = rowSelection?.selectedRowKeys?.length ?? 0
  const hasActiveFilters = Object.values(filters).some(
    (value) =>
      value !== undefined &&
      value !== null &&
      value !== '' &&
      (!Array.isArray(value) || value.length > 0)
  )

  useImperativeHandle(
    ref,
    () => ({
      reload: () => query.refetch()
    }),
    [query]
  )

  const filtersRef = useRef(filters)
  useEffect(() => {
    filtersRef.current = filters
  }, [filters])
  const handleFilterChange = (name: Extract<keyof TFilters, string>, value: unknown) => {
    const nextFilters = { ...filtersRef.current, [name]: value } as TFilters
    filtersRef.current = nextFilters
    updateFilters(() => nextFilters)
    toolbar?.filters?.onChange?.(nextFilters)
  }
  const handleClearFilters = () => {
    const nextFilters = {} as TFilters
    filtersRef.current = nextFilters
    resetFilters(nextFilters)
    toolbar?.filters?.onChange?.(nextFilters)
  }
  const handleTableChange: NonNullable<TableProps<TRecord>['onChange']> = (
    nextPagination,
    nextFilters,
    sorter,
    extra
  ) => {
    updateFromTable(nextPagination, sorter)
    onChange?.(nextPagination, nextFilters, sorter, extra)
  }
  const selectionContext: BaseTableSelectionContext = {
    clear: () => rowSelection?.onChange?.([], [], { type: 'none' }),
    selectedCount
  }
  const selectionContent = typeof selection === 'function' ? selection(selectionContext) : selection
  const hasFooter = pagination !== false || (rowSelection && selection)
  const tableScroll = autoHeight ? scroll : { ...scroll, y: viewportHeight ?? scroll?.y }
  const emptyText =
    query.isError && !displayedData ? (
      <ContentState compact kind="error" description={errorDescription}>
        <Button type="primary" onClick={() => void query.refetch()}>
          重试
        </Button>
      </ContentState>
    ) : (
      <ContentState
        compact
        kind={hasActiveFilters ? 'filtered' : 'empty'}
        description={hasActiveFilters ? filteredEmptyDescription : emptyDescription}
      />
    )
  const showStandaloneError = emptyPresentation === 'standalone' && query.isError && !displayedData
  const showStandaloneEmpty =
    emptyPresentation === 'standalone' &&
    !query.isError &&
    !query.isLoading &&
    !query.isFetching &&
    displayedData?.items.length === 0
  const showStandaloneState = showStandaloneError || showStandaloneEmpty

  return (
    <div
      className={[styles.baseTable, stickyFooter && styles.stickyFooter, className]
        .filter(Boolean)
        .join(' ')}
      ref={rootRef}
    >
      {toolbar && (
        <div className={styles.toolbar} ref={toolbarRef}>
          {toolbar.filters && (
            <div className={styles.filters}>
              <FilterForm
                filters={toolbar.filters}
                queryKey={queryKey}
                searchResetVersion={searchResetVersion}
                values={filters}
                onFieldChange={handleFilterChange}
              />
            </div>
          )}
          {toolbar.actions && <div className={styles.actions}>{toolbar.actions}</div>}
        </div>
      )}
      <div
        className={[styles.viewport, showStandaloneState && styles.emptyViewport]
          .filter(Boolean)
          .join(' ')}
        ref={viewportRef}
      >
        {showStandaloneState ? (
          <ContentState
            className={styles.standaloneEmpty}
            kind={showStandaloneError ? 'error' : hasActiveFilters ? 'filtered' : 'empty'}
            description={
              showStandaloneError
                ? errorDescription
                : hasActiveFilters
                  ? filteredEmptyDescription
                  : emptyDescription
            }
            details={
              showStandaloneError
                ? '请检查网络连接后重新加载'
                : hasActiveFilters
                  ? '没有找到与当前筛选条件匹配的记录'
                  : '当前列表还没有可展示的内容'
            }
          >
            {showStandaloneError ? (
              <Button type="primary" onClick={() => void query.refetch()}>
                重新加载
              </Button>
            ) : hasActiveFilters ? (
              <Button onClick={handleClearFilters}>清空筛选</Button>
            ) : (
              emptyAction
            )}
          </ContentState>
        ) : (
          <Table<TRecord>
            {...tableProps}
            columns={sortColumns(tableProps.columns, requestParams.sortBy, requestParams.sortOrder)}
            styles={tableStyles}
            dataSource={displayedData?.items ?? []}
            loading={query.isLoading || query.isFetching}
            locale={{ ...locale, emptyText }}
            onChange={handleTableChange}
            pagination={false}
            rowSelection={rowSelection}
            scroll={tableScroll}
            size={size}
          />
        )}
      </div>
      {hasFooter && !showStandaloneState && (
        <div className={styles.footer} ref={footerRef}>
          <div className={styles.selection}>
            {rowSelection && selection && (
              <div className={styles.selectionSummary}>
                <span
                  aria-label={selectedCount ? `已选择 ${selectedCount} 条` : undefined}
                  className={selectedCount ? styles.selectionCount : styles.selectionHint}
                >
                  {selectedCount ? (
                    <Fragment>
                      已选择 <strong>{selectedCount}</strong> 条
                    </Fragment>
                  ) : (
                    '选择记录后可批量操作'
                  )}
                </span>
                {selectedCount > 0 && (
                  <Button size="small" type="link" onClick={selectionContext.clear}>
                    清空选择
                  </Button>
                )}
                {selectionContent}
              </div>
            )}
          </div>
          {pagination !== false && (
            <div className={styles.pagination}>
              <Pagination
                {...paginationConfig}
                disabled={query.isFetching}
                current={requestParams.page}
                pageSize={requestParams.pageSize}
                size={size === 'small' ? 'small' : undefined}
                showSizeChanger={paginationConfig?.showSizeChanger ?? true}
                showTotal={paginationConfig?.showTotal ?? showPaginationTotal}
                total={displayedData?.total ?? 0}
                onChange={updatePagination}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

type BaseTableComponent = <TRecord, TFilters extends object, TSortField extends string = string>(
  props: BaseTableProps<TRecord, TFilters, TSortField> & RefAttributes<BaseTableHandle>
) => ReactElement | null

const BaseTable = forwardRef(BaseTableInner) as BaseTableComponent

export default BaseTable
export type {
  BaseTableFilterField,
  BaseTableFilters,
  BaseTableHandle,
  BaseTablePagination,
  BaseTableProps,
  BaseTableQuery,
  BaseTableRequest,
  BaseTableSelection,
  BaseTableSize,
  BaseTableToolbar
} from './types'
