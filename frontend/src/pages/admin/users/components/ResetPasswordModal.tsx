import { Fragment, useEffect } from 'react'
import { Button, Form, Input, Popconfirm } from 'antd'

import BaseModal from '@/components/BaseModal'
import { useSubmissionSession } from '@/hooks/useSubmissionSession'
import type { User } from '@/types'

interface ResetPasswordFormValues {
  confirmPassword: string
  newPassword: string
}

interface ResetPasswordModalProps {
  loading: boolean
  user: User | null
  visible: boolean
  onCancel: () => void
  onSubmit: (values: Pick<ResetPasswordFormValues, 'newPassword'>) => Promise<void>
}

export default function ResetPasswordModal({
  loading,
  user,
  visible,
  onCancel,
  onSubmit
}: ResetPasswordModalProps) {
  const [form] = Form.useForm<ResetPasswordFormValues>()

  const submission = useSubmissionSession(`reset-password:${user?.id}`, visible && Boolean(user))
  const busy = loading || submission.busy

  useEffect(() => {
    if (!visible) return
    form.resetFields()
  }, [form, visible, user?.id])

  async function handleSubmit() {
    if (loading) return
    await submission.run(async (isCurrent) => {
      const values = await form.validateFields()
      if (isCurrent()) await onSubmit({ newPassword: values.newPassword })
    })
  }

  return (
    <BaseModal
      busy={busy}
      destroyOnHidden
      footer={
        <Fragment>
          <Button disabled={busy} onClick={onCancel}>
            取消
          </Button>
          <Popconfirm
            disabled={busy}
            cancelText="取消"
            description="新密码将立即生效，当前会话不受影响。"
            okText="确认重置"
            title={`确认重置「${user?.username ?? ''}」的密码？`}
            onConfirm={handleSubmit}
          >
            <Button disabled={busy} loading={busy} type="primary">
              重置密码
            </Button>
          </Popconfirm>
        </Fragment>
      }
      title={{ title: '重置密码', subTitle: '请设置用户的新临时密码。' }}
      visible={visible}
      onCancel={onCancel}
    >
      <Form disabled={busy} form={form} layout="vertical" preserve={false}>
        <Form.Item
          label="新密码"
          name="newPassword"
          rules={[
            { required: true, message: '请输入新密码' },
            {
              pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/,
              message: '新密码至少 8 位，且包含大写字母、小写字母和数字'
            },
            {
              validator(_, value) {
                if (!value || value.trim()) return Promise.resolve()
                return Promise.reject(new Error('新密码不能只包含空白字符'))
              }
            },
            {
              validator(_, value) {
                if (!value || !user || value.toLowerCase() !== user.username.toLowerCase()) {
                  return Promise.resolve()
                }
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
    </BaseModal>
  )
}
