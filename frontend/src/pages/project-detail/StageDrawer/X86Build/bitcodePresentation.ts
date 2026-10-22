import type { ProjectBuildBitcodeReasonCode, ProjectBuildValidation } from '@/types/project'

const reasonLabels: Record<ProjectBuildBitcodeReasonCode, string> = {
  NONE: '',
  LEGACY_RECORD: '历史构建没有 Bitcode 记录',
  DISABLED: 'Bitcode 生成功能未启用',
  BUILD_FAILED: 'x86 构建未成功',
  NOT_SOURCE_X86: '该构建不在 x86 源环境运行',
  COMPILE_DATABASE_UNAVAILABLE: '没有可用的编译数据库',
  NO_C_CPP_TRANSLATION_UNITS: '没有可处理的 C/C++ 编译单元',
  TOOLCHAIN_BUNDLE_UNAVAILABLE: 'LLVM 工具链不可用',
  TOOLCHAIN_BUNDLE_INVALID: 'LLVM 工具链校验失败',
  TOOLCHAIN_CACHE_INVALID: 'LLVM 工具链缓存无效',
  TOOLCHAIN_LOCK_TIMEOUT: '等待 LLVM 工具链超时',
  TOOLCHAIN_UNSUPPORTED_ARCH: '远端架构不受工具链支持',
  TOOLCHAIN_VERSION_MISMATCH: 'LLVM 工具链版本不匹配',
  TRANSLATION_UNIT_LIMIT_EXCEEDED: '编译单元数量超过限制',
  DUPLICATE_CONTEXT: '编译单元上下文重复',
  TRANSLATION_UNIT_TIMEOUT: '编译单元处理超时',
  TRANSLATION_UNIT_FAILED: '部分编译单元生成失败',
  OUTPUT_SIZE_LIMIT_EXCEEDED: '生成制品超过大小限制',
  TRANSFER_FAILED: '制品传输失败',
  MANIFEST_INVALID: '制品清单校验失败',
  BUNDLE_INVALID: '制品包校验失败',
  STORAGE_FAILED: '制品保存失败',
  CANCELLED: '任务已取消',
  INTERNAL_ERROR: '生成过程发生错误'
}

export function getBitcodePresentation(build: Pick<ProjectBuildValidation, 'status' | 'bitcode'>) {
  if (build.status === 'PENDING' || build.status === 'QUEUED' || build.status === 'RUNNING') {
    return { label: '待生成', color: undefined, detail: 'x86 构建成功后将尝试生成 LLVM Bitcode。' }
  }

  const bitcode = build.bitcode
  if (!bitcode) {
    return { label: '未生成', color: undefined, detail: '这条构建记录没有 Bitcode 摘要。' }
  }

  const count =
    bitcode.plannedCount > 0
      ? `${bitcode.succeededCount}/${bitcode.plannedCount} 个编译单元成功` +
        (bitcode.failedCount > 0 ? `，${bitcode.failedCount} 个失败` : '') +
        (bitcode.skippedCount > 0 ? `，${bitcode.skippedCount} 个跳过` : '')
      : ''
  const reason = bitcode.reasonCode === 'NONE' ? '' : reasonLabels[bitcode.reasonCode]
  const protocolNote =
    bitcode.legacy || bitcode.schemaVersion !== '2.0'
      ? '旧版 Bitcode 制品，请重新构建生成 v2 制品后再执行专项分析'
      : ''

  switch (bitcode.status) {
    case 'READY':
      return {
        label: '已生成',
        color: 'green',
        detail: [count || 'Bitcode 已生成。', protocolNote].filter(Boolean).join('；')
      }
    case 'PARTIAL':
      return {
        label: '部分生成',
        color: 'gold',
        detail: [count, reason, protocolNote].filter(Boolean).join('；')
      }
    case 'FAILED':
      return {
        label: '生成失败',
        color: 'orange',
        detail: [count, reason].filter(Boolean).join('；') || 'Bitcode 生成失败。'
      }
    case 'UNSUPPORTED':
    case 'NOT_ATTEMPTED':
      return { label: '未生成', color: undefined, detail: reason || '未尝试生成 Bitcode。' }
  }
}
