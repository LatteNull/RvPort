import type { MessageInstance } from 'antd/es/message/interface'

let messageApi: MessageInstance | null = null

export function registerFeedbackMessage(api: MessageInstance | null) {
  messageApi = api
}

export const feedback = {
  success(content: string) {
    void messageApi?.success(content)
  },
  error(content: string) {
    void messageApi?.error(content)
  },
  warning(content: string) {
    void messageApi?.warning(content)
  }
}
