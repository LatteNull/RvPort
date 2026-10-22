import { MemoryRouter, Route, Routes } from 'react-router'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/api/auth', () => ({ logout: vi.fn() }))

import AdminLayout from './AdminLayout'
import MainLayout from './MainLayout'

function renderLayout(layout: React.ReactNode, path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={layout}>
          <Route path={path} element={<h2>路由正文</h2>} />
        </Route>
      </Routes>
    </MemoryRouter>
  )
}

describe.each([
  ['主布局', <MainLayout />, '/home'],
  ['管理布局', <AdminLayout />, '/admin/users']
])('%s', (_name, layout, path) => {
  it('provides one keyboard-addressable main-content landmark', async () => {
    renderLayout(layout, path)

    const skipLink = screen.getByRole('link', { name: '跳至主内容' })
    const main = screen.getByRole('main')

    expect(skipLink).toHaveAttribute('href', '#main-content')
    expect(main).toHaveAttribute('id', 'main-content')
    expect(main).toHaveAttribute('tabindex', '-1')
    expect(screen.getAllByRole('main')).toHaveLength(1)
    expect(screen.getByRole('heading', { name: '路由正文' })).toBeInTheDocument()
  })
})

describe('主布局品牌入口', () => {
  it('点击 Logo 返回项目列表', () => {
    renderLayout(<MainLayout />, '/home')

    expect(screen.getByRole('link', { name: 'RvPort，返回项目列表' })).toHaveAttribute(
      'href',
      '/home'
    )
  })
})

describe('主布局内容宽度', () => {
  it('为项目工作台启用宽屏内容容器', () => {
    renderLayout(<MainLayout />, '/projects/project-1/workflow')

    const main = screen.getByRole('main')
    expect(main.firstElementChild).toHaveAttribute('data-layout-width', 'workspace')
  })

  it('为普通页面保留默认内容容器', () => {
    renderLayout(<MainLayout />, '/home')

    const main = screen.getByRole('main')
    expect(main.firstElementChild).toHaveAttribute('data-layout-width', 'default')
  })
})
