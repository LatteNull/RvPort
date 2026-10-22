import type { PageResponse } from '@/types'
import type {
  AdminWorkerListParams,
  WorkerInstance,
  WorkerInstanceDetail,
  WorkerTask
} from '@/types/admin/workers'

import request from '../request'

export function getAdminWorkers(params: AdminWorkerListParams) {
  return request.get<PageResponse<WorkerInstance>>('/admin/workers', { params })
}

export function getAdminWorker(workerInstanceId: string) {
  return request.get<WorkerInstanceDetail>(`/admin/workers/${encodeURIComponent(workerInstanceId)}`)
}

export function cancelAdminWorkerTask(taskId: string) {
  return request.post<{ id: string; status: WorkerTask['status'] }>(
    `/tasks/${encodeURIComponent(taskId)}/cancel`
  )
}

export function updateAdminWorkerConcurrency(workerInstanceId: string, concurrencyLimit: number) {
  return request.put<WorkerInstance>(
    `/admin/workers/${encodeURIComponent(workerInstanceId)}/concurrency`,
    { concurrencyLimit }
  )
}
