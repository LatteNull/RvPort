import { EditOutlined } from '@ant-design/icons'
import { Alert, Button, Flex, Form, Select, Skeleton } from 'antd'

import { getStageStatus, modelStages } from '../presentation'
import type { BindingFormValues } from '../types'
import type { useModelProfiles } from '../useModelProfiles'

import styles from '../index.module.scss'

export default function ModelStageBindings({
  model
}: {
  model: ReturnType<typeof useModelProfiles>
}) {
  const {
    assignmentsQuery,
    assignments,
    modelProfilesStateQuery,
    agentRuntimesQuery,
    editingStage,
    setEditingStage,
    bindingMutation
  } = model
  return (
    <>
      {assignmentsQuery.isLoading ||
      modelProfilesStateQuery.isLoading ||
      agentRuntimesQuery.isLoading ? (
        <Skeleton active paragraph={{ rows: 3 }} />
      ) : assignmentsQuery.isError ||
        modelProfilesStateQuery.isError ||
        agentRuntimesQuery.isError ? (
        <Alert
          action={
            <Button
              type="link"
              onClick={() =>
                void Promise.all([
                  assignmentsQuery.refetch(),
                  modelProfilesStateQuery.refetch(),
                  agentRuntimesQuery.refetch()
                ])
              }
            >
              重试
            </Button>
          }
          className={styles.bindingError}
          message="无法加载模型绑定或可用选项"
          showIcon
          type="error"
        />
      ) : (
        <div className={styles.bindingList}>
          {modelStages.map((stagePresentation) => {
            const assignment = assignments.get(stagePresentation.stage)
            const currentProfile = modelProfilesStateQuery.data?.items.find(
              (profile) => profile.id === assignment?.modelProfileId
            )
            const stageStatus = getStageStatus(stagePresentation, assignment, currentProfile)
            const isEditing = editingStage === stagePresentation.stage

            return (
              <section
                aria-labelledby={`${stagePresentation.stage}-title`}
                className={styles.bindingSection}
                key={stagePresentation.stage}
              >
                <div className={styles.bindingOverview}>
                  <h2 className={styles.sectionTitle} id={`${stagePresentation.stage}-title`}>
                    {stagePresentation.title}
                  </h2>
                  <div
                    aria-live="polite"
                    className={`${styles.bindingHint} ${stageStatus.className}`}
                    role="status"
                  >
                    {stageStatus.text}
                  </div>
                </div>
                <div className={styles.bindingPanel}>
                  <Form<BindingFormValues>
                    className={styles.bindingControl}
                    initialValues={{
                      agentRuntimeId: assignment?.agentRuntimeId ?? undefined,
                      modelProfileId: assignment?.modelProfileId ?? undefined
                    }}
                    key={`${stagePresentation.stage}:${assignment?.modelProfileId ?? ''}:${assignment?.agentRuntimeId ?? ''}:${isEditing ? 'edit' : 'readonly'}`}
                    disabled={bindingMutation.isPending}
                    layout="vertical"
                    onFinish={(values) => {
                      bindingMutation.mutate({ ...values, stage: stagePresentation.stage })
                    }}
                  >
                    <Form.Item
                      className={styles.bindingFormItem}
                      label="模型 Profile"
                      name="modelProfileId"
                      rules={[{ required: true, message: '请选择模型 Profile' }]}
                    >
                      <Select
                        disabled={!isEditing || bindingMutation.isPending}
                        loading={modelProfilesStateQuery.isLoading}
                        options={(modelProfilesStateQuery.data?.items ?? []).map((profile) => ({
                          disabled: !profile.enabled,
                          label: `${profile.name} · ${profile.model || '未设置模型'}`,
                          value: profile.id
                        }))}
                        placeholder="请选择已启用的 Profile"
                      />
                    </Form.Item>
                    <Form.Item
                      className={styles.bindingFormItem}
                      label="Agent Runtime"
                      name="agentRuntimeId"
                      rules={[{ required: true, message: '请选择 Agent 运行时' }]}
                    >
                      <Select
                        disabled={!isEditing || bindingMutation.isPending}
                        loading={agentRuntimesQuery.isLoading}
                        options={(agentRuntimesQuery.data ?? []).map((runtime) => ({
                          disabled: !runtime.enabled,
                          label: `${runtime.name} · ${runtime.agentType}`,
                          value: runtime.id
                        }))}
                        placeholder="请选择已启用的 Agent 运行时"
                      />
                    </Form.Item>
                    <Flex className={styles.bindingActions} gap={4} justify="flex-end">
                      {isEditing ? (
                        <>
                          <Button onClick={() => setEditingStage(null)}>取消</Button>
                          <Button
                            htmlType="submit"
                            loading={
                              bindingMutation.isPending &&
                              bindingMutation.variables?.stage === stagePresentation.stage
                            }
                            type="primary"
                          >
                            保存
                          </Button>
                        </>
                      ) : (
                        <Button
                          icon={<EditOutlined />}
                          type={assignment ? 'text' : 'primary'}
                          disabled={bindingMutation.isPending}
                          onClick={() => setEditingStage(stagePresentation.stage)}
                        >
                          {assignment ? '修改' : '立即配置'}
                        </Button>
                      )}
                    </Flex>
                  </Form>
                </div>
              </section>
            )
          })}
        </div>
      )}
    </>
  )
}
