import { loader } from '@monaco-editor/react'
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api.js'
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import jsonWorker from 'monaco-editor/esm/vs/language/json/json.worker?worker'

import 'monaco-editor/esm/vs/basic-languages/cpp/cpp.contribution.js'
import 'monaco-editor/esm/vs/basic-languages/shell/shell.contribution.js'
import 'monaco-editor/esm/vs/language/json/monaco.contribution.js'

interface MonacoEnvironmentConfig {
  getWorker: (_moduleId: string, label: string) => Worker
}

const monacoGlobal = self as typeof self & { MonacoEnvironment?: MonacoEnvironmentConfig }

monacoGlobal.MonacoEnvironment = {
  getWorker(_moduleId, label) {
    if (label === 'json') return new jsonWorker()

    return new editorWorker()
  }
}

monaco.editor.defineTheme('rvport-light', {
  base: 'vs',
  inherit: true,
  rules: [],
  colors: {
    'scrollbarSlider.activeBackground': '#1c1f3547',
    'scrollbarSlider.background': '#1c1f3529',
    'scrollbarSlider.hoverBackground': '#1c1f3547'
  }
})

loader.config({ monaco })
