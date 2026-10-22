import { lazy, Suspense, useCallback, useEffect, useRef } from 'react'
import type { EditorProps, OnMount } from '@monaco-editor/react'

import ContentState from '@/components/ContentState'

import styles from './index.module.scss'

let monacoEditorLoadPromise: Promise<typeof import('@monaco-editor/react')> | undefined
const EMPTY_HIGHLIGHTED_LINE_NUMBERS: number[] = []
const EMPTY_HIGHLIGHTED_RANGES: MonacoEditorHighlightRange[] = []
const EMPTY_SOURCE_GAPS: MonacoEditorSourceGap[] = []
const LOAD_EARLIER_THROTTLE_MS = 500

export interface MonacoEditorHighlightRange {
  endColumn: number
  endLineNumber: number
  startColumn: number
  startLineNumber: number
}

export interface MonacoEditorSourceGap {
  afterLineNumber: number
  endLine: number
  error?: boolean
  id: string
  lineCount: number
  loadable?: boolean
  loading?: boolean
  onLoad?: () => void
  startLine: number
}

type MonacoEditorInstance = Parameters<OnMount>[0]
type MonacoOverlayWidget = Parameters<MonacoEditorInstance['addOverlayWidget']>[0]

function loadMonacoEditor() {
  monacoEditorLoadPromise ??= Promise.all([
    import('./configureMonaco'),
    import('@monaco-editor/react')
  ]).then(([, editorModule]) => editorModule)

  return monacoEditorLoadPromise
}

const MonacoEditorComponent = lazy(loadMonacoEditor)

interface MonacoEditorProps {
  ariaLabel?: string
  className?: string
  height?: EditorProps['height']
  hasEarlierContent?: boolean
  highlightedLineNumbers?: number[]
  highlightedRanges?: MonacoEditorHighlightRange[]
  isFetchingEarlierContent?: boolean
  language?: string
  lineNumbers?: number[]
  lineNumberOffset?: number
  onChange?: (value: string) => void
  onLoadEarlierContent?: () => unknown
  readOnly?: boolean
  revealLineKey?: number | string
  revealLineNumber?: number
  scrollToBottomOnValueChange?: boolean
  sourceGaps?: MonacoEditorSourceGap[]
  theme?: EditorProps['theme']
  totalLines?: number
  value?: string
  wordWrap?: 'on' | 'off'
}

