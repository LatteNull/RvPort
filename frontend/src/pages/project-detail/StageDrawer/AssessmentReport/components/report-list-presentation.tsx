import { Button, Popconfirm, Select, Tooltip } from 'antd'
import type { ReactElement } from 'react'

import { reportFindingTypeText } from '../reportPresentation'
import type { OrganizedReportProps } from './types'

import styles from '../index.module.scss'

export function ReportActions({
  canGenerate,
  isCreating,
  onCreate,
  onDownload
}: Pick<OrganizedReportProps, 'canGenerate' | 'isCreating' | 'onCreate' | 'onDownload'>) {
  return (
    <div className={styles.reportActions}>
      {canGenerate ? (
        <Popconfirm
          cancelText="取消"
          description="将基于当前已纳入报告的问题生成一份新的评估报告。"
          okButtonProps={{ loading: isCreating }}
          okText="确认重新生成"
          title="确认重新生成评估报告？"
          onConfirm={onCreate}
        >
          <Button disabled={!canGenerate} loading={isCreating}>
            重新生成报告
          </Button>
        </Popconfirm>
      ) : null}
      <Button onClick={() => onDownload('HTML')}>下载 HTML</Button>
      <Button onClick={() => onDownload('JSON')}>下载 JSON</Button>
    </div>
  )
}

export function SummaryFact({
  label,
  primary = false,
  value
}: {
  label: string
  primary?: boolean
  value: string
}) {
  return (
    <span className={primary ? styles.summaryFactPrimary : undefined}>
      <small>{label}</small>
      <strong>{value}</strong>
    </span>
  )
}

export function TypeCounts({ counts, limit }: { counts: Record<string, number>; limit?: number }) {
  const allEntries = Object.entries(counts).sort(([, left], [, right]) => right - left)
  const entries = limit ? allEntries.slice(0, limit) : allEntries
  if (!entries.length) return <span className={styles.emptyValue}>暂无类型统计</span>
  return (
    <div className={styles.typeCounts}>
      {entries.map(([type, count]) => (
        <span key={type}>
          {reportFindingTypeText(type)} <strong>{count}</strong>
        </span>
      ))}
      {limit && allEntries.length > limit ? <span>另有 {allEntries.length - limit} 种</span> : null}
    </div>
  )
}

export function FindingTypeFilter({
  ariaLabel,
  findingCount,
  options,
  value,
  onChange
}: {
  ariaLabel: string
  findingCount: number
  options: Array<{ count: number; type: string }>
  value?: string
  onChange: (value?: string) => void
}) {
  return (
    <div className={styles.findingTypeSelect}>
      <span>问题类型</span>
      <Select<string>
        aria-label={ariaLabel}
        optionFilterProp="label"
        options={[
          { label: `全部问题（${findingCount}）`, value: 'ALL' },
          ...options.map(({ count, type }) => ({
            label: `${reportFindingTypeText(type)}（${count}）`,
            value: type
          }))
        ]}
        showSearch
        value={value ?? 'ALL'}
        onChange={(nextValue) => onChange(nextValue === 'ALL' ? undefined : nextValue)}
      />
    </div>
  )
}

export function FindingTooltip({
  activeId,
  children,
  disabled = false,
  id,
  title,
  onOpenChange
}: {
  activeId?: string
  children: ReactElement
  disabled?: boolean
  id: string
  title: string
  onOpenChange: (id: string, open: boolean) => void
}) {
  return (
    <Tooltip
      destroyOnHidden
      getPopupContainer={(triggerNode) =>
        (triggerNode.closest('[data-finding-pane]') as HTMLElement | null) ?? triggerNode
      }
      open={!disabled && activeId === id}
      title={title}
      onOpenChange={(open) => {
        if (!disabled) onOpenChange(id, open)
      }}
    >
      {children}
    </Tooltip>
  )
}
