import { app, BrowserWindow, dialog } from 'electron'
import { execSync, spawn } from 'child_process'
import fs from 'fs'
import http from 'http'
import path from 'path'
import { fileURLToPath, pathToFileURL } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const isPackaged = app.isPackaged
const isDev = !isPackaged

let mainWindow
let backendProcess
let backendStderr = ''
let logFile = ''
let isQuitting = false
let restartTimer = null

function initLog() {
  logFile = path.join(app.getPath('userData'), 'backend.log')
  try {
    fs.mkdirSync(path.dirname(logFile), { recursive: true })
    fs.appendFileSync(logFile, `\n--- ${new Date().toISOString()} session ---\n`)
  } catch (err) {
    console.error('Could not create log file:', err)
  }
}

function log(msg) {
  const line = `${new Date().toISOString()} ${msg}`
  console.log(line)
  if (!logFile) return
  try {
    fs.appendFileSync(logFile, `${line}\n`)
  } catch (err) {
    console.error('Log write failed:', err)
  }
}

function getBackendExePath() {
  if (isPackaged) {
    return path.join(process.resourcesPath, 'stock-signal-backend.exe')
  }
  return path.join(__dirname, '..', 'backend', 'dist', 'stock-signal-backend.exe')
}

function getDevPythonPath() {
  return path.join(__dirname, '..', 'backend', 'venv', 'Scripts', 'python.exe')
}

function showBackendStartupError(message) {
  log(`ERROR DIALOG: ${message}`)
  dialog.showErrorBox('Stock Signal Analyzer - Startup Error', message)
}

function freePort8000() {
  if (process.platform !== 'win32') return

  log('Freeing port 8000 if in use...')
  try {
    const out = execSync('netstat -ano | findstr :8000 | findstr LISTENING', {
      encoding: 'utf8',
      windowsHide: true,
    })
    for (const line of out.trim().split('\n')) {
      const parts = line.trim().split(/\s+/)
      const pid = parts[parts.length - 1]
      if (pid && /^\d+$/.test(pid)) {
        execSync(`taskkill /F /PID ${pid}`, { windowsHide: true, stdio: 'ignore' })
        log(`Killed PID ${pid} on port 8000`)
      }
    }
  } catch {
    log('No process listening on port 8000')
  }
}

async function waitForBackend(url, timeout = 60000) {
  const start = Date.now()

  while (Date.now() - start < timeout) {
    try {
      await new Promise((resolve, reject) => {
        const req = http.get(url, (res) => {
          res.resume()
          resolve()
        })
        req.on('error', reject)
        req.setTimeout(3000, () => {
          req.destroy(new Error('Backend health check timed out'))
        })
      })
      log(`Backend healthy at ${url}`)
      return true
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 1000))
    }
  }

  throw new Error('Backend did not start in time')
}

function scheduleBackendRestart(code, signal) {
  if (isQuitting || restartTimer) return
  log(`Backend exited with code ${code} signal=${signal ?? 'none'}, restarting in 2 seconds...`)
  restartTimer = setTimeout(() => {
    restartTimer = null
    if (isQuitting) return
    freePort8000()
    if (startBackend()) {
      waitForBackend('http://127.0.0.1:8000/health', 60000).catch((err) => {
        log(`Backend restart health check failed: ${err.message}`)
      })
    }
  }, 2000)
}

function attachBackendLogs() {
  backendProcess.on('error', (err) => {
    log(`ERROR: ${err.message}`)
    if (!isQuitting) {
      showBackendStartupError(`Backend failed to start: ${err.message}`)
    }
  })

  backendProcess.stderr?.on('data', (data) => {
    const text = data.toString()
    backendStderr += text
    log(`STDERR: ${text.trim()}`)
  })

  backendProcess.stdout?.on('data', (data) => {
    log(`STDOUT: ${data.toString().trim()}`)
  })

  backendProcess.on('exit', (code, signal) => {
    log(`EXIT: code=${code} signal=${signal ?? 'none'}`)
    backendProcess = null
    scheduleBackendRestart(code, signal)
  })
}

function startBackend() {
  const backendExe = getBackendExePath()
  const useExe = isPackaged || fs.existsSync(backendExe)

  log('App starting...')
  log(`Packaged: ${isPackaged}`)
  log(`Resources path: ${process.resourcesPath}`)
  log(`Backend exe: ${backendExe}`)
  log(`Backend exe exists: ${fs.existsSync(backendExe)}`)
  log(`Log file: ${logFile}`)

  if (useExe) {
    if (!fs.existsSync(backendExe)) {
      const msg =
        `Backend not found at:\n${backendExe}\n\n` +
        'Rebuild the app with: npm run build-electron'
      showBackendStartupError(msg)
      return false
    }

    const modelsDir = path.join(app.getPath('userData'), 'models')
    fs.mkdirSync(modelsDir, { recursive: true })

    backendProcess = spawn(backendExe, [], {
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: {
        ...process.env,
        STOCK_SIGNAL_MODELS_DIR: modelsDir,
      },
    })
    log(`Spawned PyInstaller backend PID: ${backendProcess.pid ?? 'unknown'}`)
    attachBackendLogs()
    return true
  }

  // Dev fallback: venv + uvicorn (when dist exe not built yet)
  const pythonPath = getDevPythonPath()
  const backendPath = path.join(__dirname, '..', 'backend')

  log(`Dev Python path: ${pythonPath}`)
  if (!fs.existsSync(pythonPath)) {
    showBackendStartupError(
      `Backend exe missing and dev Python not found.\n\n` +
        `Build backend: cd backend && pyinstaller stock_signal_backend.spec --clean\n` +
        `Or create venv: run INSTALL.bat`,
    )
    return false
  }

  backendProcess = spawn(
    pythonPath,
    ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000'],
    {
      cwd: backendPath,
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  )
  log(`Spawned dev Python backend PID: ${backendProcess.pid ?? 'unknown'}`)
  attachBackendLogs()
  return true
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    title: 'Stock Signal Analyzer',
    icon: path.join(__dirname, 'public', 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: isDev,
    },
    backgroundColor: '#0d1117',
    show: false,
  })

  if (isDev) {
    mainWindow.loadURL('http://127.0.0.1:3000')
  } else {
    mainWindow.loadURL(
      pathToFileURL(path.join(__dirname, 'app-ui', 'index.html')).toString(),
    )
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    log('Main window shown')
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.commandLine.appendSwitch('disable-features', 'BlockInsecurePrivateNetworkRequests')

app.whenReady().then(async () => {
  initLog()
  freePort8000()

  if (!startBackend()) {
    app.quit()
    return
  }

  try {
    await waitForBackend('http://127.0.0.1:8000/health', 60000)
  } catch (err) {
    const backendExe = getBackendExePath()
    const details = backendStderr.trim()
      ? `\n\nServer output:\n${backendStderr.trim().slice(-2000)}`
      : ''
    showBackendStartupError(
      `The analysis backend did not start within 60 seconds.\n\n` +
        `Backend: ${backendExe}\n` +
        `Error: ${err.message}${details}\n\n` +
        `See log: ${logFile}\n\n` +
        'Ensure port 8000 is not in use by another program.',
    )
    if (backendProcess) backendProcess.kill()
    app.quit()
    return
  }

  createWindow()
})

app.on('before-quit', () => {
  isQuitting = true
  if (restartTimer) {
    clearTimeout(restartTimer)
    restartTimer = null
  }
  if (backendProcess) backendProcess.kill()
})

app.on('window-all-closed', () => {
  app.quit()
})
