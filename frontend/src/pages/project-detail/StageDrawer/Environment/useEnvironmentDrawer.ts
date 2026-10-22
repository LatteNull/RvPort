import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Form } from 'antd'

import {
  checkProjectEnvironment,
  createProjectEnvironment,
  getProjectEnvironments,
  getProjectEnvironmentScriptExecution,
  runProjectEnvironmentScript,
  testProjectEnvironmentConnection,
  testSavedProjectEnvironmentConnection,
  updateProjectEnvironment
} from '@/api/project/environments'
import { updateProjectRuntimeEnvironments } from '@/api/project/runtime-environments'
import { readAllPages } from '@/api/readAllPages'
import { useSubmissionSession } from '@/hooks/useSubmissionSession'
import type {
  ProjectEnvironment,
  ProjectEnvironmentScriptExecution,
  ProjectOverview
} from '@/types/project'
import { feedback } from '@/utils/feedback'

import { useProjectOverviewData } from '../../ProjectOverviewContext'
import { projectQueryKeys } from '../../queryKeys'
import {
  toEnvironmentConnectionRequest,
  toEnvironmentInput,
  toEnvironmentUpdateRequest
} from './environment-input'
import {
  createEnvironmentFormValues,
  type EnvironmentFormValues,
  type EnvironmentScriptFormValues,
  type EnvironmentView,
  initialEnvironmentFormValues,
  initialEnvironmentScriptFormValues
} from './model'

