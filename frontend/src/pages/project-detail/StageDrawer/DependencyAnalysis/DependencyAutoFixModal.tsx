import { useMemo, useState } from 'react'
import { ArrowRightOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Checkbox, Flex, Table, Tag, Tooltip } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { Key } from 'react'

import {
  createProjectDependencyAutoFix,
  getProjectDependencyAutoFixCandidates
} from '@/api/project/dependency-analysis'
import { readAllPages } from '@/api/readAllPages'
import BaseModal from '@/components/BaseModal'
import ContentState from '@/components/ContentState'
import { useSessionMutation } from '@/hooks/useSessionMutation'
import type { ProjectDependencyAutoFixCandidate } from '@/types/project/dependency-analysis'
import { feedback } from '@/utils/feedback'

import { projectQueryKeys } from '../../queryKeys'
import StageStateNotice from '../components/StageStateNotice'

import styles from './index.module.scss'

interface DependencyAutoFixModalProps {
  analysisId: string
  open: boolean
  onClose: () => void
}

function riskTag(risk: string) {
  const config = {
    CRITICAL: { color: 'error', label: '严重' },
    HIGH: { color: 'volcano', label: '高' },
    MEDIUM: { color: 'warning', label: '中' },
    LOW: { color: 'success', label: '低' }
  }[risk]
  return config ? <Tag color={config.color}>{config.label}</Tag> : <Tag>{risk}</Tag>
}

function installTarget(candidate: ProjectDependencyAutoFixCandidate) {
  return candidate.installVersionConstraint
    ? `${candidate.installPackageName} ${candidate.installVersionConstraint}`
    : candidate.installPackageName
}

export default function DependencyAutoFixModal({
  analysisId,
  open,
  onClose
}: DependencyAutoFixModalProps) {
  const [selectedKeys, setSelectedKeys] = useState<Key[] | null>(null)
  const [rerunAnalysis, setRerunAnalysis] = useState(true)
  const candidatesQuery = useQuery({
    queryKey: projectQueryKeys.dependencyAutoFixCandidates(analysisId),
    queryFn: ({ signal }) =>
      readAllPages(
        (page, pageSize) =>
          getProjectDependencyAutoFixCandidates(analysisId, {
            page,
            pageSize,
            selectable: true,
            sortBy: 'defaultSelected',
            sortDirection: 'desc'
          }),
        { signal }
      ),
    enabled: open
  })
  const candidates = candidatesQuery.data?.items
  const effectiveSelectedKeys = useMemo(
    () =>
      selectedKeys ??
      (candidates ?? [])
        .filter((candidate) => candidate.defaultSelected)
        .map((item) => item.resultItemId),
    [candidates, selectedKeys]
  )
  const createMutation = useSessionMutation({
    sessionKey: `auto-fix:${analysisId}`,
    active: open,
    mutationFn: () =>
      createProjectDependencyAutoFix(analysisId, {
        rerunDependencyAnalysis: rerunAnalysis,
        resultItemIds: effectiveSelectedKeys.map(String)
      }),
    onSuccess: (result) => {
      feedback.success(`已创建 ${result.selectedCount} 项依赖自动修复任务`)
      resetAndClose()
    }
  })
  const columns = useMemo<ColumnsType<ProjectDependencyAutoFixCandidate>>(
    () => [
      {
        title: '依赖',
        dataIndex: 'dependencyName',
        width: 150,
        ellipsis: { showTitle: false },
        render: (value, record) => (
          <Tooltip
            title={record.dependencyVersion ? `${value}@${record.dependencyVersion}` : value}
          >
            <span className={styles.autoFixDependency}>{value}</span>
          </Tooltip>
        )
      },
      { title: '风险', dataIndex: 'riskLevel', width: 76, render: riskTag },
      {
        title: '将安装到目标环境',
        width: 190,
        render: (_, record) => (
          <code className={styles.autoFixPackage}>{installTarget(record)}</code>
        )
      },
      {
        title: '选择依据',
        dataIndex: 'reason',
        ellipsis: { showTitle: false },
        render: (value) => (
          <Tooltip title={value}>
            <span className={styles.autoFixReason}>{value || '--'}</span>
          </Tooltip>
        )
      }
    ],
    []
  )

  function resetAndClose() {
    setSelectedKeys(null)
    setRerunAnalysis(true)
    onClose()
  }

  return (
    <BaseModal
      busy={createMutation.isPending}
      cancelText="取消"
      destroyOnHidden
      mask={{ closable: !createMutation.isPending }}
      okButtonProps={{
        disabled:
          candidatesQuery.isLoading || candidatesQuery.isError || !effectiveSelectedKeys.length,
        loading: createMutation.isPending
      }}
      okText={`修复选中的依赖${effectiveSelectedKeys.length ? `（${effectiveSelectedKeys.length}）` : ''}`}
      visible={open}
      title={
        <Flex align="center" gap={8}>
          <SafetyCertificateOutlined className={styles.autoFixTitleIcon} />
          <span>自动修复依赖</span>
        </Flex>
      }
      width={820}
      onCancel={() => {
        if (!createMutation.isPending) resetAndClose()
      }}
      onOk={() => createMutation.mutate(undefined)}
    >
      <div className={styles.autoFixContent}>
        <div className={styles.autoFixPath}>
          <span>分析发现的依赖</span>
          <ArrowRightOutlined />
          <strong>受控安装软件包</strong>
          <ArrowRightOutlined />
          <span>RISC-V 目标环境</span>
        </div>
        <p className={styles.autoFixDescription}>
          请选择要处理的依赖。后端将在当前目标环境中执行软件包安装，不会修改项目源码。
        </p>
        {candidatesQuery.isError ? (
          <StageStateNotice
            description="无法读取本次分析的可修复依赖，请重新加载。"
            embedded
            primaryAction={{ label: '重新加载', onClick: () => void candidatesQuery.refetch() }}
            title="自动修复候选项加载失败"
            variant="request-error"
          />
        ) : (
          <Table<ProjectDependencyAutoFixCandidate>
            columns={columns}
            dataSource={candidates ?? []}
            loading={candidatesQuery.isLoading}
            locale={{ emptyText: <ContentState description="本次分析没有可自动修复的依赖" /> }}
            pagination={false}
            rowKey="resultItemId"
            rowSelection={{
              preserveSelectedRowKeys: true,
              getCheckboxProps: () => ({ disabled: createMutation.isPending }),
              selectedRowKeys: effectiveSelectedKeys,
              onChange: (keys) => setSelectedKeys(keys)
            }}
            scroll={{ y: 320 }}
            size="small"
            tableLayout="fixed"
          />
        )}
        <div className={styles.autoFixFooterOption}>
          <Checkbox
            checked={rerunAnalysis}
            disabled={createMutation.isPending}
            onChange={(event) => setRerunAnalysis(event.target.checked)}
          >
            修复完成后重新执行依赖分析
          </Checkbox>
          <span>用于验证安装结果并生成一条新的分析记录</span>
        </div>
      </div>
    </BaseModal>
  )
}
