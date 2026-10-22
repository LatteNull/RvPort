import { useNavigate } from 'react-router'
import { Button, Result } from 'antd'

import styles from '../error.module.scss'

export default function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <main className={styles.container}>
      <Result
        status="404"
        title="页面不存在"
        subTitle="你访问的页面可能已移动、删除或地址不正确。"
        extra={
          <Button type="primary" onClick={() => void navigate('/home')}>
            返回首页
          </Button>
        }
      />
    </main>
  )
}
