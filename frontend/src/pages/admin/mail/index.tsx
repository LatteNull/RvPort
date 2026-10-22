import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Flex, Form, Input, InputNumber, Radio, Skeleton, Switch } from 'antd'

import { getMailSettings, testMailSettings, updateMailSettings } from '@/api/admin/mail'
import { useSessionMutation } from '@/hooks/useSessionMutation'
import type { MailSettings, UpdateMailSettingsPayload } from '@/types/admin/mail'
import { feedback } from '@/utils/feedback'

import { adminQueryKeys } from '../queryKeys'
import TestMailModal from './components/TestMailModal'

import styles from './index.module.scss'

interface MailFormValues {
  connectionTimeoutMillis?: number
  enabled: boolean
  fromAddress?: string
  frontendBaseUrl?: string
  host?: string
  password?: string
  port?: number
  readTimeoutMillis?: number
  security: 'none' | 'ssl' | 'startTls'
  testMode: boolean
  username?: string
}

const mailSettingsQueryKey = adminQueryKeys.mailSettings()

function getSecurity(settings: MailSettings): MailFormValues['security'] {
  if (settings.ssl) return 'ssl'
  if (settings.startTls) return 'startTls'
  return 'none'
}

function getSettingsPayload(
  settings: MailSettings,
  values: MailFormValues
): UpdateMailSettingsPayload {
  return {
    connectionTimeoutMillis: values.connectionTimeoutMillis ?? settings.connectionTimeoutMillis,
    enabled: values.enabled,
    frontendBaseUrl: values.frontendBaseUrl?.trim() || null,
    fromAddress: values.fromAddress?.trim() || null,
    host: values.host?.trim() || null,
    password: values.password || undefined,
    port: values.port ?? null,
    readTimeoutMillis: values.readTimeoutMillis ?? settings.readTimeoutMillis,
    ssl: values.security === 'ssl',
    startTls: values.security === 'startTls',
    testMode: values.testMode,
    username: values.username?.trim() || null
  }
}

function getDisplayValue(value: string | number | null | undefined) {
  return value === null || value === undefined || value === '' ? '--' : value
}

function getFormValues(settings: MailSettings): MailFormValues {
  return {
    connectionTimeoutMillis: settings.connectionTimeoutMillis,
    enabled: settings.enabled,
    fromAddress: settings.fromAddress ?? undefined,
    frontendBaseUrl: settings.frontendBaseUrl ?? undefined,
    host: settings.host ?? undefined,
    password: undefined,
    port: settings.port ?? undefined,
    readTimeoutMillis: settings.readTimeoutMillis,
    security: getSecurity(settings),
    testMode: settings.testMode,
    username: settings.username ?? undefined
  }
}

function requiredWhenRealMailEnabled(message: string) {
  return ({ getFieldValue }: { getFieldValue: (name: keyof MailFormValues) => unknown }) => ({
    validator(_: unknown, value: unknown) {
      if (
        !getFieldValue('enabled') ||
        getFieldValue('testMode') ||
        (typeof value === 'number' ? true : Boolean(value?.toString().trim()))
      ) {
        return Promise.resolve()
      }
      return Promise.reject(new Error(message))
    }
  })
}

