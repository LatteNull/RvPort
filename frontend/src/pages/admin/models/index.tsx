import { lazy, Suspense, useRef } from 'react'
import { PlusOutlined } from '@ant-design/icons'
import { Button } from 'antd'

import type { BaseTableHandle } from '@/components/BaseTable'

import ModelProfileTable from './components/ModelProfileTable'
import ModelStageBindings from './components/ModelStageBindings'
import { useModelProfiles } from './useModelProfiles'

import styles from './index.module.scss'

const ModelProfileModal = lazy(() => import('./components/ModelProfileModal'))
const TestProfileModal = lazy(() => import('./components/TestProfileModal'))

export default function AdminModelsPage() {
  const tableRef = useRef<BaseTableHandle>(null)
  const model = useModelProfiles(tableRef)
  const {
    modalProfile,
    setModalProfile,
    testModalProfile,
    setTestModalProfile,
    assignments,
    agentRuntimesQuery,
    saveProfileMutation,
    agentProbeMutation
  } = model

  return (
    <section className={styles.page}>
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.title}>模型配置</h1>
          <p className={styles.description}>
            配置各业务阶段使用的模型服务，并验证其 Agent 兼容性。
          </p>
        </div>
      </div>

      <ModelStageBindings model={model} />

      <section aria-labelledby="profiles-title" className={styles.profilesSection}>
        <div className={styles.profilesHeader}>
          <div>
            <h2 className={styles.sectionTitle} id="profiles-title">
              模型 Profile
            </h2>
            <p className={styles.sectionDescription}>
              密钥仅在提交时发送给服务端，后续只显示是否已配置。
            </p>
          </div>
          <Button
            className={styles.createProfileButton}
            icon={<PlusOutlined />}
            type="primary"
            onClick={() => setModalProfile(null)}
          >
            新增 Profile
          </Button>
        </div>
        <div className={styles.tableArea}>
          <ModelProfileTable model={model} tableRef={tableRef} />
        </div>
      </section>

      {modalProfile !== undefined ? (
        <Suspense fallback={null}>
          <ModelProfileModal
            loading={saveProfileMutation.isPending}
            profile={modalProfile}
            visible
            onCancel={() => setModalProfile(undefined)}
            onSubmit={async (values) => {
              await saveProfileMutation.mutateAsync(values)
            }}
          />
        </Suspense>
      ) : null}
      {testModalProfile ? (
        <Suspense fallback={null}>
          <TestProfileModal
            agentRuntimes={agentRuntimesQuery.data ?? []}
            defaultAgentRuntimeId={
              assignments.get('TEST_LOG_COMPARE')?.agentRuntimeId ??
              assignments.get('KB_AI_EXTENSION')?.agentRuntimeId ??
              undefined
            }
            loading={agentProbeMutation.isPending}
            profile={testModalProfile}
            onCancel={() => setTestModalProfile(null)}
            onSubmit={async ({ agentRuntimeIds }) => {
              await agentProbeMutation.mutateAsync({
                agentRuntimeIds,
                profileId: testModalProfile.id
              })
            }}
          />
        </Suspense>
      ) : null}
    </section>
  )
}
