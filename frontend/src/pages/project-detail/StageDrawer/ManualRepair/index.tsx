import { CodeOutlined, RightOutlined, ToolOutlined } from '@ant-design/icons'
import { Button } from 'antd'

import StageSurface from '../components/StageSurface'
import { getStageDrawerWidth } from '../drawerWidth'
import type { StageDrawerProps } from '../types'

import styles from './index.module.scss'

const repairPaths = [
  {
    action: '查看依赖分析',
    description: '适用于缺失依赖、目标侧未安装、版本不兼容等问题。',
    icon: <ToolOutlined />,
    key: 'dependency',
    stageId: 'rv-dependency-analysis',
    title: '修复依赖问题',
    tip: '确认替代包、目标侧匹配情况和迁移输入后，再调整构建依赖。'
  },
  {
    action: '前往源码管理',
    description: '适用于知识库扫描发现的源码问题，或需要在线下修改代码的情况。',
    icon: <CodeOutlined />,
    key: 'source',
    stageId: 'assets',
    title: '修复源码问题',
    tip: '完成本地修改后，上传或更新当前源码版本，使后续构建使用修复后的内容。'
  }
] as const

export default function Manual({ visible, stage, onClose, onStageChange }: StageDrawerProps) {
  return (
    <StageSurface
      size={getStageDrawerWidth('manual')}
      title={stage?.title ?? '人工修复'}
      visible={visible}
      onClose={onClose}
    >
      <div className={styles.content}>
        <section className={styles.guideHeader}>
          <div className={styles.guideIcon}>
            <ToolOutlined />
          </div>
          <div>
            <h3>根据问题类型完成修复</h3>
            <p>请从评估报告定位问题，再选择依赖或源码的处理路径。</p>
          </div>
        </section>
        <section className={styles.repairSection}>
          <h3>选择处理路径</h3>
          <div className={styles.repairGrid}>
            {repairPaths.map((path) => (
              <article className={styles.repairPath} key={path.key}>
                <div className={styles.pathHeading}>
                  <span className={styles.pathIcon}>{path.icon}</span>
                  <h4>{path.title}</h4>
                </div>
                <p>{path.description}</p>
                <span className={styles.pathTip}>{path.tip}</span>
                <Button
                  aria-label={path.action}
                  className={`${styles.pathAction} ${styles.actionLink}`}
                  icon={<RightOutlined />}
                  iconPlacement="end"
                  type="link"
                  onClick={() => onStageChange?.(path.stageId)}
                >
                  {path.action}
                </Button>
              </article>
            ))}
          </div>
        </section>
        <section className={styles.verificationHint}>
          <strong>修复完成后</strong>
          <span>更新当前源码版本，并在构建验证中重新构建 RISC-V 产物。</span>
          <Button
            className={styles.actionLink}
            type="link"
            onClick={() => onStageChange?.('build')}
          >
            前往构建验证
          </Button>
        </section>
      </div>
    </StageSurface>
  )
}
