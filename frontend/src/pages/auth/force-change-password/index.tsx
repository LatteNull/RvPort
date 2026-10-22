import { useNavigate } from 'react-router'
import { Alert, Button, Form, Input } from 'antd'

import { usePasswordChange } from '@/hooks/usePasswordChange'
import { useAuthStore } from '@/store'

import styles from '../auth.module.scss'

interface ForceChangePasswordFormValues {
  confirmPassword: string
  currentPassword: string
  newPassword: string
}

export default function ForceChangePasswordPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const password = usePasswordChange(() => {
    void navigate('/login', { replace: true })
  })
  const loading = password.loading
  const handleSubmit = (values: ForceChangePasswordFormValues) =>
    password.submit({ currentPassword: values.currentPassword, newPassword: values.newPassword })

  return (
    <main className={styles.container}>
      <section className={styles.card}>
        <h1 className={styles.title}>强制修改密码</h1>
        <p className={styles.subtitle}>为保障账号安全，请先设置新的登录密码。</p>
        {password.passwordChanged ? (
          <Alert
            type="warning"
            title="密码已修改，请退出后重新登录"
            action={
              <Button loading={loading} onClick={() => void password.submit()}>
                重试退出登录
              </Button>
            }
          />
        ) : (
          <Form<ForceChangePasswordFormValues>
            disabled={loading}
            layout="vertical"
            onFinish={handleSubmit}
          >
            <Form.Item
              label="当前密码"
              name="currentPassword"
              rules={[
                { required: true, message: '请输入当前密码' },
                {
                  validator(_, value) {
                    return value?.trim()
                      ? Promise.resolve()
                      : Promise.reject(new Error('当前密码不能只包含空白字符'))
                  }
                }
              ]}
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
                {
                  validator(_, value) {
                    if (!value || value.trim()) return Promise.resolve()
                    return Promise.reject(new Error('新密码不能只包含空白字符'))
                  }
                },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    if (value === getFieldValue('currentPassword')) {
                      return Promise.reject(new Error('新密码不能与当前密码相同'))
                    }
                    if (user && value && value.toLowerCase() === user.username.toLowerCase()) {
                      return Promise.reject(new Error('新密码不能与账号相同'))
                    }
                    return Promise.resolve()
                  }
                })
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
            <Button block htmlType="submit" loading={loading} type="primary">
              确认修改
            </Button>
          </Form>
        )}
      </section>
    </main>
  )
}
