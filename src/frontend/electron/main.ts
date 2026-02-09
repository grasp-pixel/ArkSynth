import { app, BrowserWindow, ipcMain, session, Menu, globalShortcut } from 'electron'
import path from 'path'

// 개발 모드 확인
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged

// 백엔드 서버 URL
const BACKEND_URL = 'http://127.0.0.1:8000'

let mainWindow: BrowserWindow | null = null

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    // 타이틀바 스타일
    titleBarStyle: 'default',
    backgroundColor: '#1a1a2e',
  })

  // CSP 설정: 백엔드 서버의 이미지 허용
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          `default-src 'self' 'unsafe-inline' 'unsafe-eval'; ` +
          `img-src 'self' data: blob: ${BACKEND_URL}; ` +
          `media-src 'self' blob: ${BACKEND_URL}; ` +
          `connect-src 'self' ${BACKEND_URL} ws://localhost:*; ` +
          `font-src 'self' data:; ` +
          `style-src 'self' 'unsafe-inline';`
        ],
      },
    })
  })

  // 개발 모드: Vite 개발 서버
  // 프로덕션: 빌드된 파일
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// 앱 준비 완료
app.whenReady().then(() => {
  // 메뉴 바 제거
  Menu.setApplicationMenu(null)

  createWindow()

  // 개발 모드: DevTools 단축키 등록
  if (isDev) {
    globalShortcut.register('CommandOrControl+Shift+I', () => {
      mainWindow?.webContents.openDevTools()
    })
    globalShortcut.register('F12', () => {
      mainWindow?.webContents.openDevTools()
    })
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

// 앱 종료 전 백엔드 셧다운 요청
app.on('before-quit', () => {
  // fire-and-forget으로 백엔드 종료 신호 전송
  const http = require('http')
  const req = http.request({
    hostname: '127.0.0.1',
    port: 8000,
    path: '/api/settings/shutdown',
    method: 'POST',
    timeout: 3000,
  })
  req.on('error', () => {})  // 이미 종료되었을 수 있으므로 에러 무시
  req.end()
})

// 모든 윈도우 닫힘
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// IPC 핸들러
ipcMain.handle('get-app-path', () => {
  return app.getAppPath()
})

ipcMain.handle('get-version', () => {
  return app.getVersion()
})

ipcMain.handle('restart-app', () => {
  app.relaunch()
  app.quit()
})
