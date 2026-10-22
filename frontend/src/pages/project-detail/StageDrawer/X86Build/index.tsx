import { useState } from 'react'
import { DownOutlined, LeftOutlined, ReloadOutlined, UpOutlined } from '@ant-design/icons'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Flex, Form, Tooltip } from 'antd'

import {
  cancelProjectBuildValidation,
  createProjectBuildValidations,
  getProjectBuildValidation,
  getProjectBuildValidationLatest
} from '@/api/project/build-validation'
import { getProjectStageReadiness } from '@/api/project/workflow'
import ContentState from '@/components/ContentState'
import { useSessionMutation } from '@/hooks/useSessionMutation'
import type { ProjectBuildValidation } from '@/types/project'
import { parseEnvironmentVariables } from '@/utils/display'
import { feedback } from '@/utils/feedback'

import { projectQueryKeys } from '../../queryKeys'
import { useBuildReadinessContext } from '../buildReadinessContext'
import PrerequisitePanel from '../components/PrerequisitePanel'
import StageSurface from '../components/StageSurface'
import { useStageDraft } from '../components/useStageDraft'
import { getStageDrawerWidth } from '../drawerWidth'
import type { StageDrawerProps } from '../types'
import BuildLogView from './components/BuildLogView'
import X86BuildConfiguration from './components/X86BuildConfiguration'
import X86BuildRecords from './components/X86BuildRecords'

import styles from './index.module.scss'

const defaultScript = '#!/usr/bin/env bash\nset -eu\nmake -j'

