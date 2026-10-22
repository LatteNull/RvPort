import { useSyncExternalStore } from 'react'
import { Suspense } from 'react'
import { Link, Outlet, useMatch, useNavigate } from 'react-router'
import { DownOutlined, LogoutOutlined, SettingOutlined, UserOutlined } from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { Button, Dropdown, Layout } from 'antd'

import { logout as logoutApi } from '@/api/auth'
import logo from '@/assets/images/logo.svg'
import ContentState from '@/components/ContentState'
import { useSubmissionSession } from '@/hooks/useSubmissionSession'
import { getAuthGeneration, subscribeAuthSession } from '@/store/authSession'
import { useAuthStore } from '@/store/authStore'
import { feedback } from '@/utils/feedback'

import styles from './index.module.scss'

const { Header, Content } = Layout

export default function MainLayout() {
  const generation = useSyncExternalStore(
    subscribeAuthSession,
    getAuthGeneration,
    getAuthGeneration
  )
  const navigate = useNavigate()
  const isProjectWorkbench = Boolean(useMatch('/projects/:projectId/*'))
  const logout = useAuthStore((s) => s.logout)
  const user = useAuthStore((s) => s.user)
  const session = useSubmissionSession(user?.id ?? 'logout')
  const loggingOut = session.busy
  const handleLogout = async () => {
    await session.run(async (isCurrent) => {
      try {
        const { loggedOut } = await logoutApi()
        if (!isCurrent()) return
        if (!loggedOut) {
          feedback.error('退出登录失败，请重试')
          return
        }
        logout()
        feedback.success('已退出登录')
        void navigate('/login', { replace: true })
      } catch {
        /* 请求层负责当前会话错误反馈。 */
      }
    })
  }

  const menuItems: MenuProps['items'] = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人中心'
    },
    ...(user?.isSuperAdmin
      ? [
          {
            key: 'admin',
            icon: <SettingOutlined />,
            label: '管理中心'
          }
        ]
      : []),
    { type: 'divider' },
    {
      key: 'logout',
      danger: true,
      icon: <LogoutOutlined />,
      label: '退出登录'
    }
  ]
  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (key === 'profile') navigate('/settings/profile')
    if (key === 'admin') navigate('/admin/users')
    if (key === 'logout') void handleLogout()
  }
  const userName = user?.displayName || user?.username || '当前用户'

  return (
    <Layout className={styles.root}>
      <a className={styles.skipLink} href="#main-content">
        跳至主内容
      </a>
      <Header className={styles.header}>
        <div
          className={[styles.headerInner, isProjectWorkbench && styles.workspaceInner]
            .filter(Boolean)
            .join(' ')}
          data-layout-width={isProjectWorkbench ? 'workspace' : 'default'}
        >
          <Link aria-label="RvPort，返回项目列表" className={styles.logoLink} to="/home">
            <img src={logo} alt="" className={styles.logo} height={33} width={121} />
          </Link>
          <Dropdown menu={{ items: menuItems, onClick: handleMenuClick }} trigger={['click']}>
            <Button
              aria-label="账户菜单"
              className={styles.userMenuButton}
              disabled={loggingOut}
              type="text"
            >
              <span className={styles.userName}>{userName}</span>
              <DownOutlined className={styles.userMenuArrow} />
            </Button>
          </Dropdown>
        </div>
      </Header>
      <Content className={styles.content} id="main-content" tabIndex={-1}>
        <div
          className={[styles.contentInner, isProjectWorkbench && styles.workspaceInner]
            .filter(Boolean)
            .join(' ')}
          data-layout-width={isProjectWorkbench ? 'workspace' : 'default'}
        >
          <Suspense fallback={<ContentState kind="loading" description="正在加载页面" compact />}>
            <Outlet key={generation} />
          </Suspense>
        </div>
      </Content>
    </Layout>
  )
}
