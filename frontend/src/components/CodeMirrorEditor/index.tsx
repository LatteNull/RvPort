import { lazy, Suspense } from 'react'

import type { CodeMirrorEditorProps } from './types'

import styles from './index.module.scss'

const CodeMirrorEditorImpl = lazy(() => import('./CodeMirrorEditorImpl'))

export default function CodeMirrorEditor({
  ariaLabel,
  className,
  height = '100%',
  highlightedLineNumbers,
  language = 'shell',
  onChange,
  readOnly = false,
  value = ''
}: CodeMirrorEditorProps) {
  const editorClassName = [styles.editor, className].filter(Boolean).join(' ')

  return (
    <Suspense
      fallback={
        <div
          aria-busy="true"
          aria-label={ariaLabel}
          className={editorClassName}
          style={{ height }}
        />
      }
    >
      <CodeMirrorEditorImpl
        ariaLabel={ariaLabel}
        className={className}
        height={height}
        highlightedLineNumbers={highlightedLineNumbers}
        language={language}
        readOnly={readOnly}
        value={value}
        onChange={onChange}
      />
    </Suspense>
  )
}
