import { Button, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { getSpecializedFindings } from '@/api/project/specialized-analysis'
import BaseTable from '@/components/BaseTable'
import type {
  SpecializedAnalysis,
  SpecializedAnalysisStageId,
  SpecializedFinding
} from '@/types/project/specialized-analysis'

import { projectQueryKeys } from '../../../queryKeys'
import { presentFinding, severityColors, severityLabels } from '../presentation'

export default function FindingList({
  run,
  projectId,
  stageId,
  search,
  severity,
  onFiltersChange,
  onSelect
}: {
  run: SpecializedAnalysis
  projectId: string
  stageId: SpecializedAnalysisStageId
  search: string
  severity: string
  onFiltersChange: (search: string, severity: string) => void
  onSelect: (id: string) => void
}) {
  const columns: ColumnsType<SpecializedFinding> = [
    {
      title: '风险',
      width: 260,
      ellipsis: true,
      render: (_, raw) => (
        <Button type="link" onClick={() => onSelect(raw.id)}>
          {presentFinding(raw).title}
        </Button>
      )
    },
    {
      title: '等级',
      width: 100,
      render: (_, raw) => {
        const finding = presentFinding(raw)
        return (
          <Tag color={severityColors[finding.severity]}>{severityLabels[finding.severity]}</Tag>
        )
      }
    },
    {
      title: '文件',
      dataIndex: 'filePath',
      width: 250,
      ellipsis: true,
      render: (value) => value || '--'
    },
    { title: '行号', dataIndex: 'startLine', width: 80, render: (value) => value ?? '--' },
    { title: '说明', width: 300, ellipsis: true, render: (_, raw) => presentFinding(raw).impact },
    { title: '置信度', width: 120, render: (_, raw) => presentFinding(raw).confidence },
    {
      title: '操作',
      fixed: 'right',
      width: 90,
      render: (_, raw) => (
        <Button type="link" onClick={() => onSelect(raw.id)}>
          查看
        </Button>
      )
    }
  ]
  return (
    <BaseTable<SpecializedFinding, { keyword?: string; severity?: string }>
      autoHeight
      columns={columns}
      emptyPresentation="table"
      emptyDescription={
        run.status === 'PARTIAL'
          ? '当前已分析范围内暂无风险结果，部分范围尚未完成'
          : '本次分析范围内未发现支持的风险'
      }
      filteredEmptyDescription="没有符合筛选条件的风险"
      errorDescription="分析结果加载失败"
      pagination={{ initialPageSize: 20 }}
      queryKey={projectQueryKeys.specializedFindings(projectId, stageId, run.id)}
      request={(query) =>
        getSpecializedFindings(projectId, stageId, run.id, {
          page: query.page,
          pageSize: query.pageSize,
          keyword: query.keyword?.trim() || undefined,
          severity: query.severity
        })
      }
      rowKey="id"
      size="small"
      scroll={{ x: 1200 }}
      tableLayout="fixed"
      toolbar={{
        filters: {
          initialValues: {
            keyword: search || undefined,
            severity: severity === 'all' ? undefined : severity.toUpperCase()
          },
          onChange: (values) =>
            onFiltersChange(values.keyword ?? '', values.severity?.toLowerCase() ?? 'all'),
          fields: [
            {
              name: 'keyword',
              type: 'search',
              placeholder: '搜索风险、文件或规则',
              ariaLabel: '搜索风险'
            },
            {
              name: 'severity',
              type: 'select',
              placeholder: '风险等级',
              ariaLabel: '风险等级',
              options: Object.entries(severityLabels)
                .filter(([key]) => key !== 'unknown')
                .map(([value, label]) => ({ value: value.toUpperCase(), label }))
            }
          ]
        }
      }}
    />
  )
}
