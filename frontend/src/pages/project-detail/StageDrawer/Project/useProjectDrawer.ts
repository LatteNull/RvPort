import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Form } from 'antd'

import {
  type BackendProject,
  getProject,
  updateProject,
  type UpdateProjectRequest
} from '@/api/project/projects'
import { useSubmissionSession } from '@/hooks/useSubmissionSession'
import { feedback } from '@/utils/feedback'

import { projectQueryKeys } from '../../queryKeys'

export type ProjectFormValues = Pick<UpdateProjectRequest, 'description'>

export function useProjectDrawer(projectId: string | undefined, visible: boolean) {
  const [form] = Form.useForm<ProjectFormValues>()
  const [isDescriptionEditing, setIsDescriptionEditing] = useState(false)
  const queryClient = useQueryClient()
  const queryKey = projectQueryKeys.detail(projectId)
  const {
    data: detail,
    isError,
    isLoading
  } = useQuery({
    queryKey,
    queryFn: () => getProject(projectId ?? ''),
    enabled: visible && Boolean(projectId)
  })
  const submission = useSubmissionSession(`project-description:${projectId}`, visible)
  const handleSave = () =>
    submission.run(async (isCurrent) => {
      const values = await form.validateFields(['description'])
      if (!isCurrent()) return
      const updatedProject = await updateProject(projectId ?? '', {
        description: values.description
      })
      if (!isCurrent()) return
      queryClient.setQueryData<BackendProject>(queryKey, updatedProject)
      form.setFields([
        { name: 'description', touched: false, value: updatedProject.description ?? '' }
      ])
      setIsDescriptionEditing(false)
      feedback.success('项目描述已保存')
    })
  const handleCancelDescriptionEdit = () => {
    form.setFields([{ name: 'description', touched: false, value: detail?.description ?? '' }])
    setIsDescriptionEditing(false)
  }
  return {
    detail,
    handleCancelDescriptionEdit,
    handleSave,
    isDescriptionEditing,
    isError,
    isLoading,
    isSaving: submission.busy,
    form,
    resetAfterClose: handleCancelDescriptionEdit,
    setIsDescriptionEditing
  }
}
