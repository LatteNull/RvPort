import { useMemo } from 'react'
import { cpp } from '@codemirror/lang-cpp'
import { json } from '@codemirror/lang-json'
import { StreamLanguage } from '@codemirror/language'
import { shell } from '@codemirror/legacy-modes/mode/shell'
import { RangeSetBuilder, StateField } from '@codemirror/state'
import { Decoration, EditorView } from '@codemirror/view'
import CodeMirror from '@uiw/react-codemirror'

import type { CodeLanguage, CodeMirrorEditorProps } from './types'

import styles from './index.module.scss'

const EMPTY_HIGHLIGHTED_LINE_NUMBERS: number[] = []

function getLanguageExtension(language: CodeLanguage) {
  if (language === 'cpp') return cpp()
  if (language === 'json') return json()
  if (language === 'shell') return StreamLanguage.define(shell)
  return []
}

function createHighlightedLineExtension(lineNumbersToHighlight: number[]) {
  const highlightedLine = Decoration.line({ class: styles.highlightedLine })

  return StateField.define({
    create(state) {
      const builder = new RangeSetBuilder<Decoration>()

      Array.from(new Set(lineNumbersToHighlight))
        .filter(
          (lineNumber) =>
            Number.isInteger(lineNumber) && lineNumber > 0 && lineNumber <= state.doc.lines
        )
        .sort((left, right) => left - right)
        .forEach((lineNumber) => {
          builder.add(
            state.doc.line(lineNumber).from,
            state.doc.line(lineNumber).from,
            highlightedLine
          )
        })

      return builder.finish()
    },
    update(value) {
      return value
    },
    provide: (field) => EditorView.decorations.from(field)
  })
}

export default function CodeMirrorEditorImpl({
  ariaLabel,
  className,
  height = '100%',
  highlightedLineNumbers = EMPTY_HIGHLIGHTED_LINE_NUMBERS,
  language = 'shell',
  onChange,
  readOnly = false,
  value = ''
}: CodeMirrorEditorProps) {
  const editorClassName = [styles.editor, className].filter(Boolean).join(' ')
  const extensions = useMemo(
    () => [
      getLanguageExtension(language),
      ...(ariaLabel ? [EditorView.contentAttributes.of({ 'aria-label': ariaLabel })] : []),
      EditorView.lineWrapping,
      createHighlightedLineExtension(highlightedLineNumbers)
    ],
    [ariaLabel, highlightedLineNumbers, language]
  )

  return (
    <CodeMirror
      basicSetup={{ foldGutter: false, highlightActiveLine: false, lineNumbers: true }}
      className={editorClassName}
      extensions={extensions}
      height={typeof height === 'number' ? `${height}px` : height}
      indentWithTab
      readOnly={readOnly}
      value={value}
      onChange={onChange}
    />
  )
}
