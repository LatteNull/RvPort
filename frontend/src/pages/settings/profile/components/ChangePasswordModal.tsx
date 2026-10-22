import { Fragment, useEffect } from 'react'
import { Alert, Button, Form, Input } from 'antd'

import BaseModal from '@/components/BaseModal'

const formId = 'profile-change-password-form'

export interface ProfileChangePasswordFormValues {
  confirmPassword: string
  currentPassword: string
  newPassword: string
}

interface ChangePasswordModalProps {
  passwordChanged?: boolean
  onRetryLogout?: () => Promise<void>
  loading: boolean
  username: string
  visible: boolean
  onCancel: () => void
  onSubmit: (values: ProfileChangePasswordFormValues) => Promise<void>
}

export default function ChangePasswordModal({
  loading,
  passwordChanged = false,
  onRetryLogout,
  username,
  visible,
  onCancel,
  onSubmit
}: ChangePasswordModalProps) {
  const [form] = Form.useForm<ProfileChangePasswordFormValues>()

  useEffect(() => {
    if (!visible) form.resetFields()
  }, [form, visible])

  async function handleSubmit(values: ProfileChangePasswordFormValues) {
    if (!loading) await onSubmit(values)
  }

  const footer = (
    <Fragment>
      <Button disabled={loading} onClick={onCancel}>
        取消
      </Button>
      {passwordChanged ? (
        <Button loading={loading} onClick={() => void onRetryLogout?.()} type="primary">
          重试退出登录
        </Button>
      ) : (
        <Button form={formId} htmlType="submit" disabled={loading} loading={loading} type="primary">
          确认修改
        </Button>
      )}
    </Fragment>
  )

  return (
    <BaseModal
      busy={loading}
      destroyOnHidden
      width={520}
      footer={footer}
      title={{ title: '修改密码' }}
      visible={visible}
      onCancel={onCancel}
    >
      {passwordChanged ? (
        <Alert type="warning" title="密码已修改，请退出后重新登录" />
      ) : (
        <Form<ProfileChangePasswordFormValues>
          disabled={loading}
          form={form}
          id={formId}
          layout="vertical"
          preserve={false}
          onFinish={handleSubmit}
        >
          <Form.Item
            label="当前密码"
            name="currentPassword"
            rules={[{ required: true, message: '请输入当前密码' }]}
          >
            <Input.Password autoComplete="current-password" placeholder="请输入当前密码" />
          </Form.Item>
          <Form.Item
            label="新密码"
            name="newPassword"
            rules={[
              { required: true, message: '请输入新密码' },
              {
                pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/,
                message: '新密码至少 8 位，且包含大写字母、小写字母和数字'
              },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || value !== getFieldValue('currentPassword')) return Promise.resolve()
                  return Promise.reject(new Error('新密码不能与当前密码相同'))
                }
              }),
              {
                validator(_, value) {
                  if (!value || value.toLowerCase() !== username.toLowerCase())
                    return Promise.resolve()
                  return Promise.reject(new Error('新密码不能与账号相同'))
                }
              }
            ]}
          >
            <Input.Password autoComplete="new-password" placeholder="请输入新密码" />
          </Form.Item>
          <Form.Item
            dependencies={['newPassword']}
            label="确认新密码"
            name="confirmPassword"
            rules={[
              { required: true, message: '请再次输入新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  return !value || getFieldValue('newPassword') === value
                    ? Promise.resolve()
                    : Promise.reject(new Error('两次输入的新密码不一致'))
                }
              })
            ]}
          >
            <Input.Password autoComplete="new-password" placeholder="请再次输入新密码" />
          </Form.Item>
        </Form>
      )}
    </BaseModal>
  )
}
