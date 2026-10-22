import { act, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'

const { getMailSettings, testMailSettings, updateMailSettings } = vi.hoisted(() => ({
  getMailSettings: vi.fn(),
  testMailSettings: vi.fn(),
  updateMailSettings: vi.fn()
}))

vi.mock('@/api/admin/mail', () => ({ getMailSettings, testMailSettings, updateMailSettings }))

import AdminMailPage from '.'

describe('admin mail page', () => {
  it('shows only the configured-password state and leaves the password input empty', async () => {
    getMailSettings.mockResolvedValue({
      connectionTimeoutMillis: 5000,
      enabled: true,
      frontendBaseUrl: 'https://rvport.example.com',
      fromAddress: 'noreply@example.com',
      host: 'smtp.example.com',
      passwordConfigured: true,
      port: 465,
      readTimeoutMillis: 10000,
      ssl: true,
      startTls: false,
      testMode: false,
      username: 'noreply@example.com'
    })
    const userEventInstance = userEvent.setup()

    renderWithQueryClient(<AdminMailPage />)

    expect(await screen.findByText('已配置')).toBeInTheDocument()
    await userEventInstance.click(screen.getByRole('button', { name: '编辑配置' }))

    expect(screen.getByLabelText('SMTP 密码 / 授权码')).toHaveValue('')
  })
  it('recovers from initial failure through retry', async () => {
    getMailSettings.mockRejectedValueOnce(new Error('offline')).mockResolvedValue(settings)
    const user = userEvent.setup()
    renderWithQueryClient(<AdminMailPage />)
    expect(await screen.findByText('邮箱配置加载失败')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /重\s*试/ }))
    expect(await screen.findByRole('button', { name: '编辑配置' })).toBeInTheDocument()
  })

  it.each(['success', 'failure'])(
    'preserves all editing drafts across background refresh %s',
    async (outcome) => {
      getMailSettings.mockResolvedValue(settings)
      const user = userEvent.setup()
      const { queryClient } = renderWithQueryClient(<AdminMailPage />)
      await user.click(await screen.findByRole('button', { name: '编辑配置' }))
      await user.clear(screen.getByLabelText('SMTP 主机'))
      await user.type(screen.getByLabelText('SMTP 主机'), 'draft-host')
      await user.type(screen.getByLabelText('SMTP 密码 / 授权码'), 'draft-secret')
      if (outcome === 'failure') getMailSettings.mockRejectedValue(new Error('offline'))
      else getMailSettings.mockResolvedValue({ ...settings, host: 'refreshed-host' })
      await act(async () => {
        await queryClient.invalidateQueries({ queryKey: ['admin-mail-settings'] })
      })
      expect(screen.getByLabelText('SMTP 主机')).toHaveValue('draft-host')
      expect(screen.getByLabelText('SMTP 密码 / 授权码')).toHaveValue('draft-secret')
      if (outcome === 'failure')
        expect(await screen.findByText('邮箱配置刷新失败，当前内容已保留')).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: /取\s*消/ }))
      await user.click(screen.getByRole('button', { name: '编辑配置' }))
      expect(screen.getByLabelText('SMTP 密码 / 授权码')).toHaveValue('')
      expect(screen.getByLabelText('SMTP 主机')).toHaveValue(
        outcome === 'success' ? 'refreshed-host' : settings.host
      )
    }
  )
})

const settings = {
  connectionTimeoutMillis: 5000,
  enabled: true,
  frontendBaseUrl: null,
  fromAddress: 'test@example.com',
  host: 'saved-host',
  passwordConfigured: true,
  port: 465,
  readTimeoutMillis: 10000,
  ssl: true,
  startTls: false,
  testMode: false,
  username: 'saved-user'
}
