import type { AxiosError, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios'
import axios from 'axios'

import { useAuthStore } from '@/store'
import {
  getAuthGeneration,
  isAuthGenerationCurrent,
  SessionChangedError,
  subscribeAuthSession
} from '@/store/authSession'
import type { ApiErrorResponse, ApiResponse } from '@/types'
import { feedback } from '@/utils/feedback'

interface CsrfTokenResponse {
  headerName: string
  parameterName: string
  token: string
}

interface RequestConfig extends AxiosRequestConfig {
  authGeneration?: number
  skipCsrf?: boolean
  suppressAuthRedirect?: boolean
  suppressErrorToast?: boolean
}

const UNSAFE_METHODS = new Set(['post', 'put', 'patch', 'delete'])

export const DEFAULT_REQUEST_TIMEOUT_MS = 30_000
export const UPLOAD_REQUEST_TIMEOUT_MS = 300_000
export const LONG_RUNNING_REQUEST_TIMEOUT_MS = 3_600_000

export const requestClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api',
  timeout: DEFAULT_REQUEST_TIMEOUT_MS,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' }
})

let csrfToken: CsrfTokenResponse | null = null
let csrfTokenPromise: Promise<CsrfTokenResponse> | null = null

subscribeAuthSession(() => {
  csrfToken = null
  csrfTokenPromise = null
})

function shouldAttachCsrf(config: InternalAxiosRequestConfig) {
  const requestConfig = config as InternalAxiosRequestConfig & RequestConfig
  const method = (config.method ?? 'get').toLowerCase()
  return !requestConfig.skipCsrf && UNSAFE_METHODS.has(method)
}

async function getCsrfToken() {
  if (csrfToken) return csrfToken
  if (csrfTokenPromise) return csrfTokenPromise

  const generation = getAuthGeneration()
  const pending = requestClient
    .get<unknown, CsrfTokenResponse>('/auth/csrf', { skipCsrf: true } as RequestConfig)
    .then((token) => {
      if (!isAuthGenerationCurrent(generation)) throw new SessionChangedError()
      csrfToken = token
      return token
    })
    .finally(() => {
      if (csrfTokenPromise === pending) csrfTokenPromise = null
    })

  csrfTokenPromise = pending
  return pending
}

function setHeader(config: InternalAxiosRequestConfig, name: string, value: string) {
  if (typeof config.headers.set === 'function') {
    config.headers.set(name, value)
  } else {
    config.headers[name] = value
  }
}

requestClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const ownedConfig = config as InternalAxiosRequestConfig & RequestConfig
  ownedConfig.authGeneration ??= getAuthGeneration()
  if (!isAuthGenerationCurrent(ownedConfig.authGeneration)) throw new SessionChangedError()
  if (shouldAttachCsrf(config)) {
    const token = await getCsrfToken()
    if (!isAuthGenerationCurrent(ownedConfig.authGeneration)) throw new SessionChangedError()
    setHeader(config, token.headerName, token.token)
  }
  return config
})

requestClient.interceptors.response.use(
  (response) => {
    const generation = (response.config as RequestConfig).authGeneration
    if (generation !== undefined && !isAuthGenerationCurrent(generation))
      throw new SessionChangedError()
    const res = response.data as ApiResponse
    return res.data as never
  },
  async (error: AxiosError<ApiErrorResponse>) => {
    if (axios.isCancel(error)) return Promise.reject(error)
    const status = error.response?.status
    const responseData = error.response?.data
    const requestConfig = (error.config ?? {}) as RequestConfig
    if (
      error instanceof SessionChangedError ||
      (requestConfig.authGeneration !== undefined &&
        !isAuthGenerationCurrent(requestConfig.authGeneration))
    ) {
      return Promise.reject(new SessionChangedError())
    }
    const message = responseData?.error?.message ?? responseData?.message ?? error.message

    if (status === 401) {
      useAuthStore.getState().logout()
      if (!requestConfig.suppressErrorToast) {
        feedback.error(message || '登录已失效，请重新登录')
      }
      if (!requestConfig.suppressAuthRedirect && window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    } else if (status === 403) {
      const errorCode = responseData?.error?.code ?? responseData?.code
      if (errorCode === 'PASSWORD_CHANGE_REQUIRED') {
        if (window.location.pathname !== '/force-change-password') {
          window.location.href = '/force-change-password'
        }
        return Promise.reject(error)
      }
      if (!requestConfig.suppressErrorToast) feedback.error(message || '没有权限执行此操作')
    } else {
      if (!requestConfig.suppressErrorToast) {
        feedback.error(message || '网络异常，请稍后重试')
      }
    }
    return Promise.reject(error)
  }
)

const request = {
  get<T>(url: string, config?: RequestConfig) {
    return requestClient.get<unknown, T>(url, {
      ...config,
      authGeneration: getAuthGeneration()
    } as RequestConfig)
  },
  post<T>(url: string, data?: unknown, config?: RequestConfig) {
    return requestClient.post<unknown, T>(url, data, {
      ...config,
      authGeneration: getAuthGeneration()
    } as RequestConfig)
  },
  put<T>(url: string, data?: unknown, config?: RequestConfig) {
    return requestClient.put<unknown, T>(url, data, {
      ...config,
      authGeneration: getAuthGeneration()
    } as RequestConfig)
  },
  patch<T>(url: string, data?: unknown, config?: RequestConfig) {
    return requestClient.patch<unknown, T>(url, data, {
      ...config,
      authGeneration: getAuthGeneration()
    } as RequestConfig)
  },
  delete<T>(url: string, config?: RequestConfig) {
    return requestClient.delete<unknown, T>(url, {
      ...config,
      authGeneration: getAuthGeneration()
    } as RequestConfig)
  }
}

export function resetRequestClientForTests() {
  csrfToken = null
  csrfTokenPromise = null
}

export default request
