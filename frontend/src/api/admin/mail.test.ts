import { describe, expect, it, vi } from 'vitest'

const { request } = vi.hoisted(() => ({
  request: {
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
    put: vi.fn()
  }
}))

vi.mock('../request', () => ({
  default: request,
  LONG_RUNNING_REQUEST_TIMEOUT_MS: 3_600_000
}))

import { getMailSettings, testMailSettings, updateMailSettings } from '@/api/admin/mail'

describe('mail API contract', () => {
  it('uses documented mail-settings endpoints without reading a password value', () => {
    getMailSettings()
    updateMailSettings({
      connectionTimeoutMillis: 5000,
      enabled: true,
      frontendBaseUrl: null,
      fromAddress: 'noreply@example.com',
      host: 'smtp.example.com',
      password: 'smtp-secret',
      port: 465,
      readTimeoutMillis: 10000,
      ssl: true,
      startTls: false,
      testMode: false,
      username: 'noreply@example.com'
    })
    testMailSettings({ to: 'developer@example.com' })

    expect(request.get).toHaveBeenCalledWith('/admin/configs/mail')
    expect(request.patch).toHaveBeenCalledWith(
      '/admin/configs/mail',
      expect.objectContaining({
        password: 'smtp-secret'
      })
    )
    expect(request.post).toHaveBeenLastCalledWith('/admin/configs/mail:test', {
      to: 'developer@example.com'
    })
  })
})
