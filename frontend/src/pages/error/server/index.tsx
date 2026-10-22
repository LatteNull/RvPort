import { useNavigate } from 'react-router'
import { Button, Result } from 'antd'

import styles from '../error.module.scss'

export default function ServerErrorPage() {
  const navigate = useNavigate()

  return (
    <main className={styles.container}>
      <Result
        status="500"
        title="服务暂时不可用"
        subTitle="服务端发生异常，请稍后重试。"
        extra={
          <Button type="primary" onClick={() => navigate('/home')}>
            返回首页
          </Button>
        }
      />
    </main>
  )
}
