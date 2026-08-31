import { spawn } from 'node:child_process'
import { rmSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const e2eDir = dirname(fileURLToPath(import.meta.url))
const frontendDir = resolve(e2eDir, '..')
const runtimeDir = join(frontendDir, '.e2e', 'runtime')
const playwrightCli = join(frontendDir, 'node_modules', '@playwright', 'test', 'cli.js')
const playwright = spawn(process.execPath, [playwrightCli, 'test', ...process.argv.slice(2)], {
  cwd: frontendDir,
  env: process.env,
  stdio: 'inherit',
  windowsHide: true,
})

for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
  process.on(signal, () => {
    if (!playwright.killed) playwright.kill(signal)
  })
}

let exitCode = 1
try {
  exitCode = await new Promise((resolveCode, reject) => {
    playwright.once('error', reject)
    playwright.once('exit', code => resolveCode(code ?? 1))
  })
} catch (error) {
  console.error(error)
} finally {
  rmSync(runtimeDir, { recursive: true, force: true })
}

process.exitCode = exitCode