export function useEnvironmentDrawer(
  projectId: string | undefined,
  visible: boolean,
  onClose: () => void
) {
  const [form] = Form.useForm<EnvironmentFormValues>()
  const [scriptForm] = Form.useForm<EnvironmentScriptFormValues>()
  const [view, setView] = useState<EnvironmentView>({ type: 'list' })
  const session = useSubmissionSession(
    `${projectId}:${view.type}:${'environment' in view ? view.environment.id : ''}`,
    visible
  )
  // Row actions keep their submission scope when opening an editor or history view.
  const rowSubmission = useSubmissionSession(`environment-row:${projectId}`, visible)
  const [action, setAction] = useState<'save' | 'test' | 'script'>()
  const isSaving = session.busy && action === 'save'
  const isTestingConnection = session.busy && action === 'test'
  const isRunningScript = session.busy && action === 'script'
  const [isListReady, setIsListReady] = useState(false)
  const [hasPrecheckedConnection, setHasPrecheckedConnection] = useState(false)
  const [isEnvironmentFormDirty, setIsEnvironmentFormDirty] = useState(false)
  const [isScriptFormDirty, setIsScriptFormDirty] = useState(false)
  const [checkingEnvironmentId, setCheckingEnvironmentId] = useState<string | null>(null)
  const [settingRuntimeEnvironmentId, setSettingRuntimeEnvironmentId] = useState<string | null>(
    null
  )
  const queryClient = useQueryClient()
  const environmentQueryKey = projectQueryKeys.environments(projectId)
  const environmentOptionsQueryKey = projectQueryKeys.environmentOptions(projectId)
  const historyEnvironment = view.type === 'history' ? view.environment : null
  const logExecutionId = view.type === 'log' ? view.executionId : null
  const overviewQuery = useProjectOverviewData(projectId)
  const runtimeEnvironments = overviewQuery.data?.currentContext.runtimeEnvironments
  const {
    data: executionDetail,
    isLoading: isExecutionDetailLoading,
    isError: isExecutionDetailError,
    refetch: refetchExecutionDetail
  } = useQuery({
    queryKey: projectQueryKeys.environmentScriptExecution(logExecutionId ?? undefined),
    queryFn: () => getProjectEnvironmentScriptExecution(logExecutionId ?? ''),
    enabled: visible && Boolean(logExecutionId),
    gcTime: 0,
    refetchOnMount: 'always'
  })
  const { data: environmentOptions } = useQuery({
    queryKey: environmentOptionsQueryKey,
    queryFn: ({ signal }) =>
      readAllPages(
        (page, pageSize) =>
          getProjectEnvironments(projectId ?? '', {
            page,
            pageSize,
            role: 'JUMP_HOST',
            status: 'AVAILABLE'
          }),
        { signal }
      ),
    gcTime: 0,
    refetchOnMount: 'always',
    enabled: visible && Boolean(projectId) && (view.type === 'create' || view.type === 'edit')
  })
  const jumpHostOptions = (environmentOptions?.items ?? []).filter(
    (environment) => view.type !== 'edit' || environment.id !== view.environment.id
  )

  const resetToList = () => {
    form.resetFields()
    scriptForm.resetFields()
    setHasPrecheckedConnection(false)
    setIsEnvironmentFormDirty(false)
    setIsScriptFormDirty(false)
    setView({ type: 'list' })
  }
  const showList = () => {
    if (!session.isBusy()) resetToList()
  }
  const showCreate = () => {
    form.resetFields()
    form.setFieldsValue(initialEnvironmentFormValues)
    setHasPrecheckedConnection(false)
    setIsEnvironmentFormDirty(false)
    setView({ type: 'create' })
  }
  const showEdit = (environment: ProjectEnvironment) => {
    form.resetFields()
    form.setFieldsValue(createEnvironmentFormValues(environment))
    setHasPrecheckedConnection(false)
    setIsEnvironmentFormDirty(false)
    setView({ environment, type: 'edit' })
  }
  const showRunScript = (environment: ProjectEnvironment) => {
    scriptForm.resetFields()
    scriptForm.setFieldsValue({
      ...initialEnvironmentScriptFormValues,
      workdir: environment.workdir
    })
    setIsScriptFormDirty(false)
    setView({ environment, type: 'script' })
  }
  const showHistory = (environment: ProjectEnvironment) => setView({ environment, type: 'history' })
  const showLog = (execution: ProjectEnvironmentScriptExecution) => {
    if (historyEnvironment)
      setView({ environment: historyEnvironment, executionId: execution.id, type: 'log' })
  }
  const handleSave = async () => {
    await session.run(async (isCurrent) => {
      setAction('save')
      const values = await form.validateFields()
      if (!isCurrent()) return
      const environment =
        view.type === 'edit'
          ? await updateProjectEnvironment(view.environment.id, toEnvironmentUpdateRequest(values))
          : await createProjectEnvironment(projectId ?? '', toEnvironmentInput(values))
      if (!isCurrent()) return
      let verificationFailed = false
      if (hasPrecheckedConnection) {
        try {
          await testSavedProjectEnvironmentConnection(projectId ?? '', environment.id)
        } catch {
          verificationFailed = true
        }
        if (!isCurrent()) return
      }
      void queryClient.invalidateQueries({ queryKey: environmentQueryKey })
      if (verificationFailed)
        feedback.warning('环境已保存，但连接验证未能提交，请在环境列表中重新测试')
      else
        feedback.success(
          hasPrecheckedConnection
            ? '环境已保存，连接验证已提交'
            : view.type === 'create'
              ? '环境已创建'
              : '环境配置已保存'
        )
      resetToList()
    })
  }
  const handleCheck = (environment: ProjectEnvironment) =>
    rowSubmission.run(async (isCurrent) => {
      if (checkingEnvironmentId) return
      setCheckingEnvironmentId(environment.id)
      try {
        await checkProjectEnvironment(projectId ?? '', environment)
        if (isCurrent()) feedback.success('环境检查任务已提交')
      } finally {
        if (isCurrent()) setCheckingEnvironmentId(null)
      }
    })
  const handleTestConnection = async () => {
    await session.run(async (isCurrent) => {
      setAction('test')
      const values = await form.validateFields()
      if (!isCurrent()) return
      if (!values.username?.trim()) {
        form.setFields([{ name: 'username', errors: ['请输入登录用户名'] }])
        return
      }
      await testProjectEnvironmentConnection(
        projectId ?? '',
        toEnvironmentConnectionRequest(values, view.type === 'edit' ? view.environment : undefined)
      )
      if (!isCurrent()) return
      setHasPrecheckedConnection(true)
      feedback.success('连接预检已提交，保存后将验证该环境')
    })
  }
  const handleEnvironmentFormValuesChange = () => {
    setHasPrecheckedConnection(false)
    setIsEnvironmentFormDirty(true)
  }
  const handleScriptFormValuesChange = () => setIsScriptFormDirty(true)
  const syncRuntimeEnvironments = (
    updatedRuntimeEnvironments: NonNullable<typeof runtimeEnvironments>
  ) => {
    queryClient.setQueryData<ProjectOverview>(projectQueryKeys.overview(projectId), (current) =>
      current
        ? {
            ...current,
            currentContext: {
              ...current.currentContext,
              runtimeEnvironments: updatedRuntimeEnvironments
            }
          }
        : current
    )
  }
  const handleSetRuntimeEnvironment = (environment: ProjectEnvironment) =>
    rowSubmission.run(async (isCurrent) => {
      if (environment.role === 'JUMP_HOST') return

      if (settingRuntimeEnvironmentId) return
      setSettingRuntimeEnvironmentId(environment.id)
      try {
        const updatedRuntimeEnvironments = await updateProjectRuntimeEnvironments(
          projectId ?? '',
          environment.role === 'SOURCE'
            ? { sourceEnvironmentId: environment.id }
            : { targetEnvironmentId: environment.id }
        )
        if (!isCurrent()) return
        syncRuntimeEnvironments(updatedRuntimeEnvironments)
        feedback.success(environment.role === 'SOURCE' ? '当前源环境已更新' : '当前目标环境已更新')
      } finally {
        if (isCurrent()) setSettingRuntimeEnvironmentId(null)
      }
    })
  const handleRunScript = async () => {
    if (view.type !== 'script') return
    await session.run(async (isCurrent) => {
      setAction('script')
      const values = await scriptForm.validateFields()
      if (!isCurrent()) return
      const execution = await runProjectEnvironmentScript(
        projectId ?? '',
        view.environment.id,
        values
      )
      if (!isCurrent()) return
      feedback.success(
        values.scriptType === 'COLLECTION'
          ? '环境信息采集任务已提交'
          : values.scriptType === 'PRECHECK'
            ? '构建前检查任务已提交'
            : '自定义脚本任务已提交'
      )
      if (values.scriptType === 'CUSTOM')
        setView({ type: 'log', environment: view.environment, executionId: execution.id })
      else resetToList()
    })
  }
  const handleRefresh = async () => {
    if (view.type === 'list') {
      await queryClient.invalidateQueries({ queryKey: environmentQueryKey })
      return
    }
    if (view.type === 'history') {
      await queryClient.invalidateQueries({
        queryKey: projectQueryKeys.environmentScriptExecutions(projectId, view.environment.id)
      })
      return
    }
    if (view.type === 'log') {
      await refetchExecutionDetail()
    }
  }
  const handleAfterOpenChange = (open: boolean) => {
    if (open !== visible) return
    if (open) {
      setIsListReady(true)
      return
    }
    if (view.type === 'create' || view.type === 'edit') form.resetFields()
    if (view.type === 'script') scriptForm.resetFields()
    setCheckingEnvironmentId(null)
    setSettingRuntimeEnvironmentId(null)
    setHasPrecheckedConnection(false)
    setIsEnvironmentFormDirty(false)
    setIsScriptFormDirty(false)
    setIsListReady(false)
    setView({ type: 'list' })
  }
  const handleClose = () => {
    if (!session.isBusy()) onClose()
  }

  return {
    executionDetail,
    checkingEnvironmentId,
    form,
    handleAfterOpenChange,
    handleCheck,
    handleClose,
    handleEnvironmentFormValuesChange,
    handleScriptFormValuesChange,
    handleRefresh,
    handleRunScript,
    handleSave,
    handleTestConnection,
    isExecutionDetailLoading,
    isExecutionDetailError,
    isBusy: session.isBusy,
    busy: session.busy,
    isListReady,
    isRunningScript,
    isSaving,
    isTestingConnection,
    hasUnsavedChanges:
      view.type === 'create' || view.type === 'edit'
        ? isEnvironmentFormDirty
        : view.type === 'script'
          ? isScriptFormDirty
          : false,
    jumpHostOptions,
    runtimeEnvironments,
    scriptForm,
    showCreate,
    showEdit,
    showHistory,
    showList,
    showLog,
    showRunScript,
    handleSetRuntimeEnvironment,
    refetchExecutionDetail,
    settingRuntimeEnvironmentId,
    view
  }
}