export default function MonacoEditor({
  ariaLabel,
  className,
  height = '100%',
  hasEarlierContent = false,
  highlightedLineNumbers = EMPTY_HIGHLIGHTED_LINE_NUMBERS,
  highlightedRanges = EMPTY_HIGHLIGHTED_RANGES,
  isFetchingEarlierContent = false,
  language = 'shell',
  lineNumbers: explicitLineNumbers,
  lineNumberOffset = 1,
  onChange,
  onLoadEarlierContent,
  readOnly = false,
  revealLineKey,
  revealLineNumber,
  scrollToBottomOnValueChange = false,
  sourceGaps = EMPTY_SOURCE_GAPS,
  theme = 'rvport-light',
  totalLines,
  value = '',
  wordWrap = 'on'
}: MonacoEditorProps) {
  const editorClassName = [styles.editor, className].filter(Boolean).join(' ')
  const loadingClassName = [styles.loading, className].filter(Boolean).join(' ')
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null)
  const monacoRef = useRef<Parameters<OnMount>[1] | null>(null)
  const decorationIdsRef = useRef<string[]>([])
  const hasEarlierContentRef = useRef(hasEarlierContent)
  const isFetchingEarlierContentRef = useRef(isFetchingEarlierContent)
  const onLoadEarlierContentRef = useRef(onLoadEarlierContent)
  const loadEarlierInFlightRef = useRef(false)
  const lastLoadEarlierAtRef = useRef(0)
  const scrollRestoreRef = useRef<{ height: number; top: number } | null>(null)
  const scrollListenerRef = useRef<{ dispose: () => void } | null>(null)
  const sourceGapWidgetsRef = useRef<MonacoOverlayWidget[]>([])
  const viewZoneIdsRef = useRef<string[]>([])
  const maximumLineNumber =
    explicitLineNumbers?.reduce(
      (maximum, lineNumber) => Math.max(maximum, lineNumber),
      totalLines ?? lineNumberOffset
    ) ??
    totalLines ??
    lineNumberOffset
  const lineNumbersMinChars = Math.max(1, String(maximumLineNumber).length)

  useEffect(() => {
    hasEarlierContentRef.current = hasEarlierContent
    isFetchingEarlierContentRef.current = isFetchingEarlierContent
    onLoadEarlierContentRef.current = onLoadEarlierContent
  }, [hasEarlierContent, isFetchingEarlierContent, onLoadEarlierContent])

  const syncScrollPosition = useCallback(() => {
    const editor = editorRef.current
    if (!editor) return

    const restorePosition = scrollRestoreRef.current
    if (restorePosition) {
      editor.setScrollTop(
        Math.max(0, editor.getScrollHeight() - restorePosition.height + restorePosition.top)
      )
      scrollRestoreRef.current = null
    } else if (scrollToBottomOnValueChange) {
      editor.setScrollTop(editor.getScrollHeight())
    }
  }, [scrollToBottomOnValueChange])
  const applyHighlights = useCallback(() => {
    const editor = editorRef.current
    const monaco = monacoRef.current
    if (!editor || !monaco) return

    decorationIdsRef.current = editor.deltaDecorations(decorationIdsRef.current, [
      ...highlightedRanges.map((range) => ({
        range: new monaco.Range(
          range.startLineNumber,
          range.startColumn,
          range.endLineNumber,
          range.endColumn
        ),
        options: { inlineClassName: styles.highlightedRange }
      })),
      ...highlightedLineNumbers.map((lineNumber) => ({
        range: new monaco.Range(lineNumber, 1, lineNumber, 1),
        options: {
          className: styles.highlightedLine,
          isWholeLine: true,
          linesDecorationsClassName: styles.highlightedLineDecoration
        }
      }))
    ])
  }, [highlightedLineNumbers, highlightedRanges])
  const revealRequestedLine = useCallback(() => {
    const editor = editorRef.current
    const targetLine = revealLineNumber ?? highlightedLineNumbers[0]
    if (editor && targetLine) editor.revealLineInCenter(targetLine)
  }, [highlightedLineNumbers, revealLineNumber])
  const applySourceGaps = useCallback(() => {
    const editor = editorRef.current
    if (
      !editor ||
      (!sourceGaps.length && !viewZoneIdsRef.current.length && !sourceGapWidgetsRef.current.length)
    ) {
      return
    }

    sourceGapWidgetsRef.current.forEach((widget) => editor.removeOverlayWidget(widget))
    sourceGapWidgetsRef.current = []

    editor.changeViewZones((accessor) => {
      viewZoneIdsRef.current.forEach((id) => accessor.removeZone(id))
      viewZoneIdsRef.current = sourceGaps.map((gap) => {
        const zoneDomNode = document.createElement('div')
        zoneDomNode.className = styles.sourceGapZone

        const overlayNode = document.createElement('div')
        overlayNode.className = styles.sourceGap
        overlayNode.style.pointerEvents = 'auto'
        overlayNode.style.width = `calc(100% - ${editor.getLayoutInfo().contentLeft}px)`

        const message = document.createElement('span')
        message.textContent = `已省略 ${gap.lineCount} 行 · 第 ${gap.startLine}–${gap.endLine} 行`
        overlayNode.append(message)

        if (gap.loadable && gap.onLoad) {
          const button = document.createElement('button')
          button.className = styles.sourceGapAction
          button.disabled = Boolean(gap.loading)
          button.type = 'button'
          button.style.pointerEvents = 'auto'
          button.setAttribute('aria-label', `加载第 ${gap.startLine}–${gap.endLine} 行`)
          button.textContent = gap.loading ? '加载中…' : gap.error ? '重新加载' : '加载此段'
          button.addEventListener('pointerdown', (event) => event.stopPropagation())
          button.addEventListener('mousedown', (event) => event.stopPropagation())
          button.addEventListener('click', (event) => {
            event.preventDefault()
            event.stopPropagation()
            gap.onLoad?.()
          })
          overlayNode.append(button)
        }

        let top = -1_000_000
        const widget: MonacoOverlayWidget = {
          getDomNode: () => overlayNode,
          getId: () => `source-gap-${gap.id}`,
          getPosition: () => ({
            preference: { left: editor.getLayoutInfo().contentLeft, top }
          })
        }
        sourceGapWidgetsRef.current.push(widget)
        editor.addOverlayWidget(widget)

        return accessor.addZone({
          afterLineNumber: gap.afterLineNumber,
          domNode: zoneDomNode,
          heightInPx: 40,
          onDomNodeTop: (nextTop) => {
            top = nextTop
            overlayNode.style.visibility = nextTop < -10_000 ? 'hidden' : 'visible'
            editor.layoutOverlayWidget(widget)
          },
          suppressMouseDown: true
        })
      })
    })
  }, [sourceGaps])
  const handleMount = useCallback<OnMount>(
    (editor, monaco) => {
      editorRef.current = editor
      monacoRef.current = monaco
      scrollListenerRef.current?.dispose()
      scrollListenerRef.current = editor.onDidScrollChange((event) => {
        const now = Date.now()
        if (
          !event.scrollTopChanged ||
          editor.getScrollTop() > 32 ||
          !hasEarlierContentRef.current ||
          isFetchingEarlierContentRef.current ||
          loadEarlierInFlightRef.current ||
          now - lastLoadEarlierAtRef.current < LOAD_EARLIER_THROTTLE_MS ||
          !onLoadEarlierContentRef.current
        ) {
          return
        }

        loadEarlierInFlightRef.current = true
        lastLoadEarlierAtRef.current = now
        scrollRestoreRef.current = {
          height: editor.getScrollHeight(),
          top: editor.getScrollTop()
        }
        const loadResult = onLoadEarlierContentRef.current()
        void Promise.resolve(loadResult).then(
          () => {
            loadEarlierInFlightRef.current = false
          },
          () => {
            loadEarlierInFlightRef.current = false
          }
        )
      })
      applyHighlights()
      applySourceGaps()
      revealRequestedLine()
      syncScrollPosition()
    },
    [applyHighlights, applySourceGaps, revealRequestedLine, syncScrollPosition]
  )

  useEffect(() => {
    applyHighlights()
    applySourceGaps()
    syncScrollPosition()
  }, [applyHighlights, applySourceGaps, syncScrollPosition, value])

  useEffect(() => {
    void revealLineKey
    revealRequestedLine()
  }, [revealLineKey, revealRequestedLine])

  useEffect(
    () => () => {
      scrollListenerRef.current?.dispose()
      const editor = editorRef.current
      if (editor) {
        sourceGapWidgetsRef.current.forEach((widget) => editor.removeOverlayWidget(widget))
        sourceGapWidgetsRef.current = []
        if (viewZoneIdsRef.current.length) {
          editor.changeViewZones((accessor) => {
            viewZoneIdsRef.current.forEach((id) => accessor.removeZone(id))
            viewZoneIdsRef.current = []
          })
        }
      }
    },
    []
  )

  return (
    <Suspense
      fallback={
        <div
          aria-busy="true"
          aria-label={ariaLabel}
          className={loadingClassName}
          style={{ height }}
        >
          <ContentState kind="loading" description="正在加载源码编辑器" compact />
        </div>
      }
    >
      <div className={editorClassName} style={{ height }}>
        <MonacoEditorComponent
          height="100%"
          language={language}
          options={{
            ariaLabel,
            automaticLayout: true,
            fontSize: 14,
            folding: false,
            glyphMargin: false,
            guides: { highlightActiveIndentation: !readOnly },
            lineDecorationsWidth: 16,
            lineNumbers: (lineNumber) =>
              String(explicitLineNumbers?.[lineNumber - 1] ?? lineNumber + lineNumberOffset - 1),
            lineNumbersMinChars,
            minimap: { enabled: false },
            readOnly,
            renderLineHighlight: readOnly ? 'none' : 'line',
            scrollbar: {
              horizontalScrollbarSize: 8,
              horizontalSliderSize: 8,
              useShadows: false,
              verticalScrollbarSize: 8,
              verticalSliderSize: 8
            },
            scrollBeyondLastLine: false,
            wordWrap
          }}
          theme={theme}
          value={value}
          onChange={(nextValue) => onChange?.(nextValue ?? '')}
          onMount={handleMount}
        />
      </div>
    </Suspense>
  )
}
