import { useRef, useState } from 'react'
import {
  EditOutlined,
  KeyOutlined,
  MailOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined
} from '@ant-design/icons'
import { Button, Flex, Popconfirm, Tag, Tooltip } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  createAdminUser,
  getAdminUsers,
  resetAdminUserPassword,
  sendAdminUserInvitation,
  updateAdminUser
} from '@/api/admin/users'
import type { BaseTableHandle } from '@/components/BaseTable'
import BaseTable from '@/components/BaseTable'
import { useSessionMutation } from '@/hooks/useSessionMutation'
import type { User } from '@/types'
import type { AdminUserListParams } from '@/types/admin/users'
import { formatDateTime } from '@/utils/display'
import { feedback } from '@/utils/feedback'

import { adminQueryKeys } from '../queryKeys'
import ResetPasswordModal from './components/ResetPasswordModal'
import UserModal from './components/UserModal'

import styles from './index.module.scss'

type Filters = Pick<AdminUserListParams, 'keyword' | 'status'>

export default function AdminUsersPage() {
  const tableRef = useRef<BaseTableHandle>(null)
  const [invitingUserIds, setInvitingUserIds] = useState<Set<string>>(() => new Set())
  const [updatingUser, setUpdatingUser] = useState<string | null>(null)
  const [modalUser, setModalUser] = useState<User | null | undefined>()
  const [resetPasswordUser, setResetPasswordUser] = useState<User | undefined>()
  const updateMutation = useSessionMutation({
    sessionKey: 'admin-user-status',
    active: true,
    mutationFn: ({ userId, status }: { userId: string; status: User['status'] }) =>
      updateAdminUser(userId, { status }),
    onSuccess: async () => {
      feedback.success('用户状态已更新')
      await tableRef.current?.reload()
    },
    onSettled: () => setUpdatingUser(null)
  })
  const invitationMutation = useSessionMutation({
    sessionKey: 'admin-user-invitation',
    active: true,
    mutationFn: sendAdminUserInvitation,
    onMutate: (userId) => {
      setInvitingUserIds((ids) => new Set(ids).add(userId))
    },
    onSuccess: async () => {
      feedback.success('邀请邮件已发送')
      await tableRef.current?.reload()
    },
    onSettled: (_, __, userId) => {
      setInvitingUserIds((ids) => {
        const nextIds = new Set(ids)
        nextIds.delete(userId)
        return nextIds
      })
    }
  })
  const saveMutation = useSessionMutation({
    sessionKey: modalUser?.id ?? 'new-user',
    active: modalUser !== undefined,
    mutationFn: async (values: {
      displayName?: string
      email: string
      status: User['status']
      username: string
    }) => {
      if (modalUser)
        return updateAdminUser(modalUser.id, {
          displayName: values.displayName || null,
          email: values.email,
          status: values.status
        })
      return createAdminUser(values)
    },
    onSuccess: async () => {
      setModalUser(undefined)
      feedback.success('用户信息已保存')
      await tableRef.current?.reload()
    }
  })
  const resetPasswordMutation = useSessionMutation({
    sessionKey: resetPasswordUser?.id ?? 'reset-password',
    active: Boolean(resetPasswordUser),
    mutationFn: ({ newPassword, userId }: { newPassword: string; userId: string }) =>
      resetAdminUserPassword(userId, { mustChangePassword: true, newPassword }),
    onSuccess: async () => {
      setResetPasswordUser(undefined)
      feedback.success('密码已重置')
      await tableRef.current?.reload()
    }
  })
  const columns: ColumnsType<User> = [
    { dataIndex: 'username', title: '账号' },
    { dataIndex: 'displayName', title: '昵称', render: (value) => value || '--' },
    { dataIndex: 'email', title: '邮箱', render: (value) => value || '--' },
    {
      dataIndex: 'lastLoginAt',
      title: '最近登录时间',
      render: formatDateTime
    },
    {
      dataIndex: 'status',
      title: '状态',
      render: (value) => (
        <Tag color={value === 'ACTIVE' ? 'success' : 'default'}>
          {value === 'ACTIVE' ? '启用' : '禁用'}
        </Tag>
      )
    },
    { dataIndex: 'mustChangePassword', title: '需改密', render: (value) => (value ? '是' : '否') },
    {
      key: 'actions',
      title: '操作',
      fixed: 'right',
      width: 152,
      render: (_, user) => {
        return (
          <Flex gap={4}>
            <Popconfirm
              title={`确认${user.status === 'ACTIVE' ? '禁用' : '启用'}该用户？`}
              onConfirm={() => {
                setUpdatingUser(user.id)
                updateMutation.mutate({
                  userId: user.id,
                  status: user.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE'
                })
              }}
            >
              <Tooltip title={user.status === 'ACTIVE' ? '禁用用户' : '启用用户'}>
                <Button
                  aria-label={user.status === 'ACTIVE' ? '禁用用户' : '启用用户'}
                  icon={user.status === 'ACTIVE' ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                  loading={updatingUser === user.id}
                  disabled={updateMutation.isPending && updatingUser !== user.id}
                  size="small"
                  type="text"
                />
              </Tooltip>
            </Popconfirm>
            <Tooltip title="重发邀请">
              <Popconfirm
                cancelText="取消"
                description="该用户此前未使用的邀请链接将立即失效。"
                okText="确认重发"
                title={`确认向「${user.username}」重发邀请？`}
                onConfirm={() => invitationMutation.mutate(user.id)}
              >
                <Button
                  aria-label="重发邀请"
                  icon={<MailOutlined />}
                  loading={invitingUserIds.has(user.id)}
                  disabled={invitationMutation.isPending && !invitingUserIds.has(user.id)}
                  size="small"
                  type="text"
                />
              </Popconfirm>
            </Tooltip>
            <Tooltip title="编辑用户">
              <Button
                aria-label="编辑用户"
                icon={<EditOutlined />}
                size="small"
                type="text"
                onClick={() => setModalUser(user)}
              />
            </Tooltip>
            <Tooltip title="重置密码">
              <Button
                aria-label="重置密码"
                icon={<KeyOutlined />}
                size="small"
                type="text"
                onClick={() => setResetPasswordUser(user)}
              />
            </Tooltip>
          </Flex>
        )
      }
    }
  ]

  return (
    <section className={styles.page}>
      <div className={styles.tableArea}>
        <BaseTable<User, Filters>
          className={styles.table}
          columns={columns}
          queryKey={adminQueryKeys.users()}
          ref={tableRef}
          rowKey="id"
          autoHeight
          request={(query) =>
            getAdminUsers({
              keyword: query.keyword,
              page: query.page,
              pageSize: query.pageSize,
              status: query.status
            })
          }
          toolbar={{
            actions: (
              <Button icon={<PlusOutlined />} type="primary" onClick={() => setModalUser(null)}>
                新增用户
              </Button>
            ),
            filters: {
              fields: [
                { name: 'keyword', placeholder: '搜索账号或邮箱', type: 'search' },
                {
                  name: 'status',
                  options: [
                    { label: '启用', value: 'ACTIVE' },
                    { label: '禁用', value: 'DISABLED' }
                  ],
                  placeholder: '状态',
                  type: 'select'
                }
              ]
            }
          }}
        />
      </div>
      <UserModal
        loading={saveMutation.isPending}
        user={modalUser ?? null}
        visible={modalUser !== undefined}
        onCancel={() => setModalUser(undefined)}
        onSubmit={async (values) => {
          await saveMutation.mutateAsync(values)
        }}
      />
      <ResetPasswordModal
        loading={resetPasswordMutation.isPending}
        user={resetPasswordUser ?? null}
        visible={Boolean(resetPasswordUser)}
        onCancel={() => setResetPasswordUser(undefined)}
        onSubmit={async (values) => {
          if (!resetPasswordUser) return
          await resetPasswordMutation.mutateAsync({ ...values, userId: resetPasswordUser.id })
        }}
      />
    </section>
  )
}
