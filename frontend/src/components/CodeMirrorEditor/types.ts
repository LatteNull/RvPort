export type CodeLanguage = 'cpp' | 'json' | 'plaintext' | 'shell'

export interface CodeMirrorEditorProps {
  ariaLabel?: string
  className?: string
  height?: number | string
  highlightedLineNumbers?: number[]
  language?: CodeLanguage
  onChange?: (value: string) => void
  readOnly?: boolean
  value?: string
}
