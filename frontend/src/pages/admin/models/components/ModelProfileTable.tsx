import {
  DeleteOutlined,
  EditOutlined,
  ExperimentOutlined,
  LinkOutlined,
  LoadingOutlined,
  PoweroffOutlined
} from '@ant-design/icons'
import { Button, Flex, Popconfirm, Tag, Tooltip } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { RefObject } from 'react'

import { getModelProfiles } from '@/api/admin/models'
import type { BaseTableHandle } from '@/components/BaseTable'
import BaseTable from '@/components/BaseTable'
import type { ModelProfile, ModelProfileListParams } from '@/types/admin/models'
import { formatDateTime } from '@/utils/display'

import { latestAgentProbeTime } from '../presentation'
import { modelQueryKeys } from '../queryKeys'
import type { useModelProfiles } from '../useModelProfiles'
import AgentCompatibilitySummary from './AgentCompatibilitySummary'

import styles from '../index.module.scss'
type Filters = Pick<ModelProfileListParams, 'keyword'>

export default function ModelProfileTable({
  model,
  tableRef
}: {
  model: ReturnType<typeof useModelProfiles>
  tableRef: RefObject<BaseTableHandle | null>
}) {
  const {
    agentRuntimesQuery,
    connectivityMutation,
    setTestModalProfile,
    setModalProfile,
    updateStatusMutation,
    deleteMutation
  } = model
  const columns: ColumnsType<ModelProfile> = [
    {
      dataIndex: 'name',
      title: 'Profile',
      width: 180,
      render: (value) => <span className={styles.profileName}>{value}</span>
    },
    { dataIndex: 'model', title: '模型', width: 180, render: (value) => value || '--' },
    {
      dataIndex: 'baseUrl',
      title: 'API 地址',
      width: 300,
      ellipsis: { showTitle: false },
      render: (value) =>
        value ? (
          <Tooltip title={value}>
            <span className={styles.endpoint}>{value}</span>
          </Tooltip>
        ) : (
          '--'
        )
    },
    {
      dataIndex: 'lastConnectivityStatus',
      title: '连通性',
      width: 110,
      render: (value, profile) => {
        if (!profile.lastConnectivityTestedAt) return <Tag>未测试</Tag>
        const presentation =
          value === 'SUCCESS'
            ? { color: 'success', text: '可用' }
            : value === 'TIMEOUT'
              ? { color: 'warning', text: '超时' }
              : { color: 'error', text: '失败' }
        return (
          <Tooltip title={profile.lastConnectivityMessage || '暂无测试说明'}>
            <Tag color={presentation.color}>{presentation.text}</Tag>
          </Tooltip>
        )
      }
    },
    {
      key: 'agentCompatibility',
      title: 'Agent 兼容性',
      width: 300,
      render: (_, profile) => {
        if (profile.activeAgentProbeRun) {
          return (
            <Tag color="processing" icon={<LoadingOutlined spin />}>
              正在测试 {profile.activeAgentProbeRun.agentRuntimes.length} 个 Agent
            </Tag>
          )
        }
        if (profile.agentProbeResults.length === 0) return <Tag>未测试</Tag>
        return (
          <AgentCompatibilitySummary
            agentRuntimes={agentRuntimesQuery.data ?? []}
            results={profile.agentProbeResults}
          />
        )
      }
    },
    {
      key: 'lastAgentProbeAt',
      title: 'Agent 最近测试',
      width: 170,
      render: (_, profile) => formatDateTime(latestAgentProbeTime(profile.agentProbeResults))
    },
    {
      dataIndex: 'enabled',
      title: '状态',
      width: 90,
      render: (value) => <Tag color={value ? 'success' : 'default'}>{value ? '启用' : '停用'}</Tag>
    },
    {
      key: 'actions',
      title: '操作',
      fixed: 'right',
      width: 184,
      render: (_, profile) => {
        const isProbeRunning = Boolean(profile.activeAgentProbeRun)
        const canTestAgents = profile.lastConnectivityStatus === 'SUCCESS' && !isProbeRunning
        const agentProbeTip = isProbeRunning
          ? 'Agent 兼容性测试运行中'
          : profile.lastConnectivityStatus === 'SUCCESS'
            ? '测试 Agent 兼容性'
            : '请先通过模型连通性测试'

        return (
          <Flex gap={4}>
            <Tooltip title="测试模型连通性">
              <Button
                aria-label="测试模型连通性"
                icon={<LinkOutlined />}
                loading={
                  connectivityMutation.isPending && connectivityMutation.variables === profile.id
                }
                size="small"
                type="text"
                onClick={() => connectivityMutation.mutate(profile.id)}
              />
            </Tooltip>
            <Tooltip title={agentProbeTip}>
              <Button
                aria-label="测试 Agent 兼容性"
                disabled={!canTestAgents}
                icon={<ExperimentOutlined />}
                loading={isProbeRunning}
                size="small"
                type="text"
                onClick={() => setTestModalProfile(profile)}
              />
            </Tooltip>
            <Tooltip title="编辑 Profile">
              <Button
                aria-label="编辑 Profile"
                icon={<EditOutlined />}
                size="small"
                type="text"
                onClick={() => setModalProfile(profile)}
              />
            </Tooltip>
            <Popconfirm
              title={`确认${profile.enabled ? '停用' : '启用'}该 Profile？`}
              onConfirm={() =>
                updateStatusMutation.mutate({ enabled: !profile.enabled, profileId: profile.id })
              }
            >
              <Tooltip title={profile.enabled ? '停用 Profile' : '启用 Profile'}>
                <Button
                  aria-label={profile.enabled ? '停用 Profile' : '启用 Profile'}
                  icon={<PoweroffOutlined />}
                  loading={
                    updateStatusMutation.isPending &&
                    updateStatusMutation.variables?.profileId === profile.id
                  }
                  size="small"
                  type="text"
                />
              </Tooltip>
            </Popconfirm>
            <Popconfirm
              description="已绑定到阶段的 Profile 无法删除。"
              title="确认删除该 Profile？"
              onConfirm={() => deleteMutation.mutate(profile.id)}
            >
              <Tooltip title="删除 Profile">
                <Button
                  aria-label="删除 Profile"
                  danger
                  icon={<DeleteOutlined />}
                  loading={deleteMutation.isPending && deleteMutation.variables === profile.id}
                  size="small"
                  type="text"
                />
              </Tooltip>
            </Popconfirm>
          </Flex>
        )
      }
    }
  ]

  return (
    <BaseTable<ModelProfile, Filters>
      className={styles.profilesTable}
      columns={columns}
      queryKey={modelQueryKeys.profiles()}
      ref={tableRef}
      rowKey="id"
      autoHeight
      request={(query) =>
        getModelProfiles({
          keyword: query.keyword,
          page: query.page,
          pageSize: query.pageSize
        })
      }
      scroll={{ x: 'max-content' }}
      toolbar={{
        filters: {
          fields: [{ name: 'keyword', placeholder: '搜索名称或模型', type: 'search' }]
        }
      }}
    />
  )
}
