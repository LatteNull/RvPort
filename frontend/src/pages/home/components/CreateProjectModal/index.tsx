import { useEffect } from 'react'
import { Button, Form, Input, Select } from 'antd'

import { createProject } from '@/api/project/projects'
import BaseModal from '@/components/BaseModal'
import { projectArchitectureConfig } from '@/config/project-status'
import { useSubmissionSession } from '@/hooks/useSubmissionSession'
import type { CreateProjectRequest, ProjectListItem } from '@/types/project'
import { feedback } from '@/utils/feedback'

import styles from './index.module.scss'

interface CreateProjectModalProps {
  visible: boolean
  onCancel: () => void
  onCreated: (project: ProjectListItem, action: CreateProjectAction) => void
}

const initialValues: CreateProjectRequest = {
  name: '',
  description: '',
  sourceArch: 'x86_64',
  targetArch: 'riscv64'
}

const sourceArchOptions = [projectArchitectureConfig.x86_64]
const targetArchOptions = [projectArchitectureConfig.riscv64]

export type CreateProjectAction = 'configure-environment' | 'open-workbench'

export default function CreateProjectModal({
  visible,
  onCancel,
  onCreated
}: CreateProjectModalProps) {
  const [form] = Form.useForm<CreateProjectRequest>()
  const submission = useSubmissionSession('create-project', visible)
  const isPending = submission.busy

  useEffect(() => {
    if (visible) form.setFieldsValue(initialValues)
  }, [form, visible])

  const handleCancel = () => {
    if (!isPending) onCancel()
  }

  const submitForm = (action: CreateProjectAction) => {
    void submission
      .run(async (isCurrent) => {
        const values = await form.validateFields()
        if (!isCurrent()) return
        const project = await createProject({
          name: values.name.trim(),
          description: values.description?.trim() || undefined,
          sourceArch: values.sourceArch,
          targetArch: values.targetArch
        })
        if (!isCurrent()) return
        feedback.success('项目创建成功')
        onCreated(project, action)
      })
      .catch((error: unknown) =>
        feedback.error(error instanceof Error ? error.message : '项目创建失败')
      )
  }

  const footer = (
    <div className={styles.modalFooter}>
      <Button className={styles.modalFooterButton} disabled={isPending} onClick={handleCancel}>
        取消
      </Button>
      <Button
        className={styles.modalFooterButton}
        type="default"
        loading={isPending}
        onClick={() => submitForm('open-workbench')}
      >
        创建并进入工作台
      </Button>
      <Button
        className={styles.modalFooterButton}
        type="primary"
        loading={isPending}
        onClick={() => submitForm('configure-environment')}
      >
        创建并开始配置环境
      </Button>
    </div>
  )

  const title = (
    <div className={styles.modalTitle}>
      <span className={styles.title}>新建项目</span>
      <span className={styles.description}>创建项目后直接进入项目迁移流水线</span>
    </div>
  )

  return (
    <BaseModal
      busy={isPending}
      destroyOnHidden
      visible={visible}
      title={title}
      width={800}
      footer={footer}
      onCancel={handleCancel}
    >
      <Form<CreateProjectRequest>
        key={visible ? 'create-project-open' : 'create-project-closed'}
        form={form}
        initialValues={initialValues}
        layout="vertical"
        preserve={false}
        disabled={isPending}
        onFinish={() => submitForm('open-workbench')}
      >
        <div className={styles.formSectionTitle}>项目基本信息</div>
        <Form.Item<CreateProjectRequest>
          name="name"
          label="项目名称"
          normalize={(value) => value?.trim()}
          rules={[
            { required: true, whitespace: true, message: '请输入项目名称' },
            { max: 160, message: '项目名称不能超过 160 个字符' }
          ]}
        >
          <Input placeholder="请输入项目名称" />
        </Form.Item>
        <Form.Item<CreateProjectRequest>
          name="description"
          label="项目描述"
          rules={[{ max: 2000, message: '项目描述不能超过 2000 个字符' }]}
        >
          <Input.TextArea placeholder="请输入项目描述" autoSize={{ minRows: 3, maxRows: 5 }} />
        </Form.Item>
        <div className={styles.formSectionTitle}>架构配置</div>
        <Form.Item<CreateProjectRequest>
          name="sourceArch"
          label="源架构"
          rules={[{ required: true, message: '请选择源架构' }]}
        >
          <Select options={sourceArchOptions} />
        </Form.Item>
        <Form.Item<CreateProjectRequest>
          name="targetArch"
          label="目标架构"
          rules={[{ required: true, message: '请选择目标架构' }]}
        >
          <Select options={targetArchOptions} />
        </Form.Item>
      </Form>
    </BaseModal>
  )
}
