import type {
  MailSendResult,
  MailSettings,
  TestMailSettingsPayload,
  UpdateMailSettingsPayload
} from '@/types/admin/mail'

import request from '../request'

export function getMailSettings() {
  return request.get<MailSettings>('/admin/configs/mail')
}

export function updateMailSettings(data: UpdateMailSettingsPayload) {
  return request.patch<MailSettings>('/admin/configs/mail', data)
}

export function testMailSettings(data: TestMailSettingsPayload) {
  return request.post<MailSendResult>('/admin/configs/mail:test', data)
}
