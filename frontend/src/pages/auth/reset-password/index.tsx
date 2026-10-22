import { useNavigate } from 'react-router'
import { Button, Form, Input } from 'antd'

import { confirmPasswordReset } from '@/api/auth'
import { useSensitiveQueryToken } from '@/hooks/useSensitiveQueryToken'
import { useSessionMutation } from '@/hooks/useSessionMutation'
import { feedback } from '@/utils/feedback'

import styles from '../auth.module.scss'

interface ResetPasswordFormValues {
  confirmPassword: string
  newPassword: string
}

export default function ResetPasswordPage() {
  const navigate = useNavigate()
  const token = useSensitiveQueryToken()
  const mutation = useSessionMutation({
    sessionKey: `reset-password:${token}`,
    active: Boolean(token),
    mutationFn: confirmPasswordReset,
    onSuccess() {
      feedback.success('密码已重置，请重新登录')
      navigate('/login', { replace: true })
    }
  })

  const handleSubmit = async (values: ResetPasswordFormValues) => {
    if (!token) return
    await mutation.mutateAsync({ token, newPassword: values.newPassword })
  }

  return (
    <main className={styles.container}>
      <section className={styles.card}>
        <h1 className={styles.title}>重置密码</h1>
        {token ? (
          <Form<ResetPasswordFormValues>
            disabled={mutation.isPending}
            layout="vertical"
            onFinish={handleSubmit}
          >
            <Form.Item
              label="新密码"
              name="newPassword"
              rules={[
                { required: true, message: '请输入新密码' },
                {
                  pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/,
                  message: '新密码至少 8 位，且包含大写字母、小写字母和数字'
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
            <Button block htmlType="submit" loading={mutation.isPending} type="primary">
              重置密码
            </Button>
          </Form>
        ) : (
          <div>
            <p className={styles.resultText}>重置链接无效或已过期，请重新申请。</p>
            <Button block type="primary" onClick={() => void navigate('/forgot-password')}>
              重新申请
            </Button>
          </div>
        )}
      </section>
    </main>
  )
}
