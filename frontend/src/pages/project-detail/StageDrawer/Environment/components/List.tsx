import {
  AimOutlined,
  CheckCircleOutlined,
  EditOutlined,
  HistoryOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined
} from '@ant-design/icons'
import { Button, Flex, Popconfirm, Tag, Tooltip } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { getProjectEnvironments } from '@/api/project/environments'
import type { BaseTableFilterField } from '@/components/BaseTable'
import BaseTable from '@/components/BaseTable'
import type {
  ProjectEnvironment,
  ProjectEnvironmentListParams,
  ProjectEnvironmentRole,
  ProjectRuntimeEnvironments
} from '@/types/project'
import { formatDateTime } from '@/utils/display'

import { projectQueryKeys } from '../../../queryKeys'
import {
  environmentConnectionStatusConfig,
  environmentRoleOptions,
  environmentRoleText
} from '../constants'

import styles from '../index.module.scss'

interface EnvironmentFilters {
  role?: ProjectEnvironmentRole
  status?: ProjectEnvironmentListParams['status']
}

const environmentFilterFields: BaseTableFilterField<EnvironmentFilters>[] = [
  {
    name: 'role',
    options: environmentRoleOptions,
    placeholder: '角色',
    type: 'select'
  },
  {
    name: 'status',
    options: [
      { label: '连接成功', value: 'AVAILABLE' },
      { label: '连接失败', value: 'UNAVAILABLE' },
      { label: '未检查', value: 'UNKNOWN' },
      { label: '已禁用', value: 'DISABLED' }
    ],
    placeholder: '环境状态',
    type: 'select'
  }
]

interface EnvironmentListActions {
  checkingEnvironmentId: string | null
  onCheck: (environment: ProjectEnvironment) => Promise<void>
  onCreate: () => void
  onEdit: (environment: ProjectEnvironment) => void
  onHistory: (environment: ProjectEnvironment) => void
  onRefresh: () => Promise<void>
  onRunScript: (environment: ProjectEnvironment) => void
  onSetCurrent: (environment: ProjectEnvironment) => Promise<void>
  settingRuntimeEnvironmentId: string | null
}

interface ListProps {
  actions: EnvironmentListActions
  projectId: string
  runtimeEnvironments?: ProjectRuntimeEnvironments
}

