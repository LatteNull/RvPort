import { getProjectEvaluationReportInputs } from '@/api/project/assessment-report'
import { readAllPages } from '@/api/readAllPages'

export async function getAllEvaluationReportInputs(reportId: string, signal?: AbortSignal) {
  return (
    await readAllPages(
      (page, pageSize) =>
        getProjectEvaluationReportInputs(reportId, {
          inputType: 'MIGRATION_INPUT_REF',
          page,
          pageSize
        }),
      { signal }
    )
  ).items
}
