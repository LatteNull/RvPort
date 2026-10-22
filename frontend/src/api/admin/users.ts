import type { PageResponse, User } from '@/types'
import type {
  AdminUserListParams,
  CreateAdminUserPayload,
  ResetAdminUserPasswordPayload,
  UpdateAdminUserPayload
} from '@/types/admin/users'

import request from '../request'

export function getAdminUsers(params: AdminUserListParams) {
  return request.get<PageResponse<User>>('/admin/users', { params })
}

export function createAdminUser(data: CreateAdminUserPayload) {
  return request.post<User>('/admin/users', data)
}

export function updateAdminUser(userId: string, data: UpdateAdminUserPayload) {
  return request.patch<User>(`/admin/users/${userId}`, data)
}

export function sendAdminUserInvitation(userId: string) {
  return request.post<User>(`/admin/users/${userId}/send-invitation`)
}

export function resetAdminUserPassword(userId: string, data: ResetAdminUserPasswordPayload) {
  return request.post<User>(`/admin/users/${userId}/reset-password`, data)
}
