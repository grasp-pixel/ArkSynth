import { contextBridge, ipcRenderer } from 'electron'

// 렌더러 프로세스에 노출할 API
contextBridge.exposeInMainWorld('electronAPI', {
  getAppPath: () => ipcRenderer.invoke('get-app-path'),
  getVersion: () => ipcRenderer.invoke('get-version'),
  restartApp: () => ipcRenderer.invoke('restart-app'),
})

// 타입 선언 (전역)
declare global {
  interface Window {
    electronAPI: {
      getAppPath: () => Promise<string>
      getVersion: () => Promise<string>
      restartApp: () => Promise<void>
    }
  }
}
