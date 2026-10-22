import { useState } from 'react'
import { DownOutlined, LeftOutlined, ReloadOutlined, UpOutlined } from '@ant-design/icons'
import { useIsFetching, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Flex, Tooltip } from 'antd'

import { getProjectBuildValidation } from '@/api/project/build-validation'
import ContentState from '@/components/ContentState'
import type { ProjectBuildValidation } from '@/types/project'
import { parseEnvironmentVariables } from '@/utils/display'

import { projectQueryKeys } from '../../queryKeys'
import PrerequisitePanel from '../components/PrerequisitePanel'
import StageSurface from '../components/StageSurface'
import { useStageDraft } from '../components/useStageDraft'
import { getStageDrawerWidth } from '../drawerWidth'
import type { StageDrawerProps } from '../types'
import BuildConfiguration from './components/BuildConfiguration'
import BuildRecordDetail from './components/BuildRecordDetail'
import BuildRecords from './components/BuildRecords'
import { projectBuildValidationQueryKey, useBuildDrawer } from './useBuildDrawer'

import drawerStyles from '../index.module.scss'
import styles from './index.module.scss'

const defaultBuildScript = '#!/usr/bin/env bash\nset -eu\nmake -j'

export default function Build({
  projectId,
  visible,
  stage,
  onClose,
  onStageChange,
  onDirtyChange
}: StageDrawerProps) {
  const queryClient = useQueryClient()
  const [script, setScript] = useState<string | null>(null)
  const [timeoutSeconds, setTimeoutSeconds] = useState(3600)
  const [environmentVariables, setEnvironmentVariables] = useState('')
  const [selectedBuild, setSelectedBuild] = useState<ProjectBuildValidation | null>(null)
  const selectedBuildQuery = useQuery({
    queryKey: projectQueryKeys.buildValidation(selectedBuild?.id),
    queryFn: () => getProjectBuildValidation(selectedBuild?.id ?? ''),
    enabled: visible && Boolean(selectedBuild),
    initialData: selectedBuild ?? undefined
  })
  const [preconditionsCollapsed, setPreconditionsCollapsed] = useState(false)
  const [configurationCollapsed, setConfigurationCollapsed] = useState(false)
  const isRecordsView = !selectedBuild
  const drawer = useBuildDrawer(projectId, visible && isRecordsView)
  const recordsQueryKey = [...projectBuildValidationQueryKey(projectId), 'records'] as const
  const recordsIsFetching = useIsFetching({ queryKey: recordsQueryKey }) > 0
  const buildReady = drawer.buildReady
  const [activeSourcePrerequisite, sourceEnvironmentPrerequisite, targetEnvironmentPrerequisite] =
    drawer.generationPrerequisites
  const missingSourceRevision = activeSourcePrerequisite?.status !== 'SATISFIED'
  const sourceEnvironmentReady = sourceEnvironmentPrerequisite?.status === 'SATISFIED'
  const targetEnvironmentReady = targetEnvironmentPrerequisite?.status === 'SATISFIED'
  const sourceEnvironment = drawer.context.sourceEnvironment
  const targetEnvironment = drawer.context.targetEnvironment
  const latestCommand =
    drawer.latestFreshness === 'CURRENT' ? drawer.latestBuild?.command.trim() : undefined
  const currentBuildId = drawer.latestFreshness === 'CURRENT' ? drawer.latestBuild?.id : undefined
  const effectiveScript = script ?? (latestCommand || defaultBuildScript)
  const { markSubmitted } = useStageDraft(
    { script: effectiveScript, timeoutSeconds, environmentVariables },
    { script: latestCommand || defaultBuildScript, timeoutSeconds: 3600, environmentVariables: '' },
    visible,
    onDirtyChange
  )
  const title = selectedBuild ? (
    <Flex align="center" className={drawerStyles.drawerTitle} gap={8}>
      <Tooltip title="返回构建记录">
        <Button
          aria-label="返回构建记录"
          className={drawerStyles.drawerBackButton}
          icon={<LeftOutlined />}
          shape="circle"
          type="text"
          onClick={() => setSelectedBuild(null)}
        />
      </Tooltip>
      <span className={drawerStyles.drawerTitleText}>
        {selectedBuild.environment?.name ?? '构建'}构建日志
      </span>
    </Flex>
  ) : (
    <Flex align="center" gap={12}>
      <span>{stage?.title ?? '构建验证'}</span>
    </Flex>
  )
  return (
    <StageSurface
      afterOpenChange={(open) => {
        if (open) return
        setSelectedBuild(null)
        setScript(null)
        setTimeoutSeconds(3600)
        setEnvironmentVariables('')
      }}
      loading={false}
      extra={
        isRecordsView ? (
          <Tooltip title="刷新构建信息">
            <Button
              aria-label="刷新构建信息"
              icon={<ReloadOutlined />}
              loading={drawer.isLoading || recordsIsFetching}
              type="text"
              onClick={() =>
                void Promise.all([
                  drawer.refetch(),
                  queryClient.refetchQueries({ queryKey: recordsQueryKey })
                ])
              }
            />
          </Tooltip>
        ) : undefined
      }
      size={getStageDrawerWidth('build')}
      title={title}
      panelTitleVisible={Boolean(selectedBuild)}
      panelScrollKey={selectedBuild?.id ?? 'records'}
      visible={visible}
      onClose={onClose}
    >
      {!selectedBuild && drawer.isError && drawer.hasData ? (
        <Alert showIcon type="warning" title="前置条件刷新失败，保留已读取内容；暂不能开始构建。" />
      ) : null}
      {!selectedBuild && drawer.isLoading ? (
        <ContentState kind="loading" description="正在读取前置条件" compact />
      ) : null}
      {!selectedBuild && drawer.isError && !drawer.hasData ? (
        <div className={styles.statePanel}>
          <ContentState kind="error" description="构建前置数据加载失败">
            <Button type="primary" onClick={() => void drawer.refetch()}>
              重试
            </Button>
          </ContentState>
        </div>
      ) : null}
      {selectedBuild ? (
        <BuildRecordDetail
          build={selectedBuildQuery.data ?? selectedBuild}
          onTaskCompleted={() => void selectedBuildQuery.refetch()}
        />
      ) : null}
      {!selectedBuild && !drawer.isLoading && (!drawer.isError || drawer.hasData) ? (
        <div className={styles.content}>
          <section
            className={[styles.section, preconditionsCollapsed ? styles.sectionCollapsed : '']
              .filter(Boolean)
              .join(' ')}
          >
            <Flex align="center" className={styles.sectionHeader} justify="space-between">
              <div className={styles.sectionHeading}>
                <h3>构建前置条件</h3>
              </div>
              <Button
                aria-label={preconditionsCollapsed ? '展开构建前置条件' : '收起构建前置条件'}
                aria-expanded={!preconditionsCollapsed}
                icon={preconditionsCollapsed ? <DownOutlined /> : <UpOutlined />}
                size="small"
                type="text"
                onClick={() => setPreconditionsCollapsed((current) => !current)}
              />
            </Flex>
            <PrerequisitePanel
              description={buildReady ? undefined : '请完成下方未满足的前置条件。'}
              items={[
                {
                  actionLabel: missingSourceRevision ? '前往源码管理' : undefined,
                  href: missingSourceRevision ? null : drawer.context.activeSourceRepositoryUrl,
                  key: 'source',
                  label: '当前源码',
                  onAction: missingSourceRevision ? () => onStageChange?.('assets') : undefined,
                  value: missingSourceRevision
                    ? '尚未配置'
                    : (drawer.context.activeSourceName ?? '--'),
                  valueTitle: drawer.context.activeSourceRepositoryUrl
                },
                {
                  actionLabel: sourceEnvironmentReady ? undefined : '前往环境管理',
                  key: 'source-environment',
                  label: 'x86 源环境',
                  onAction: sourceEnvironmentReady ? undefined : () => onStageChange?.('env'),
                  value: sourceEnvironmentReady
                    ? `${sourceEnvironment?.name ?? '--'} / ${sourceEnvironment?.architecture ?? '--'}`
                    : '尚未配置或不可用',
                  valueTitle: sourceEnvironment?.name
                },
                {
                  actionLabel: targetEnvironmentReady ? undefined : '前往环境管理',
                  key: 'target-environment',
                  label: 'RISC-V 目标环境',
                  onAction: targetEnvironmentReady ? undefined : () => onStageChange?.('env'),
                  value: targetEnvironmentReady
                    ? `${targetEnvironment?.name ?? '--'} / ${targetEnvironment?.architecture ?? '--'}`
                    : '尚未配置或不可用',
                  valueTitle: targetEnvironment?.name
                }
              ]}
              ready={buildReady}
              title={buildReady ? '可以开始构建验证' : '暂不能开始构建验证'}
            />
          </section>

          {buildReady ? (
            <section
              className={[styles.section, configurationCollapsed ? styles.sectionCollapsed : '']
                .filter(Boolean)
                .join(' ')}
            >
              <Flex align="center" className={styles.sectionHeader} justify="space-between">
                <div className={styles.sectionHeading}>
                  <h3>构建配置</h3>
                  <p>每个构建任务会先准备源码，再在对应环境中执行脚本。</p>
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
              <BuildConfiguration
                effectiveScript={effectiveScript}
                setScript={setScript}
                timeoutSeconds={timeoutSeconds}
                setTimeoutSeconds={setTimeoutSeconds}
                environmentVariables={environmentVariables}
                setEnvironmentVariables={setEnvironmentVariables}
                disabled={drawer.isError}
                isPending={drawer.buildMutation.isPending}
                onSubmit={() =>
                  drawer.buildMutation.mutate(
                    {
                      script: effectiveScript,
                      timeoutSeconds,
                      environmentVariables: parseEnvironmentVariables(environmentVariables)
                    },
                    { onSuccess: markSubmitted }
                  )
                }
              />
            </section>
          ) : null}
        </div>
      ) : null}
      {!selectedBuild ? (
        <BuildRecords
          projectId={projectId}
          queryKey={recordsQueryKey}
          currentBuildId={currentBuildId}
          onSelect={setSelectedBuild}
          onCancel={(id) => drawer.cancelMutation.mutate(id)}
        />
      ) : null}
    </StageSurface>
  )
}
