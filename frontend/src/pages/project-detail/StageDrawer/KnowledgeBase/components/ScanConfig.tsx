import { useEffect } from 'react'
import { Button, Flex, Form, Input, Select } from 'antd'

import styles from '../index.module.scss'

export function ScanConfig({
  sourceReady,
  x86BuildReady,
  onManageSource,
  onManageX86Build,
  onReady
}: {
  sourceReady: boolean
  x86BuildReady: boolean
  onManageSource?: () => void
  onManageX86Build?: () => void
  onReady?: () => void
}) {
  useEffect(() => {
    onReady?.()
  }, [onReady])

  return (
    <div className={styles.configView}>
      <div className={styles.viewIntro}>
        <h3>执行知识库扫描</h3>
        <p>扫描当前有效源码，识别架构相关实现和迁移风险。</p>
      </div>
      {!sourceReady ? (
        <div className={styles.helpPanel} role="alert">
          当前没有可用源码版本，请先完成源码导入并设为当前源码。
          {onManageSource ? (
            <Button type="link" onClick={onManageSource}>
              前往源码管理
            </Button>
          ) : null}
        </div>
      ) : null}
      {sourceReady && !x86BuildReady ? (
        <div className={styles.helpPanel} role="alert">
          请先完成当前源码的 x86 构建，再执行知识库扫描。
          {onManageX86Build ? (
            <Button type="link" onClick={onManageX86Build}>
              前往 x86 构建
            </Button>
          ) : null}
        </div>
      ) : null}
      <>
        <Flex gap={16}>
          <Form.Item
            className={styles.configFormItem}
            label="扫描语言"
            name="language"
            rules={[{ required: true }]}
          >
            <Select options={[{ label: 'C/C++', value: 'C/C++' }]} />
          </Form.Item>
        </Flex>
        <Form.Item
          className={styles.configFormItem}
          label="扫描范围"
          name="scope"
          rules={[{ required: true }]}
        >
          <Input />
        </Form.Item>
        <div className={styles.helpPanel}>使用项目根目录相对路径；填写 ./ 表示扫描整个项目。</div>
        <Form.Item
          className={styles.configFormItem}
          label="排除目录名（宽松匹配，--exclude）"
          name="excludedDirectoryNames"
          rules={[{ required: true }]}
        >
          <Input />
        </Form.Item>
        <div className={styles.helpPanel}>
          逗号分隔。只要文件路径片段中包含这些目录名就跳过，例如 build 会跳过任意路径下的 build
          目录。
        </div>
        <Form.Item
          className={styles.configFormItem}
          label="精确排除路径（项目根目录下，--exclude-path）"
          name="excludedPaths"
        >
          <Input.TextArea rows={4} />
        </Form.Item>
        <div className={styles.helpPanel}>
          每行一个项目根目录下的目录路径。只有文件位于该目录下才跳过，不会误伤其他同名目录。
        </div>
      </>
    </div>
  )
}
