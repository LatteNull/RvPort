import { useQuery } from '@tanstack/react-query'

import {
  getProjectDependencyAnalysisArtifact,
  getProjectDependencyAnalysisArtifacts
} from '@/api/project/dependency-analysis'
import { useSessionMutation } from '@/hooks/useSessionMutation'
import type {
  ProjectDependencyAnalysis,
  ProjectDependencyAnalysisArtifact
} from '@/types/project/dependency-analysis'
import { feedback } from '@/utils/feedback'

import { projectQueryKeys } from '../../queryKeys'
import { artifactFileExtension } from './components/presentation'

export function useAnalysisArtifacts(analysis: ProjectDependencyAnalysis) {
  const artifactsQuery = useQuery({
    queryKey: projectQueryKeys.dependencyAnalysisArtifacts(analysis.id),
    queryFn: () => getProjectDependencyAnalysisArtifacts(analysis.id)
  })
  const downloadArtifactMutation = useSessionMutation({
    sessionKey: `artifact:${analysis.id}`,
    active: true,
    mutationFn: async (artifact: ProjectDependencyAnalysisArtifact, isCurrent) => {
      const detail = await getProjectDependencyAnalysisArtifact(analysis.id, artifact.artifactType)
      if (!isCurrent()) return
      const content =
        typeof detail.content === 'string'
          ? detail.content
          : JSON.stringify(detail.content, null, 2)
      const blob = new Blob([content], { type: detail.artifact.contentType })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${artifact.artifactType.toLowerCase()}.${artifactFileExtension(
        detail.artifact.contentType
      )}`
      document.body.append(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 0)
    },
    onError: () => feedback.error('分析制品下载失败')
  })
  return { artifactsQuery, downloadArtifactMutation }
}
