import { Fragment, useEffect, useMemo } from 'react'
import { Button, Checkbox, Form, Tag } from 'antd'

import BaseModal from '@/components/BaseModal'
import type { AgentRuntime, ModelProfile } from '@/types/admin/models'

import styles from './TestProfileModal.module.scss'

interface TestProfileFormValues {
  agentRuntimeIds: string[]
}

interface TestProfileModalProps {
  agentRuntimes: AgentRuntime[]
  defaultAgentRuntimeId?: string
  loading: boolean
  profile: ModelProfile | null
  onCancel: () => void
  onSubmit: (values: TestProfileFormValues) => Promise<void>
}

const formId = 'test-model-profile-form'

export default function TestProfileModal({
  agentRuntimes,
  defaultAgentRuntimeId,
  loading,
  profile,
  onCancel,
  onSubmit
}: TestProfileModalProps) {
  const [form] = Form.useForm<TestProfileFormValues>()
  const selectedAgentRuntimeIds = Form.useWatch('agentRuntimeIds', form) ?? []
  const enabledRuntimes = useMemo(
    () => agentRuntimes.filter((runtime) => runtime.enabled),
    [agentRuntimes]
  )
  const selectableAgentRuntimeIds = useMemo(
    () => enabledRuntimes.slice(0, 10).map((runtime) => runtime.id),
    [enabledRuntimes]
  )
  const allAgentsSelected =
    selectableAgentRuntimeIds.length > 0 &&
    selectableAgentRuntimeIds.every((runtimeId) => selectedAgentRuntimeIds.includes(runtimeId))
  const initialAgentRuntimeIds = useMemo(
    () =>
      defaultAgentRuntimeId &&
      enabledRuntimes.some((runtime) => runtime.id === defaultAgentRuntimeId)
        ? [defaultAgentRuntimeId]
        : [],
    [defaultAgentRuntimeId, enabledRuntimes]
  )

  useEffect(() => {
    if (!profile) return
    form.resetFields()
    form.setFieldsValue({ agentRuntimeIds: initialAgentRuntimeIds })
  }, [form, initialAgentRuntimeIds, profile])

  return (
    <BaseModal
      busy={loading}
      destroyOnHidden
      footer={
        <Fragment>
          <Button disabled={loading} onClick={onCancel}>
            取消
          </Button>
          <Button
            disabled={loading || enabledRuntimes.length === 0}
            form={formId}
            htmlType="submit"
            loading={loading}
            type="primary"
          >
            开始测试
          </Button>
        </Fragment>
      }
      title="测试模型 Profile"
      visible={Boolean(profile)}
      onCancel={onCancel}
    >
      {profile ? (
        <div className={styles.profileContext}>
          <span className={styles.profileContextLabel}>当前 Profile</span>
          <span className={styles.profileContextValue}>{profile.name}</span>
        </div>
      ) : null}
      <Form<TestProfileFormValues>
        disabled={loading}
        form={form}
        id={formId}
        initialValues={{ agentRuntimeIds: initialAgentRuntimeIds }}
        layout="vertical"
        preserve={false}
        onFinish={(values) => {
          if (!loading) return onSubmit(values)
        }}
      >
        <Form.Item extra="最多选择 10 个 Agent Runtime" label="测试 Agent">
          <div className={styles.agentSelectToolbar}>
            <Checkbox
              checked={allAgentsSelected}
              disabled={loading || selectableAgentRuntimeIds.length === 0}
              indeterminate={selectedAgentRuntimeIds.length > 0 && !allAgentsSelected}
              onChange={(event) => {
                form.setFieldValue(
                  'agentRuntimeIds',
                  event.target.checked ? selectableAgentRuntimeIds : []
                )
              }}
            >
              {enabledRuntimes.length > 10 ? '全选前 10 个' : '全选'}
            </Checkbox>
            <span>已选 {selectedAgentRuntimeIds.length} 个</span>
          </div>
          <Form.Item
            name="agentRuntimeIds"
            noStyle
            rules={[
              {
                max: 10,
                message: '最多选择 10 个 Agent Runtime',
                min: 1,
                required: true,
                type: 'array'
              }
            ]}
          >
            <Checkbox.Group className={styles.agentOptions}>
              {enabledRuntimes.map((runtime) => (
                <Checkbox
                  className={styles.agentOption}
                  disabled={
                    loading ||
                    (selectedAgentRuntimeIds.length >= 10 &&
                      !selectedAgentRuntimeIds.includes(runtime.id))
                  }
                  key={runtime.id}
                  value={runtime.id}
                >
                  <span className={styles.agentName}>{runtime.name}</span>
                  <Tag bordered={false}>{runtime.agentType}</Tag>
                </Checkbox>
              ))}
            </Checkbox.Group>
          </Form.Item>
        </Form.Item>
      </Form>
    </BaseModal>
  )
}
