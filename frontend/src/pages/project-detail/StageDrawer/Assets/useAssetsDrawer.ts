import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Form } from 'antd'

import { updateProjectSourceFromGit, uploadProjectSourceArtifact } from '@/api/project/assets'
import { useSessionMutation } from '@/hooks/useSessionMutation'
import type {
  ProjectOverview,
  ProjectOverviewTask,
  UpdateProjectSourceFromGitRequest
} from '@/types/project'
import { feedback } from '@/utils/feedback'

import { useProjectOverviewData } from '../../ProjectOverviewContext'
import { projectQueryKeys } from '../../queryKeys'
import { useStageDraft } from '../components/useStageDraft'
import type { AssetsView, UploadValues } from './types'

export function useAssetsDrawer(
  projectId: string | undefined,
  visible: boolean,
  onDirtyChange?: (dirty: boolean) => void
) {
  const [view, setView] = useState<AssetsView>('upload')
  const [isEditingSource, setIsEditingSource] = useState(false)
  const [submittedSourceMode, setSubmittedSourceMode] = useState<{
    mode: AssetsView
    projectId: string
    task?: ProjectOverviewTask
  }>()
  const [uploadForm] = Form.useForm<UploadValues>()
  const [gitForm] = Form.useForm<UpdateProjectSourceFromGitRequest>()
  const queryClient = useQueryClient()
  const {
    data: overview,
    isError,
    isFetching,
    isLoading,
    refetch
  } = useProjectOverviewData(projectId)
  const artifact = overview?.currentContext.activeSourceRevision ?? undefined
  const configuredSourceMode =
    overview?.project.sourceInputType === 'ARCHIVE'
      ? 'upload'
      : overview?.project.sourceInputType === 'GIT'
        ? 'git'
        : undefined
  const persistedSourceMode =
    artifact?.type === 'ARCHIVE' ? 'upload' : artifact?.type === 'GIT' ? 'git' : undefined
  const lockedSourceMode =
    configuredSourceMode ??
    persistedSourceMode ??
    (submittedSourceMode?.projectId === projectId ? submittedSourceMode?.mode : undefined)
  const sourceMode = lockedSourceMode ?? view
  const submittedTask =
    submittedSourceMode?.projectId === projectId ? submittedSourceMode?.task : undefined
  const submittedTaskObserved = Boolean(
    submittedTask && overview?.recentTasks.some((task) => task.id === submittedTask.id)
  )
  if (submittedTaskObserved && submittedSourceMode) {
    setSubmittedSourceMode({ ...submittedSourceMode, task: undefined })
  }
  const sourceTasks = (overview?.recentTasks ?? []).filter(
    (task) => task.type === 'SOURCE_GIT_SYNC'
  )
  if (submittedTask && !sourceTasks.some((task) => task.id === submittedTask.id))
    sourceTasks.unshift(submittedTask)
  const sourceTask = sourceTasks.sort(
    (left, right) =>
      (Date.parse(right.createdAt ?? '') || 0) - (Date.parse(left.createdAt ?? '') || 0)
  )[0]
  const isImportPending = Boolean(
    sourceTask && ['PENDING', 'QUEUED', 'RUNNING'].includes(sourceTask.status)
  )
  const isEditing = !isImportPending && (isEditingSource || !artifact)
  const files = Form.useWatch('file', { form: uploadForm, preserve: true }) as
    UploadValues['file'] | undefined
  const gitValues = Form.useWatch([], { form: gitForm, preserve: true }) as
    Partial<UpdateProjectSourceFromGitRequest> | undefined
  useStageDraft(
    {
      files: files?.map((file) => file.uid) ?? [],
      repositoryUrl: gitValues?.repositoryUrl ?? '',
      ref: gitValues?.ref ?? '',
      username: gitValues?.username ?? '',
      accessToken: gitValues?.accessToken ?? ''
    },
    { files: [], repositoryUrl: '', ref: '', username: '', accessToken: '' },
    visible && isEditing,
    onDirtyChange
  )

  const setSourceMode = (mode: AssetsView) => {
    if (!lockedSourceMode) setView(mode)
  }
  const resetSourceInput = () => {
    uploadForm.resetFields()
    gitForm.resetFields()
    setView(lockedSourceMode ?? 'upload')
    setIsEditingSource(false)
  }
  const { isPending: isUploading, mutateAsync: handleUpload } = useSessionMutation({
    sessionKey: `upload-source:${projectId}`,
    active: visible && isEditing,
    mutationFn: (values: UploadValues) => {
      const file = values.file[0]?.originFileObj
      if (!file) throw new Error('请选择源码压缩包')
      return uploadProjectSourceArtifact(projectId ?? '', { file })
    },
    onSuccess: (uploadedArtifact) => {
      queryClient.setQueryData<ProjectOverview>(projectQueryKeys.overview(projectId), (current) =>
        current
          ? {
              ...current,
              currentContext: { ...current.currentContext, activeSourceRevision: uploadedArtifact }
            }
          : current
      )
      if (projectId) setSubmittedSourceMode({ mode: 'upload', projectId })
      resetSourceInput()
      feedback.success('当前源码已更新')
    }
  })
  const { isPending: isUpdatingGit, mutateAsync: handleGitUpdate } = useSessionMutation({
    sessionKey: `git-source:${projectId}`,
    active: visible && isEditing,
    mutationFn: (values: UpdateProjectSourceFromGitRequest) =>
      updateProjectSourceFromGit(projectId ?? '', {
        ...values,
        ref: values.ref.trim(),
        repositoryUrl: values.repositoryUrl.trim(),
        username: values.username?.trim() || undefined
      }),
    onSuccess: (task) => {
      if (projectId) setSubmittedSourceMode({ mode: 'git', projectId, task })
      setView('git')
      setIsEditingSource(false)
      gitForm.setFieldValue('accessToken', undefined)
      feedback.success('Git 更新任务已提交，请在后续阶段按需手动发起扫描')
    }
  })
  return {
    artifact,
    gitForm,
    handleGitUpdate,
    handleUpload,
    isError,
    isFetching,
    isLoading,
    isUpdatingGit,
    isUploading,
    isEditing,
    sourceTask,
    lockedSourceMode,
    refetch,
    setSourceMode,
    startSourceUpdate: () => setIsEditingSource(true),
    resetSourceInput,
    uploadForm,
    view: sourceMode
  }
}
