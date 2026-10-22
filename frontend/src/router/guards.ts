import { redirect } from 'react-router'
import { isAxiosError } from 'axios'

import { getAuthGeneration } from '@/store/authSession'
import { AuthRequiredError, useAuthStore } from '@/store/authStore'
import type { User } from '@/types'

const LOGIN_PATH = '/login'
const HOME_PATH = '/home'
const FORCE_CHANGE_PASSWORD_PATH = '/force-change-password'

type UserRedirectResolver = (user: User) => string | null

// 会话失效在此统一清理，访客路由可据此放行，受保护路由则跳转登录页。
async function getSessionUser() {
  const generation = getAuthGeneration()
  try {
    return await useAuthStore.getState().ensureSession()
  } catch (error) {
    if (generation !== getAuthGeneration()) return useAuthStore.getState().user
    if (
      !(error instanceof AuthRequiredError) &&
      !(isAxiosError(error) && error.response?.status === 401)
    )
      throw error
    useAuthStore.getState().logout()
    return null
  }
}

// 所有受保护路由共用会话校验，按路由追加各自的重定向规则。
async function requireUser(redirectResolver?: UserRedirectResolver) {
  const user = await getSessionUser()
  if (!user) {
    throw redirect(LOGIN_PATH)
  }

  const redirectPath = redirectResolver?.(user)
  if (redirectPath) {
    throw redirect(redirectPath)
  }

  return null
}

// 强制改密优先于业务和角色权限，避免用户绕过密码更新流程。
function redirectWhenPasswordChangeRequired(user: User) {
  return user.mustChangePassword ? FORCE_CHANGE_PASSWORD_PATH : null
}

export async function requireAuth() {
  return requireUser()
}

export async function requireFullAccess() {
  return requireUser(redirectWhenPasswordChangeRequired)
}

export async function requireAdmin() {
  return requireUser(
    (user) => redirectWhenPasswordChangeRequired(user) ?? (user.isSuperAdmin ? null : '/403')
  )
}

export async function requireGuest() {
  const user = await getSessionUser()
  if (!user) {
    return null
  }
  throw redirect(user.mustChangePassword ? FORCE_CHANGE_PASSWORD_PATH : HOME_PATH)
}

export async function requirePasswordChange() {
  return requireUser((user) => (user.mustChangePassword ? null : HOME_PATH))
}
