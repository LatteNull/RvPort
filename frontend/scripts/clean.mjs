import { access, rm } from 'node:fs/promises'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = resolve(fileURLToPath(new URL('..', import.meta.url)))
const removeDependencies = process.argv.includes('--all')
const targets = ['dist', 'coverage', 'dist-ssr']

if (removeDependencies) {
  targets.push('node_modules', '.pnpm-store')
}

async function removeTarget(target) {
  const targetPath = resolve(rootDir, target)

  if (!targetPath.startsWith(`${rootDir}/`)) {
    throw new Error(`Refusing to remove a path outside the frontend root: ${target}`)
  }

  try {
    await access(targetPath)
  } catch {
    return false
  }

  await rm(targetPath, { force: true, recursive: true })
  console.log(`Removed ${target}`)
  return true
}

console.log(
  `Cleaning ${removeDependencies ? 'build artifacts and dependencies' : 'build artifacts'}...`
)

const removed = await Promise.all(targets.map(removeTarget))
const count = removed.filter(Boolean).length

console.log(`Cleanup complete: removed ${count} target${count === 1 ? '' : 's'}.`)
