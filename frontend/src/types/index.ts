export interface User {
  id: string
  username: string
  displayName: string | null
  email: string | null
  isSuperAdmin: boolean
  mustChangePassword: boolean
  status: 'ACTIVE' | 'DISABLED'
  lastLoginAt: string | null
  createdAt: string
  updatedAt: string | null
}

export interface ApiSuccessResponse<T = unknown> {
  success?: true
  data: T
  traceId: string
  timestamp: string
}

export interface ApiErrorResponse {
  success?: false
  error?: {
    code: string
    message: string
    details?: unknown
  }
  code?: string
  message?: string
  details?: unknown
  traceId: string
  timestamp: string
}

export type ApiResponse<T = unknown> = ApiSuccessResponse<T>

export interface PageParams {
  page: number
  pageSize: number
}

export interface PageResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  hasMore: boolean
}