export default function List({ actions, projectId, runtimeEnvironments }: ListProps) {
  const {
    checkingEnvironmentId,
    onCheck,
    onCreate,
    onEdit,
    onHistory,
    onRefresh,
    onRunScript,
    onSetCurrent,
    settingRuntimeEnvironmentId
  } = actions
  const handleCheck = async (environment: ProjectEnvironment) => {
    await onCheck(environment)
  }
  const columns: ColumnsType<ProjectEnvironment> = [
    { dataIndex: 'name', title: '名称', width: 200 },
    {
      dataIndex: 'role',
      title: '角色',
      width: 140,
      render: (value: ProjectEnvironmentRole) => environmentRoleText[value]
    },
    { dataIndex: 'architecture', title: '架构', width: 96 },
    {
      dataIndex: 'os',
      title: 'OS',
      width: 140,
      render: (value: string | null) => value ?? '-'
    },
    { dataIndex: 'host', title: '主机', width: 160 },
    {
      key: 'environmentStatus',
      title: '环境状态',
      width: 100,
      render: (_, environment) => {
        const config = environment.enabled
          ? environmentConnectionStatusConfig[environment.connectionStatus]
          : { color: 'default' as const, text: '已禁用' }
        return <Tag color={config.color}>{config.text}</Tag>
      }
    },
    {
      dataIndex: 'basicInfo',
      title: '包管理器',
      width: 120,
      render: (value: ProjectEnvironment['basicInfo']) => value?.packageManager ?? '-'
    },
    {
      dataIndex: 'basicInfo',
      title: '最近检查',
      width: 160,
      render: (value: ProjectEnvironment['basicInfo']) => formatDateTime(value?.checkedAt)
    },
    {
      key: 'actions',
      title: '操作',
      fixed: 'right',
      width: 200,
      render: (_, environment) => {
        const canRunScript = environment.enabled !== false
        const currentEnvironment =
          environment.role === 'SOURCE'
            ? runtimeEnvironments?.sourceEnvironment
            : runtimeEnvironments?.targetEnvironment
        const isCurrent =
          environment.role !== 'JUMP_HOST' && currentEnvironment?.id === environment.id
        const roleText = environment.role === 'SOURCE' ? '源环境' : '目标环境'
        const canSetCurrent =
          environment.role !== 'JUMP_HOST' &&
          environment.enabled !== false &&
          environment.connectionStatus === 'SUCCESS'
        const setCurrentButton = !isCurrent ? (
          <Button
            aria-label={`设为当前${roleText}`}
            disabled={!canSetCurrent}
            icon={<AimOutlined />}
            loading={settingRuntimeEnvironmentId === environment.id}
            size="small"
            type="text"
          />
        ) : null

        return (
          <Flex className={styles.rowActions} gap={2}>
            <Tooltip title="修改环境">
              <Button
                aria-label="修改环境"
                icon={<EditOutlined />}
                onClick={() => onEdit(environment)}
                size="small"
                type="text"
              />
            </Tooltip>
            <Tooltip title={canRunScript ? '运行脚本' : '请先启用环境'}>
              <Button
                aria-label="运行脚本"
                disabled={!canRunScript}
                icon={<PlayCircleOutlined />}
                onClick={() => onRunScript(environment)}
                size="small"
                type="text"
              />
            </Tooltip>
            <span aria-hidden="true" className={styles.actionDivider} />
            <Tooltip title="环境检查">
              <Popconfirm
                cancelText="取消"
                description="将检查 SSH 连接、基础工具、工作目录和权限。"
                okButtonProps={{ loading: checkingEnvironmentId === environment.id }}
                okText="开始检查"
                onConfirm={() => handleCheck(environment)}
                title={`检查环境“${environment.name}”？`}
              >
                <Button
                  aria-label="环境检查"
                  icon={<SafetyCertificateOutlined />}
                  loading={checkingEnvironmentId === environment.id}
                  size="small"
                  type="text"
                />
              </Popconfirm>
            </Tooltip>
            {environment.role === 'JUMP_HOST' ? null : isCurrent ? (
              <Tooltip title={`当前${roleText}`}>
                <span
                  aria-label={`当前${roleText}`}
                  className={styles.currentEnvironmentIndicator}
                  data-visual="outlined"
                  role="img"
                >
                  <CheckCircleOutlined />
                </span>
              </Tooltip>
            ) : canSetCurrent ? (
              <Tooltip title={`设为当前${roleText}`}>
                <Popconfirm
                  cancelText="取消"
                  description="切换后，依赖当前运行环境的后续结果需要重新执行。"
                  okButtonProps={{ loading: settingRuntimeEnvironmentId === environment.id }}
                  okText="确认设置"
                  title={`设为当前${roleText}？`}
                  onConfirm={() => onSetCurrent(environment)}
                >
                  {setCurrentButton}
                </Popconfirm>
              </Tooltip>
            ) : (
              <Tooltip title="请先启用环境并完成环境检查">
                <span>{setCurrentButton}</span>
              </Tooltip>
            )}
            <Tooltip title="执行记录">
              <Button
                aria-label="执行记录"
                icon={<HistoryOutlined />}
                onClick={() => onHistory(environment)}
                size="small"
                type="text"
              />
            </Tooltip>
          </Flex>
        )
      }
    }
  ]
  const requestEnvironments = async (query: Parameters<typeof getProjectEnvironments>[1]) => {
    return getProjectEnvironments(projectId, query)
  }

  return (
    <section className={styles.environmentList}>
      <h3>环境列表</h3>
      <BaseTable<ProjectEnvironment, EnvironmentFilters>
        autoHeight
        columns={columns}
        emptyDescription="暂无环境，请新建环境"
        pagination={{ initialPageSize: 20 }}
        queryKey={projectQueryKeys.environments(projectId)}
        request={requestEnvironments}
        rowKey="id"
        scroll={{ x: 1316 }}
        tableLayout="fixed"
        toolbar={{
          filters: { fields: environmentFilterFields },
          actions: (
            <Flex gap={8}>
              <Tooltip title="刷新环境列表">
                <Button
                  aria-label="刷新环境列表"
                  icon={<ReloadOutlined />}
                  type="text"
                  onClick={() => void onRefresh()}
                />
              </Tooltip>
              <Button icon={<PlusOutlined />} onClick={onCreate} type="primary">
                新建环境
              </Button>
            </Flex>
          )
        }}
      />
    </section>
  )
}