export default function AdminMailPage() {
  const [form] = Form.useForm<MailFormValues>()
  const [isEditing, setIsEditing] = useState(false)
  const [testMailVisible, setTestMailVisible] = useState(false)
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: mailSettingsQueryKey, queryFn: getMailSettings })

  const saveMutation = useSessionMutation({
    sessionKey: 'mail-settings',
    active: isEditing,
    mutationFn: updateMailSettings,
    onSuccess: async (settings) => {
      queryClient.setQueryData(mailSettingsQueryKey, settings)
      form.setFieldsValue(getFormValues(settings))
      setIsEditing(false)
      feedback.success('邮箱配置已保存')
    }
  })

  const testMutation = useSessionMutation({
    sessionKey: 'test-mail',
    active: testMailVisible,
    mutationFn: testMailSettings,
    onSuccess: (result) => {
      if (result.success) {
        feedback.success(result.message)
        setTestMailVisible(false)
        return
      }
      feedback.error(result.message)
    }
  })

  function handleCancelEdit() {
    if (saveMutation.isPending) return
    if (query.data) {
      form.setFieldsValue(getFormValues(query.data))
    }
    setIsEditing(false)
  }

  async function handleSubmit(values: MailFormValues) {
    if (!query.data) return
    await saveMutation.mutateAsync(getSettingsPayload(query.data, values))
  }

  return (
    <section className={styles.page}>
      <Flex align="flex-start" className={styles.pageHeader} justify="space-between" gap={24}>
        <div>
          <h1 className={styles.title}>邮箱配置</h1>
          <p className={styles.description}>配置系统邮件服务，用于发送邀请、密码重置和任务通知。</p>
        </div>
        {!isEditing && query.data && (
          <Flex align="center" className={styles.headerActions} gap={16}>
            <span className={query.data.enabled ? styles.enabledStatus : styles.disabledStatus}>
              {query.data.enabled
                ? query.data.testMode
                  ? '邮件服务已启用（测试模式）'
                  : '邮件服务已启用'
                : '邮件服务未启用'}
            </span>
            <Button onClick={() => setTestMailVisible(true)}>发送测试邮件</Button>
            <Button
              type="primary"
              onClick={() => {
                form.setFieldsValue(getFormValues(query.data!))
                setIsEditing(true)
              }}
            >
              编辑配置
            </Button>
          </Flex>
        )}
      </Flex>

      {query.isError ? (
        <Alert
          type="error"
          showIcon
          title={query.data ? '邮箱配置刷新失败，当前内容已保留' : '邮箱配置加载失败'}
          action={
            <Button type="primary" onClick={() => void query.refetch()}>
              重试
            </Button>
          }
        />
      ) : null}
      {query.isLoading ? (
        <Skeleton active paragraph={{ rows: 8 }} />
      ) : isEditing && query.data ? (
        <Form<MailFormValues>
          className={styles.editForm}
          disabled={saveMutation.isPending}
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <section className={styles.formSection}>
            <h2>服务状态</h2>
            <Flex align="flex-start" className={styles.serviceControls} gap={40} wrap>
              <Form.Item
                className={styles.serviceControl}
                label="启用邮件服务"
                name="enabled"
                valuePropName="checked"
              >
                <Switch checkedChildren="已启用" unCheckedChildren="未启用" />
              </Form.Item>
              <Form.Item
                className={styles.serviceControl}
                extra="开启后仅记录测试日志，不会向收件人实际投递邮件。"
                label="测试模式"
                name="testMode"
                valuePropName="checked"
              >
                <Switch checkedChildren="已开启" unCheckedChildren="真实发送" />
              </Form.Item>
            </Flex>
          </section>

          <section className={styles.formSection}>
            <h2>SMTP 连接</h2>
            <div className={styles.formGrid}>
              <Form.Item
                dependencies={['enabled', 'testMode']}
                label="SMTP 主机"
                name="host"
                rules={[requiredWhenRealMailEnabled('请输入 SMTP 主机')]}
              >
                <Input placeholder="smtp.example.com" />
              </Form.Item>
              <Form.Item
                dependencies={['enabled', 'testMode']}
                label="端口"
                name="port"
                rules={[requiredWhenRealMailEnabled('请输入端口')]}
              >
                <InputNumber className={styles.portInput} min={1} max={65535} placeholder="465" />
              </Form.Item>
              <Form.Item label="用户名" name="username">
                <Input placeholder="noreply@example.com" />
              </Form.Item>
              <Form.Item
                extra={
                  query.data.passwordConfigured ? '已配置 SMTP 凭据，留空则保持不变。' : undefined
                }
                label="SMTP 密码 / 授权码"
                name="password"
              >
                <Input.Password autoComplete="new-password" placeholder="请输入 SMTP 密码" />
              </Form.Item>
            </div>
          </section>

          <section className={styles.formSection}>
            <h2>发件设置</h2>
            <div className={styles.formGrid}>
              <Form.Item
                dependencies={['enabled', 'testMode']}
                label="发件人地址"
                name="fromAddress"
                rules={[
                  requiredWhenRealMailEnabled('请输入发件人地址'),
                  { type: 'email', message: '请输入有效的邮箱地址' }
                ]}
              >
                <Input placeholder="noreply@example.com" />
              </Form.Item>
              <Form.Item label="加密方式" name="security">
                <Radio.Group>
                  <Radio value="startTls">STARTTLS</Radio>
                  <Radio value="ssl">SSL</Radio>
                  <Radio value="none">不加密</Radio>
                </Radio.Group>
              </Form.Item>
            </div>
          </section>

          <section className={styles.formSection}>
            <h2>高级设置</h2>
            <div className={styles.formGrid}>
              <Form.Item label="连接超时（毫秒）" name="connectionTimeoutMillis">
                <InputNumber className={styles.portInput} min={100} max={120000} />
              </Form.Item>
              <Form.Item label="读取超时（毫秒）" name="readTimeoutMillis">
                <InputNumber className={styles.portInput} min={100} max={120000} />
              </Form.Item>
              <Form.Item label="前端地址" name="frontendBaseUrl">
                <Input placeholder="https://rvport.example.com" />
              </Form.Item>
            </div>
          </section>

          <Flex className={styles.formActions} justify="flex-end" gap={12}>
            <Button disabled={saveMutation.isPending} onClick={handleCancelEdit}>
              取消
            </Button>
            <Button htmlType="submit" loading={saveMutation.isPending} type="primary">
              保存配置
            </Button>
          </Flex>
        </Form>
      ) : (
        query.data && <MailSettingsView settings={query.data} />
      )}

      <TestMailModal
        loading={testMutation.isPending}
        visible={testMailVisible}
        onCancel={() => setTestMailVisible(false)}
        onSubmit={async (values) => {
          await testMutation.mutateAsync(values)
        }}
      />
    </section>
  )
}

function MailSettingsView({ settings }: { settings: MailSettings }) {
  return (
    <div className={styles.settingsGrid}>
      <section className={styles.settingsSection}>
        <h2>SMTP 连接</h2>
        <SettingItem label="SMTP 主机" value={getDisplayValue(settings.host)} />
        <SettingItem label="端口" value={getDisplayValue(settings.port)} />
        <SettingItem label="用户名" value={getDisplayValue(settings.username)} />
        <SettingItem label="SMTP 凭据" value={settings.passwordConfigured ? '已配置' : '未配置'} />
        <SettingItem label="连接超时" value={`${settings.connectionTimeoutMillis} ms`} />
        <SettingItem label="读取超时" value={`${settings.readTimeoutMillis} ms`} />
      </section>
      <section className={styles.settingsSection}>
        <h2>发件设置</h2>
        <SettingItem label="发件人地址" value={getDisplayValue(settings.fromAddress)} />
        <SettingItem
          label="运行模式"
          value={settings.testMode ? '测试模式（仅记录日志）' : '真实发送'}
        />
        <SettingItem
          label="加密方式"
          value={settings.ssl ? 'SSL' : settings.startTls ? 'STARTTLS' : '不加密'}
        />
        <SettingItem label="前端地址" value={getDisplayValue(settings.frontendBaseUrl)} />
      </section>
    </div>
  )
}

function SettingItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div className={styles.settingItem}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}
