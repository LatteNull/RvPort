import type { User } from '@/types'

export interface AdminUserListParams {
  keyword?: string
  page: number
  pageSize: number
  status?: User['status']
}

export interface CreateAdminUserPayload {
  displayName?: string
  email: string
  status?: User['status']
  username: string
}

export interface UpdateAdminUserPayload {
  displayName?: string | null
  email?: string
  status?: User['status']
}

export interface ResetAdminUserPasswordPayload {
  mustChangePassword?: boolean
  newPassword: string
}
