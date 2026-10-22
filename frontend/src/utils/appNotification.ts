import type { ArgsProps, NotificationInstance } from 'antd/es/notification/interface'

let notificationApi: NotificationInstance | null = null

export function registerAppNotification(api: NotificationInstance | null) {
  notificationApi = api
}

export const appNotification = {
  success(options: ArgsProps) {
    notificationApi?.success(options)
  },
  error(options: ArgsProps) {
    notificationApi?.error(options)
  },
  warning(options: ArgsProps) {
    notificationApi?.warning(options)
  }
}
