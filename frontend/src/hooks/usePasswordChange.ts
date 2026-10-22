import { useState } from 'react'

import { changePassword, logout as logoutApi } from '@/api/auth'
import { useAuthStore } from '@/store'
import { feedback } from '@/utils/feedback'

import { useSubmissionSession } from './useSubmissionSession'

export function usePasswordChange(onLoggedOut: () => void, active = true) {
  const userId = useAuthStore((state) => state.user?.id)
  const session = useSubmissionSession(userId ?? 'password', active)
  const [changedFor, setChangedFor] = useState<string>()
  const passwordChanged = Boolean(userId && changedFor === userId)
  const submit = async (values?: Parameters<typeof changePassword>[0]) => {
    await session.run(async (isCurrent) => {
      if (!passwordChanged) {
        if (!values) return
        await changePassword(values)
        if (!isCurrent()) return
        setChangedFor(userId)
      }
      try {
        const { loggedOut } = await logoutApi()
        if (!isCurrent()) return
        if (!loggedOut) throw new Error('退出登录失败')
      } catch {
        if (isCurrent()) feedback.warning('密码已修改，但退出登录失败，请重试退出登录')
        return
      }
      useAuthStore.getState().logout()
      feedback.success('密码已修改，请重新登录')
      onLoggedOut()
    })
  }
  return { loading: session.busy, passwordChanged, submit }
}
