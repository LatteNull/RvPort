import type { ProjectTask } from '@/types/project/task'

import request from '../request'
export function cancelProjectTask(taskId: string) {
  return request.post<ProjectTask>(`/tasks/${encodeURIComponent(taskId)}/cancel`)
}
