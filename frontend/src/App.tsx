import { RouterProvider } from 'react-router/dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'

import FeedbackBridge from '@/components/FeedbackBridge'
import { queryClient } from '@/queryClient'
import router from '@/router'
import { antdTheme } from '@/theme'

import '@/styles/global.scss'

export default function App() {
  return (
    <ConfigProvider variant="outlined" locale={zhCN} theme={antdTheme}>
      <FeedbackBridge />
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ConfigProvider>
  )
}
