import { useState } from 'react'
import { useNavigate } from 'react-router'
import { Button, Checkbox, Flex, Form, Input } from 'antd'

import { login } from '@/api/auth'
import logo from '@/assets/images/logo.svg'
import { useSubmissionSession } from '@/hooks/useSubmissionSession'
import { useAuthStore } from '@/store'
import { feedback } from '@/utils/feedback'
import { safeLocalStorage } from '@/utils/localStorage'

import styles from '../auth.module.scss'

interface LoginForm {
  username: string
  password: string
  rememberUsername: boolean
}

const REMEMBERED_USERNAME_STORAGE_KEY = 'rvport.remembered-username'

function getRememberedUsername() {
  return safeLocalStorage.getItem(REMEMBERED_USERNAME_STORAGE_KEY) ?? ''
}

function clearRememberedUsername() {
  safeLocalStorage.removeItem(REMEMBERED_USERNAME_STORAGE_KEY)
}

export default function LoginPage() {
  const navigate = useNavigate()
  const { setUser } = useAuthStore()
  const submission = useSubmissionSession('login')
  const loading = submission.busy
  const [rememberedUsername] = useState(getRememberedUsername)

  const handleSubmit = (values: LoginForm) =>
    submission.run(async (isCurrent) => {
      const { rememberUsername, ...loginPayload } = values
      try {
        const { user } = await login(loginPayload)
        if (!isCurrent()) return
        if (rememberUsername) {
          safeLocalStorage.setItem(REMEMBERED_USERNAME_STORAGE_KEY, values.username)
        } else {
          clearRememberedUsername()
        }
        setUser(user)
        feedback.success(`欢迎回来，${user.username}`)
        navigate(user.mustChangePassword ? '/force-change-password' : '/home', { replace: true })
      } catch {
        /* 请求层已提供失败反馈，保留本次输入。 */
      }
    })

  return (
    <main className={styles.container}>
      <div className={styles.card}>
        <h1 className={styles.title}>
          <img alt="RvPort" className={styles.authLogo} height={40} src={logo} width={147} />
        </h1>
        <Form<LoginForm>
          disabled={loading}
          initialValues={{
            username: rememberedUsername,
            rememberUsername: Boolean(rememberedUsername)
          }}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Form.Item<LoginForm>
            name="username"
            label="账号"
            normalize={(value) => value?.trim()}
            rules={[{ required: true, whitespace: true, message: '请输入账号' }]}
          >
            <Input autoComplete="username" placeholder="请输入账号" />
          </Form.Item>
          <Form.Item<LoginForm>
            name="password"
            label="密码"
            rules={[
              { required: true, message: '请输入密码' },
              {
                validator(_, value) {
                  return !value || value.trim()
                    ? Promise.resolve()
                    : Promise.reject(new Error('密码不能只包含空白字符'))
                }
              }
            ]}
          >
            <Input.Password autoComplete="current-password" placeholder="请输入密码" />
          </Form.Item>
          <Flex align="center" justify="space-between">
            <Form.Item<LoginForm> name="rememberUsername" valuePropName="checked" noStyle>
              <Checkbox onChange={(event) => !event.target.checked && clearRememberedUsername()}>
                记住账号
              </Checkbox>
            </Form.Item>
            <Button type="link" onClick={() => void navigate('/forgot-password')}>
              忘记密码
            </Button>
          </Flex>
          <Button htmlType="submit" type="primary" block loading={loading} style={{ marginTop: 8 }}>
            登录
          </Button>
        </Form>
      </div>
    </main>
  )
}
