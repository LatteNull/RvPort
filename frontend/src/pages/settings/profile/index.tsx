import { Fragment, useState } from 'react'
import { useNavigate } from 'react-router'
import { HomeOutlined } from '@ant-design/icons'
import { Button, Card, Descriptions, Flex, Form, Input, Tag, Tooltip } from 'antd'

import { updateProfile } from '@/api/auth'
import { usePasswordChange } from '@/hooks/usePasswordChange'
import { useSessionMutation } from '@/hooks/useSessionMutation'
import { useAuthStore } from '@/store'
import { formatDateTime } from '@/utils/display'
import { feedback } from '@/utils/feedback'

import ChangePasswordModal, {
  type ProfileChangePasswordFormValues
} from './components/ChangePasswordModal'

import styles from './index.module.scss'

interface ProfileFormValues {
  displayName: string
}

function getStatusText(status: 'ACTIVE' | 'DISABLED') {
  return status === 'ACTIVE' ? '正常' : '已禁用'
}

export default function ProfilePage() {
  const navigate = useNavigate()
  const [form] = Form.useForm<ProfileFormValues>()
  const user = useAuthStore((state) => state.user)
  const setUser = useAuthStore((state) => state.setUser)
  const [editingProfile, setEditingProfile] = useState(false)
  const [passwordModalOpen, setPasswordModalOpen] = useState(false)

  const updateProfileMutation = useSessionMutation({
    sessionKey: `profile:${user?.id}`,
    active: editingProfile,
    mutationFn: updateProfile,
    onSuccess(updatedUser) {
      setUser(updatedUser)
      form.setFieldValue('displayName', updatedUser.displayName ?? '')
      setEditingProfile(false)
      feedback.success('昵称已更新')
    }
  })
  const password = usePasswordChange(() => {
    setPasswordModalOpen(false)
    void navigate('/login', { replace: true })
  }, passwordModalOpen)

  if (!user) return null

  const handleProfileSubmit = async ({ displayName }: ProfileFormValues) => {
    await updateProfileMutation.mutateAsync({ displayName: displayName.trim() || null })
  }
  const handlePasswordSubmit = async (values: ProfileChangePasswordFormValues) => {
    await password.submit({
      currentPassword: values.currentPassword,
      newPassword: values.newPassword
    })
  }
  const handleCancelProfileEdit = () => {
    form.setFieldValue('displayName', user.displayName ?? '')
    setEditingProfile(false)
  }
  const handleStartProfileEdit = () => {
    form.setFieldValue('displayName', user.displayName ?? '')
    setEditingProfile(true)
  }

  return (
    <Flex vertical className={styles.page} gap={16}>
      <header>
        <Flex align="center" className={styles.pageHeader} gap={8}>
          <Tooltip title="返回首页">
            <Button
              aria-label="返回首页"
              className={styles.backButton}
              icon={<HomeOutlined />}
              shape="circle"
              type="text"
              onClick={() => void navigate('/home')}
            />
          </Tooltip>
          <Flex align="baseline" gap={12}>
            <h1>个人中心</h1>
            <p>管理账户资料与安全设置</p>
          </Flex>
        </Flex>
      </header>

      <Card className={styles.section} title="基本资料">
        <Descriptions column={2} size="small">
          <Descriptions.Item label="账号">{user.username}</Descriptions.Item>
          <Descriptions.Item label="邮箱">{user.email || '--'}</Descriptions.Item>
          <Descriptions.Item label="账户状态">
            <Tag color={user.status === 'ACTIVE' ? 'success' : 'default'}>
              {getStatusText(user.status)}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="最近登录时间">
            {formatDateTime(user.lastLoginAt)}
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">{formatDateTime(user.createdAt)}</Descriptions.Item>
        </Descriptions>

        <Flex align="center" className={styles.displayNameRow} gap={12}>
          <span className={styles.fieldLabel}>昵称</span>
          {editingProfile ? (
            <Form<ProfileFormValues>
              disabled={updateProfileMutation.isPending}
              form={form}
              layout="inline"
              onFinish={handleProfileSubmit}
            >
              <Form.Item<ProfileFormValues>
                name="displayName"
                rules={[{ max: 64, message: '昵称不能超过 64 个字符' }]}
              >
                <Input aria-label="昵称" placeholder="请输入昵称" />
              </Form.Item>
              <Form.Item>
                <Flex gap={8}>
                  <Button
                    htmlType="submit"
                    loading={updateProfileMutation.isPending}
                    type="primary"
                  >
                    保存
                  </Button>
                  <Button
                    disabled={updateProfileMutation.isPending}
                    onClick={handleCancelProfileEdit}
                  >
                    取消
                  </Button>
                </Flex>
              </Form.Item>
            </Form>
          ) : (
            <Fragment>
              <span className={styles.displayName}>{user.displayName || '--'}</span>
              <Button type="link" onClick={handleStartProfileEdit}>
                编辑
              </Button>
            </Fragment>
          )}
        </Flex>
      </Card>

      <Card className={styles.section} title="账户安全">
        <Flex align="center" className={styles.securityRow} gap={24} justify="space-between">
          <Flex vertical className={styles.securityContent} gap={4}>
            <strong>登录密码</strong>
            <span className={styles.securityDescription}>定期更新密码有助于保障账户安全</span>
          </Flex>
          <Button type="primary" onClick={() => setPasswordModalOpen(true)}>
            修改密码
          </Button>
        </Flex>
      </Card>

      <ChangePasswordModal
        passwordChanged={password.passwordChanged}
        onRetryLogout={() => password.submit()}
        loading={password.loading}
        username={user.username}
        visible={passwordModalOpen}
        onCancel={() => setPasswordModalOpen(false)}
        onSubmit={handlePasswordSubmit}
      />
    </Flex>
  )
}
