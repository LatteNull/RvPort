import { useEffect } from 'react'
import { message, notification } from 'antd'

import { registerAppNotification } from '@/utils/appNotification'
import { registerFeedbackMessage } from '@/utils/feedback'

export default function FeedbackBridge() {
  const [messageApi, contextHolder] = message.useMessage()
  const [notificationApi, notificationContextHolder] = notification.useNotification()

  useEffect(() => {
    registerFeedbackMessage(messageApi)
    registerAppNotification(notificationApi)
    return () => {
      registerFeedbackMessage(null)
      registerAppNotification(null)
    }
  }, [messageApi, notificationApi])

  return (
    <>
      {contextHolder}
      {notificationContextHolder}
    </>
  )
}
