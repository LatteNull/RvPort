export interface MailSettings {
  connectionTimeoutMillis: number
  enabled: boolean
  frontendBaseUrl: string | null
  host: string | null
  passwordConfigured: boolean
  port: number | null
  readTimeoutMillis: number
  username: string | null
  fromAddress: string | null
  startTls: boolean
  ssl: boolean
  testMode: boolean
}

export type UpdateMailSettingsPayload = Omit<MailSettings, 'passwordConfigured'> & {
  password?: string
}

export interface TestMailSettingsPayload {
  settings?: Partial<UpdateMailSettingsPayload>
  to: string
}

export interface MailSendResult {
  message: string
  success: boolean
}
