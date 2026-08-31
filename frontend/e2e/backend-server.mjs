import { rmSync } from 'node:fs'
import { spawn, spawnSync } from 'node:child_process'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const e2eDir = dirname(fileURLToPath(import.meta.url))
const frontendDir = resolve(e2eDir, '..')
const repoDir = resolve(frontendDir, '..')
const backendDir = join(repoDir, 'backend')
const runtimeDir = join(frontendDir, '.e2e', 'runtime')
const python = process.env.JLU_E2E_PYTHON?.trim() || (process.platform === 'win32'
  ? join(backendDir, '.venv', 'Scripts', 'python.exe')
  : join(backendDir, '.venv', 'bin', 'python'))
const environment = {
  ...process.env,
  JLU_ENVIRONMENT: 'test',
  JLU_APP_DATA_DIR: runtimeDir,
  JLU_HOST: '127.0.0.1',
  JLU_PORT: '8010',
  JLU_CORS_ORIGINS: '["http://127.0.0.1:4173"]',
}

rmSync(runtimeDir, { recursive: true, force: true })
const seeded = spawnSync(python, [join(e2eDir, 'seed.py')], {
  cwd: backendDir,
  env: environment,
  stdio: 'inherit',
  windowsHide: true,
})
if (seeded.status !== 0) process.exit(seeded.status ?? 1)

const backend = spawn(python, ['-m', 'app', 'serve', '--host', '127.0.0.1', '--port', '8010'], {
  cwd: backendDir,
  env: environment,
  stdio: 'inherit',
  windowsHide: true,
})

let stopping = false
function cleanupRuntime() {
  rmSync(runtimeDir, { recursive: true, force: true })
}

function stop(signal = 'SIGTERM') {
  if (stopping) return
  stopping = true
  if (!backend.killed) backend.kill(signal)
}

for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.on(signal, () => stop(signal))
backend.on('exit', code => {
  cleanupRuntime()
  process.exit(code ?? 0)
})
process.on('exit', () => {
  stop()
  cleanupRuntime()
})
