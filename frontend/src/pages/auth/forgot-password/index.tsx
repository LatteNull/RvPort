import { useState } from 'react'
import { useNavigate } from 'react-router'
import { Button, Form, Input } from 'antd'

import { requestPasswordReset } from '@/api/auth'
import { useSessionMutation } from '@/hooks/useSessionMutation'
import { feedback } from '@/utils/feedback'

import styles from '../auth.module.scss'

interface ForgotPasswordFormValues {
  identifier: string
}

export default function ForgotPasswordPage() {
  const navigate = useNavigate()
  const [submitted, setSubmitted] = useState(false)
  const mutation = useSessionMutation({
    sessionKey: 'password-reset-request',
    active: !submitted,
    mutationFn: requestPasswordReset,
    onSuccess() {
      setSubmitted(true)
      feedback.success('如账号存在且已绑定邮箱，重置链接已发送')
    }
  })

  const handleSubmit = async (values: ForgotPasswordFormValues) => {
    await mutation.mutateAsync({ identifier: values.identifier.trim() })
  }

  return (
    <main className={styles.container}>
      <section className={styles.card}>
        <h1 className={styles.title}>找回密码</h1>
        {submitted ? (
          <div>
            <p className={styles.resultText}>请查看邮箱中的密码重置链接。</p>
            <Button block type="primary" onClick={() => void navigate('/login')}>
              返回登录
            </Button>
          </div>
        ) : (
          <Form<ForgotPasswordFormValues>
            disabled={mutation.isPending}
            layout="vertical"
            onFinish={handleSubmit}
          >
            <Form.Item<ForgotPasswordFormValues>
              label="账号或邮箱"
              name="identifier"
              normalize={(value) => value?.trim()}
              rules={[{ required: true, whitespace: true, message: '请输入账号或邮箱' }]}
            >
              <Input autoComplete="username" placeholder="请输入账号或邮箱" />
            </Form.Item>
            <Button block htmlType="submit" loading={mutation.isPending} type="primary">
              发送重置链接
            </Button>
            <Button block type="link" onClick={() => void navigate('/login')}>
              返回登录
            </Button>
          </Form>
        )}
      </section>
    </main>
  )
}
