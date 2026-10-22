import { useNavigate } from 'react-router'
import { Button, Result } from 'antd'

import styles from '../error.module.scss'

export default function ForbiddenPage() {
  const navigate = useNavigate()

  return (
    <main className={styles.container}>
      <Result
        status="403"
        title="403"
        subTitle="你没有权限访问此资源"
        extra={
          <Button type="primary" onClick={() => navigate('/home')}>
            返回首页
          </Button>
        }
      />
    </main>
  )
}
