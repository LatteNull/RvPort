import { describe, expect, it } from 'vitest'

import {
  reportFindingTitleText,
  reportFindingTypeText,
  reportModuleBasisText
} from './reportPresentation'

describe('assessment report presentation mappings', () => {
  it.each([
    ['EXPLICIT_BUILD_TARGET', '显式构建目标'],
    ['nearest-build-descriptor', '按构建文件归类'],
    ['directory', '目录识别'],
    ['PROJECT_ROOT', '项目根模块'],
    ['BUILD_ARTIFACT', '构建产物识别']
  ])('maps module basis %s to Chinese', (value, expected) => {
    expect(reportModuleBasisText(value)).toBe(expected)
  })

  it.each([
    ['X86_COMMENT_HINT', 'x86 架构相关注释'],
    ['build-configuration', '构建配置'],
    ['HEADER', '专用头文件'],
    ['INTRINSIC', '内建函数'],
    ['VECTOR_TYPE', '向量类型']
  ])('maps finding type %s to Chinese', (value, expected) => {
    expect(reportFindingTypeText(value)).toBe(expected)
  })

  it('keeps unknown backend values readable instead of inventing a translation', () => {
    expect(reportFindingTypeText('FUTURE_KIND')).toBe('FUTURE_KIND')
    expect(reportModuleBasisText('FUTURE_BASIS')).toBe('FUTURE_BASIS')
  })

  it('maps a raw issue title when it is the display form of a known finding type', () => {
    expect(reportFindingTitleText('X86 Comment Hint', 'X86_COMMENT_HINT')).toBe('x86 架构相关注释')
    expect(reportFindingTitleText('需要人工确认的特殊问题', 'X86_COMMENT_HINT')).toBe(
      '需要人工确认的特殊问题'
    )
  })
})
