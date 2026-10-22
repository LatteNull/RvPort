import { Tag } from 'antd'

import type { ProjectBuildValidation } from '@/types/project'

import { getBitcodePresentation } from '../bitcodePresentation'

import styles from '../index.module.scss'

type BuildBitcodeResult = Pick<ProjectBuildValidation, 'status' | 'bitcode'>

export function BitcodeStatusTag({ build }: { build: BuildBitcodeResult }) {
  const { color, label } = getBitcodePresentation(build)
  return (
    <Tag className={styles.bitcodeStatusTag} color={color}>
      {label}
    </Tag>
  )
}

export function BitcodeResult({ build }: { build: BuildBitcodeResult }) {
  const { detail } = getBitcodePresentation(build)
  return (
    <section aria-label="LLVM Bitcode" className={styles.bitcodeResult}>
      <div className={styles.bitcodeHeading}>
        <h3>LLVM Bitcode</h3>
        <BitcodeStatusTag build={build} />
      </div>
      <p>{detail}</p>
      <small>这是 x86 构建的分析制品，生成结果不影响构建状态。</small>
    </section>
  )
}
