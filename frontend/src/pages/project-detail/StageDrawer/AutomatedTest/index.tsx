import { useState } from 'react'
import { DownOutlined, ReloadOutlined, UpOutlined } from '@ant-design/icons'
import { Alert, Button, Flex, Tooltip } from 'antd'

import ContentState from '@/components/ContentState'
import type { ProjectAutomatedTest, ProjectTestComparison } from '@/types/project'
import { parseEnvironmentVariables } from '@/utils/display'

import PrerequisitePanel from '../components/PrerequisitePanel'
import RecordViewTitle from '../components/RecordViewTitle'
import StageSurface from '../components/StageSurface'
import { useStageDraft } from '../components/useStageDraft'
import { getStageDrawerWidth } from '../drawerWidth'
import type { StageDrawerProps } from '../types'
import ComparisonRecordDetail from './components/ComparisonRecordDetail'
import TestBatchResults from './components/TestBatchResults'
import TestConfiguration from './components/TestConfiguration'
import TestRecordDetail from './components/TestRecordDetail'
import TestRecords from './components/TestRecords'
import { useAutomatedTestDrawer } from './useAutomatedTestDrawer'

import styles from './index.module.scss'

const defaultCommand = 'ctest --test-dir build --output-on-failure'

export default function Test({
  projectId,
  visible,
  stage,
  onClose,
  onStageChange,
  onDirtyChange
}: StageDrawerProps) {
  const [command, setCommand] = useState<string | null>(null)
  const [timeoutSeconds, setTimeoutSeconds] = useState(3600)
  const [variables, setVariables] = useState('')
  const [selectedTest, setSelectedTest] = useState<ProjectAutomatedTest | null>(null)
  const [selectedComparison, setSelectedComparison] = useState<ProjectTestComparison | null>(null)
  const [view, setView] = useState<{ type: 'latest' } | { batchId: string; type: 'record' }>({
    type: 'latest'
  })
  const [preconditionsCollapsed, setPreconditionsCollapsed] = useState(false)
  const [configurationCollapsed, setConfigurationCollapsed] = useState(false)
  const logOpen = Boolean(selectedTest || selectedComparison)
  const currentEnabled = visible && view.type === 'latest' && !logOpen
  const recordsEnabled = visible && !logOpen
  const drawer = useAutomatedTestDrawer(projectId, {
    currentEnabled,
    recordsEnabled,
    submissionEnabled: visible
  })
  const latestCommand =
    drawer.latestFreshness === 'CURRENT' ? drawer.latestTest?.command.trim() : undefined
  const effectiveCommand = command ?? (latestCommand || defaultCommand)
  const { markSubmitted } = useStageDraft(
    { command: effectiveCommand, timeoutSeconds, variables },
    { command: latestCommand || defaultCommand, timeoutSeconds: 3600, variables: '' },
    visible,
    onDirtyChange
  )
  const displayedBatchId = view.type === 'record' ? view.batchId : null
  const displayedTests = drawer.tests.filter((item) => item.testBatchId === displayedBatchId)
  const displayedComparison = drawer.comparisons.find(
    (item) => item.testBatchId === displayedBatchId
  )
  const logBackLabel = view.type === 'record' ? '返回测试记录概览' : '返回测试记录'
  const title = selectedTest ? (
    <RecordViewTitle
      backLabel={logBackLabel}
      title={`${selectedTest.environmentName} 测试日志`}
      onBack={() => setSelectedTest(null)}
    />
  ) : selectedComparison ? (
    <RecordViewTitle
      backLabel={logBackLabel}
      title="测试结果对比日志"
      onBack={() => setSelectedComparison(null)}
    />
  ) : view.type === 'record' ? (
    <RecordViewTitle
      backLabel="返回测试记录"
      title="测试记录概览"
      onBack={() => setView({ type: 'latest' })}
    />
  ) : (
    <Flex align="center" gap={12}>
      <span>{stage?.title ?? '自动化测试'}</span>
    </Flex>
  )

  return (
    <StageSurface
      afterOpenChange={(open) => {
        if (open) return
        setSelectedTest(null)
        setSelectedComparison(null)
        setView({ type: 'latest' })
        setCommand(null)
        setTimeoutSeconds(3600)
        setVariables('')
      }}
      loading={false}
      panelTitleVisible={Boolean(selectedTest || selectedComparison || view.type !== 'latest')}
      panelScrollKey={`${view.type}:${view.type === 'record' ? view.batchId : ''}:${selectedTest?.id ?? ''}:${selectedComparison?.id ?? ''}`}
      extra={
        !logOpen ? (
          <Tooltip title="刷新自动化测试信息">
            <Button
              aria-label="刷新自动化测试信息"
              icon={<ReloadOutlined />}
              loading={false}
              type="text"
              onClick={() => void drawer.refetch()}
            />
          </Tooltip>
        ) : undefined
      }
      size={getStageDrawerWidth('test')}
      title={title}
      visible={visible}
      onClose={onClose}
    >
      {currentEnabled && drawer.currentError && !drawer.currentHasData ? (
        <div className={styles.state}>
          <ContentState kind="error" description="自动化测试数据加载失败">
            <Button type="primary" onClick={() => void drawer.refetch()}>
              重试
            </Button>
          </ContentState>
        </div>
      ) : null}
      {selectedTest ? (
        <TestRecordDetail test={selectedTest} onTaskCompleted={() => void drawer.refetch()} />
      ) : null}
      {selectedComparison ? (
        <ComparisonRecordDetail
          comparison={selectedComparison}
          onTaskCompleted={() => void drawer.refetch()}
        />
      ) : null}
      {!selectedTest && !selectedComparison ? (
        <div className={styles.root}>
          {view.type === 'latest' &&
          !drawer.currentLoading &&
          (!drawer.currentError || drawer.currentHasData) ? (
            <section
              className={[styles.section, preconditionsCollapsed ? styles.sectionCollapsed : '']
                .filter(Boolean)
                .join(' ')}
            >
              <Flex align="center" className={styles.sectionHeader} justify="space-between">
                <div className={styles.sectionHeading}>
                  <h3>测试前置条件</h3>
                </div>
                <Button
                  aria-label={preconditionsCollapsed ? '展开测试前置条件' : '收起测试前置条件'}
                  aria-expanded={!preconditionsCollapsed}
                  icon={preconditionsCollapsed ? <DownOutlined /> : <UpOutlined />}
                  size="small"
                  type="text"
                  onClick={() => setPreconditionsCollapsed((current) => !current)}
                />
              </Flex>
              <PrerequisitePanel
                description={drawer.ready ? undefined : '请完成下方未满足的构建验证。'}
                items={[
                  {
                    actionLabel: drawer.ready ? undefined : '前往构建验证',
                    key: 'BUILD_VALIDATION',
                    label: '双环境构建验证',
                    onAction: drawer.ready ? undefined : () => onStageChange?.('build'),
                    value: drawer.ready
                      ? 'x86 与 RISC-V 构建均可用'
                      : drawer.buildValidationPrerequisite?.status === 'RUNNING'
                        ? '构建验证进行中'
                        : drawer.buildValidationPrerequisite?.status === 'FAILED'
                          ? '最近构建验证未通过'
                          : '尚无有效双环境构建'
                  },
                  ...(drawer.ready
                    ? drawer.buildContexts.map(({ role, build, reason }) => ({
                        key: role,
                        label: role === 'SOURCE' ? 'x86 构建输入' : 'RISC-V 构建输入',
                        value: build
                          ? `${build.environment?.name ?? '--'} · 构建成功 · ${build.workingDirectory}`
                          : reason
                      }))
                    : [])
                ]}
                ready={drawer.ready && drawer.canCreate}
                title={drawer.ready ? '可以开始自动化测试' : '暂不能开始自动化测试'}
              />
            </section>
          ) : null}
          {view.type === 'latest' &&
          !drawer.currentLoading &&
          (!drawer.currentError || drawer.currentHasData) &&
          drawer.ready ? (
            <section
              className={[styles.section, configurationCollapsed ? styles.sectionCollapsed : '']
                .filter(Boolean)
                .join(' ')}
            >
              <Flex align="center" className={styles.sectionHeader} justify="space-between">
                <div className={styles.sectionHeading}>
                  <h3>测试配置</h3>
                  <p>命令、超时和环境变量将同时用于两个环境。</p>
                </div>
                <Button
                  aria-label={configurationCollapsed ? '展开测试配置' : '收起测试配置'}
                  aria-expanded={!configurationCollapsed}
                  icon={configurationCollapsed ? <DownOutlined /> : <UpOutlined />}
                  size="small"
                  type="text"
                  onClick={() => setConfigurationCollapsed((current) => !current)}
                />
              </Flex>
              {drawer.batchSubmission.batch?.failed.length ? (
                <Alert
                  type="warning"
                  showIcon
                  title="本批次尚未完整创建"
                  description={`已确认提交 ${Object.keys(drawer.batchSubmission.batch.created).length} 个任务；失败侧：${drawer.batchSubmission.batch.failed.map((role) => (role === 'SOURCE' ? 'x86' : 'RISC-V')).join('、')}。重试沿用本批次配置和批次编号。`}
                  action={
                    <Flex vertical gap={8}>
                      <Button
                        loading={drawer.batchSubmission.isPending}
                        onClick={() => void drawer.batchSubmission.retry()}
                      >
                        重试失败侧
                      </Button>
                      <Button
                        disabled={drawer.batchSubmission.isPending}
                        onClick={drawer.batchSubmission.startNewBatch}
                      >
                        保留已提交任务，开始新批次
                      </Button>
                    </Flex>
                  }
                />
              ) : null}
              <TestConfiguration
                effectiveCommand={effectiveCommand}
                setCommand={setCommand}
                timeoutSeconds={timeoutSeconds}
                setTimeoutSeconds={setTimeoutSeconds}
                variables={variables}
                setVariables={setVariables}
                isPending={drawer.batchSubmission.isPending}
                canCreate={drawer.canCreate && !drawer.batchSubmission.batch?.failed.length}
                onSubmit={() =>
                  void drawer.batchSubmission.submit(
                    {
                      command: effectiveCommand,
                      timeoutSeconds,
                      environmentVariables: parseEnvironmentVariables(variables)
                    },
                    markSubmitted
                  )
                }
              />
            </section>
          ) : null}
          {view.type === 'record' && displayedBatchId ? (
            <TestBatchResults
              tests={displayedTests}
              comparison={displayedComparison}
              readOnly
              onShowTestLog={setSelectedTest}
              onShowComparisonLog={setSelectedComparison}
              onCancel={(id) => drawer.cancelMutation.mutate(id)}
            />
          ) : null}
        </div>
      ) : null}
      {currentEnabled && drawer.currentLoading ? (
        <ContentState kind="loading" description="正在读取测试条件" compact />
      ) : null}
      {currentEnabled && drawer.currentError && drawer.currentHasData ? (
        <Alert showIcon type="warning" title="测试条件刷新失败，保留已有内容；暂不能新建测试。" />
      ) : null}
      {!logOpen && view.type === 'latest' ? (
        <section className={styles.section}>
          <h3>测试记录</h3>
          {drawer.recordsLoading ? (
            <ContentState kind="loading" description="正在读取测试记录" compact />
          ) : null}
          {drawer.recordsError ? (
            <ContentState kind="error" description="测试记录刷新失败">
              <Button onClick={() => void drawer.refetch()}>重新加载记录</Button>
            </ContentState>
          ) : null}
          {!drawer.recordsLoading && (!drawer.recordsError || drawer.recordsHasData) ? (
            <TestRecords
              tests={drawer.tests}
              comparisons={drawer.comparisons}
              projectId={projectId}
              onOpenBatch={(batchId) => setView({ batchId, type: 'record' })}
              onOpenTest={setSelectedTest}
              onCancel={(id) => drawer.cancelMutation.mutate(id)}
            />
          ) : null}
        </section>
      ) : null}
    </StageSurface>
  )
}
