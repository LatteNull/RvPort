import { useNavigate } from 'react-router'
import { Button, Form, Input } from 'antd'

import { acceptInvitation } from '@/api/auth'
import { useSensitiveQueryToken } from '@/hooks/useSensitiveQueryToken'
import { useSessionMutation } from '@/hooks/useSessionMutation'
import { feedback } from '@/utils/feedback'

import styles from '../auth.module.scss'

interface AcceptInvitationFormValues {
  confirmPassword: string
  newPassword: string
}

export default function AcceptInvitationPage() {
  const navigate = useNavigate()
  const token = useSensitiveQueryToken()
  const mutation = useSessionMutation({
    sessionKey: `invitation:${token}`,
    active: Boolean(token),
    mutationFn: acceptInvitation,
    onSuccess() {
      feedback.success('账号已激活，请使用新密码登录')
      navigate('/login', { replace: true })
    }
  })

  async function handleSubmit(values: AcceptInvitationFormValues) {
    if (!token) return
    await mutation.mutateAsync({ token, newPassword: values.newPassword })
  }

  return (
    <main className={styles.container}>
      <section className={styles.card}>
        <h1 className={styles.title}>设置账号密码</h1>
        {token ? (
          <Form<AcceptInvitationFormValues>
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
              完成注册
            </Button>
          </Form>
        ) : (
          <div>
            <p className={styles.resultText}>邀请链接无效或已过期，请联系管理员重新发送邀请。</p>
            <Button block type="primary" onClick={() => void navigate('/login')}>
              返回登录
            </Button>
          </div>
        )}
      </section>
    </main>
  )
}
