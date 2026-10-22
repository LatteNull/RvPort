import babel from '@rolldown/plugin-babel'
import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// 日期断言使用统一时区，避免 Docker 默认 UTC 与开发机时区导致差异。
process.env.TZ = 'Asia/Shanghai'

export default defineConfig({
  plugins: [react(), babel({ presets: [reactCompilerPreset()] })],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  test: {
    // Ant Design 与 jsdom 的异步浮层在并行文件中会互相干扰，串行执行保证交付测试可复现。
    fileParallelism: false,
    environment: 'jsdom',
    maxWorkers: 1,
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}', 'scripts/**/*.mjs'],
      exclude: ['src/**/*.test.{ts,tsx}', 'src/**/*.d.ts', 'src/test/**'],
      reporter: ['text', 'json-summary', 'html', 'lcov'],
      thresholds: { lines: 90, branches: 90 }
    },
    setupFiles: ['./src/test/setup.ts'],
    testTimeout: 30_000,
    clearMocks: true,
    restoreMocks: true,
    mockReset: true
  }
})