export default function X86Build({
  projectId,
  visible,
  stage,
  onClose,
  onStageChange,
  onDirtyChange
}: StageDrawerProps) {
  const queryClient = useQueryClient()
  const {
    context,
    hasData: hasContextData,
    isError: isContextError,
    isLoading: isContextLoading,
    refetch: refetchContext
  } = useBuildReadinessContext(projectId)
  const [form] = Form.useForm<{
    timeoutSeconds: number
    environmentVariables: string
  }>()
  const [script, setScript] = useState<string | null>(null)
  const [selectedBuild, setSelectedBuild] = useState<ProjectBuildValidation | null>(null)
  const selectedBuildQuery = useQuery({
    queryKey: projectQueryKeys.buildValidation(selectedBuild?.id),
    queryFn: () => getProjectBuildValidation(selectedBuild?.id ?? ''),
    enabled: visible && Boolean(selectedBuild),
    initialData: selectedBuild ?? undefined
  })
  const [configurationCollapsed, setConfigurationCollapsed] = useState(false)
  const readinessQuery = useQuery({
    queryKey: projectQueryKeys.readiness(projectId, 'x86-build'),
    queryFn: () => getProjectStageReadiness(projectId ?? '', 'x86-build'),
    enabled: visible && Boolean(projectId) && !selectedBuild
  })
  const activeSourcePrerequisite = readinessQuery.data?.prerequisites.find(
    (item) => item.key === 'ACTIVE_SOURCE'
  )
  const sourceEnvironmentPrerequisite = readinessQuery.data?.prerequisites.find(
    (item) => item.key === 'SOURCE_ENVIRONMENT'
  )
  const readinessSourceRevisionId = readinessQuery.data?.context.sourceRevisionId ?? undefined
  const missingSourceRevision = activeSourcePrerequisite?.status !== 'SATISFIED'
  const missingSourceEnvironment = sourceEnvironmentPrerequisite?.status !== 'SATISFIED'
  const sourceReady = !missingSourceRevision && !missingSourceEnvironment
  const buildRecordsQueryKey = ['project-build-validations', projectId, 'SOURCE_ONLY'] as const
  const queryKey = [...buildRecordsQueryKey, 'history'] as const
  const latestBuildQuery = useQuery({
    queryKey: [...buildRecordsQueryKey, 'latest'],
    queryFn: () => getProjectBuildValidationLatest(projectId ?? '', 'SOURCE_ONLY'),
    enabled: visible && Boolean(projectId) && !selectedBuild
  })
  const latestCommand =
    latestBuildQuery.data?.freshness === 'CURRENT'
      ? latestBuildQuery.data.result?.command.trim()
      : undefined
  const currentBuildId =
    latestBuildQuery.data?.freshness === 'CURRENT' ? latestBuildQuery.data.result?.id : undefined
  const effectiveScript = script ?? (latestCommand || defaultScript)
  const configValues = Form.useWatch([], { form, preserve: true }) as
    { timeoutSeconds?: number; environmentVariables?: string } | undefined
  const { markSubmitted } = useStageDraft(
    {
      script: effectiveScript,
      timeoutSeconds: configValues?.timeoutSeconds ?? 3600,
      environmentVariables: configValues?.environmentVariables ?? ''
    },
    { script: latestCommand || defaultScript, timeoutSeconds: 3600, environmentVariables: '' },
    visible,
    onDirtyChange
  )
  const hasData = Boolean(hasContextData && readinessQuery.data && latestBuildQuery.data)
  const isError = isContextError || readinessQuery.isError || latestBuildQuery.isError
  const isLoading = isContextLoading || readinessQuery.isLoading || latestBuildQuery.isLoading
  const refetch = () =>
    Promise.all([
      refetchContext(),
      readinessQuery.refetch(),
      queryClient.refetchQueries({ queryKey: buildRecordsQueryKey })
    ])
  const createMutation = useSessionMutation({
    sessionKey: `x86-build:${projectId}:${readinessSourceRevisionId}`,
    active: visible && !selectedBuild,
    mutationFn: (values: {
      script: string
      timeoutSeconds: number
      environmentVariables: string
    }) =>
      createProjectBuildValidations(projectId ?? '', {
        sourceRevisionId: readinessSourceRevisionId,
        buildScope: 'SOURCE_ONLY',
        script: values.script,
        timeoutSeconds: values.timeoutSeconds,
        environmentVariables: parseEnvironmentVariables(values.environmentVariables)
      }),
    onSuccess: () => {
      feedback.success('x86 构建任务已创建')
    }
  })
  const submitBuild = (values: { timeoutSeconds: number; environmentVariables: string }) => {
    if (isError || !sourceReady || createMutation.isPending) return
    if (!effectiveScript.trim()) {
      feedback.error('请输入构建命令')
      return
    }

    createMutation.mutate({ ...values, script: effectiveScript }, { onSuccess: markSubmitted })
  }
  const cancelMutation = useSessionMutation({
    sessionKey: `cancel-x86-build:${projectId}`,
    active: visible,
    mutationFn: cancelProjectBuildValidation,
    onSuccess: () => {
      feedback.success('构建取消请求已提交')
    }
  })
  const title = selectedBuild ? (
    <Flex align="center" gap={4}>
      <Tooltip title="返回构建记录">
        <Button
          aria-label="返回构建记录"
          icon={<LeftOutlined />}
          shape="circle"
          type="text"
          onClick={() => setSelectedBuild(null)}
        />
      </Tooltip>
      <span>x86 构建详情</span>
    </Flex>
  ) : (
    <Flex align="center" gap={12}>
      <span>{stage?.title ?? 'x86 构建'}</span>
    </Flex>
  )

  return (
    <StageSurface
      afterOpenChange={(open) => {
        if (open) return
        setSelectedBuild(null)
        setScript(null)
        form.resetFields()
      }}
      extra={
        !selectedBuild ? (
          <Tooltip title="刷新构建信息">
            <Button
              aria-label="刷新构建信息"
              icon={<ReloadOutlined />}
              loading={false}
              type="text"
              onClick={() => void refetch()}
            />
          </Tooltip>
        ) : undefined
      }
      loading={false}
      size={getStageDrawerWidth('x86-build')}
      title={title}
      panelTitleVisible={Boolean(selectedBuild)}
      panelScrollKey={selectedBuild?.id ?? 'records'}
      visible={visible}
      onClose={onClose}
    >
      {!selectedBuild && isError && hasData ? (
        <Alert showIcon type="warning" title="前置条件刷新失败，保留已读取内容；暂不能开始构建。" />
      ) : null}
      {!selectedBuild && isLoading ? (
        <ContentState kind="loading" description="正在读取前置条件" compact />
      ) : null}
      {!selectedBuild && isError && !hasData ? (
        <ContentState kind="error" description="x86 构建前置数据加载失败">
          <Button type="primary" onClick={() => void refetch()}>
            重试
          </Button>
        </ContentState>
      ) : null}
      {selectedBuild ? (
        <BuildLogView
          build={selectedBuildQuery.data ?? selectedBuild}
          onTaskCompleted={() => {
            void Promise.all([refetch(), selectedBuildQuery.refetch()])
          }}
        />
      ) : null}
      {!isLoading && (!isError || hasData) && !selectedBuild ? (
        <div className={styles.content}>
          <section className={styles.section}>
            <Flex align="center" justify="space-between">
              <div className={styles.sectionHeading}>
                <h3>构建前置条件</h3>
              </div>
            </Flex>
            <PrerequisitePanel
              description={sourceReady ? undefined : '请完成下方未满足的前置条件。'}
              items={[
                {
                  actionLabel: missingSourceRevision ? '前往源码管理' : undefined,
                  href: missingSourceRevision ? null : context.activeSourceRepositoryUrl,
                  key: 'source',
                  label: '当前源码',
                  onAction: missingSourceRevision ? () => onStageChange?.('assets') : undefined,
                  value: missingSourceRevision ? '尚未配置' : (context.activeSourceName ?? '--'),
                  valueTitle: context.activeSourceRepositoryUrl
                },
                {
                  actionLabel: missingSourceEnvironment ? '前往环境管理' : undefined,
                  key: 'environment',
                  label: '当前环境',
                  onAction: missingSourceEnvironment ? () => onStageChange?.('env') : undefined,
                  value: missingSourceEnvironment
                    ? '尚未配置完整'
                    : `${context.sourceEnvironment?.name ?? '--'} / ${context.sourceEnvironment?.architecture ?? '--'}`,
                  valueTitle: context.sourceEnvironment?.name
                }
              ]}
              ready={sourceReady}
              title={sourceReady ? '可以开始构建' : '暂不能开始构建'}
            />
          </section>
          {sourceReady ? (
            <section className={styles.section}>
              <Flex align="center" justify="space-between">
                <div className={styles.sectionHeading}>
                  <h3>构建配置</h3>
                  <p>命令在 x86 源环境执行，环境变量仅对本次任务生效。</p>
                </div>
                <Button
                  aria-label={configurationCollapsed ? '展开构建配置' : '收起构建配置'}
                  aria-expanded={!configurationCollapsed}
                  icon={configurationCollapsed ? <DownOutlined /> : <UpOutlined />}
                  size="small"
                  type="text"
                  onClick={() => setConfigurationCollapsed((current) => !current)}
                />
              </Flex>
              {!configurationCollapsed ? (
                <X86BuildConfiguration
                  form={form}
                  effectiveScript={effectiveScript}
                  setScript={setScript}
                  submitBuild={submitBuild}
                  disabled={isError}
                  isPending={createMutation.isPending}
                />
              ) : null}
            </section>
          ) : null}
        </div>
      ) : null}
      {!selectedBuild ? (
        <X86BuildRecords
          projectId={projectId}
          queryKey={queryKey}
          currentBuildId={currentBuildId}
          onSelect={setSelectedBuild}
          onCancel={(id) => cancelMutation.mutate(id)}
        />
      ) : null}
    </StageSurface>
  )
}
