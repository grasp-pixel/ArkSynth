export {}

declare global {
  interface Window {
    electronAPI: {
      getAppPath: () => Promise<string>
      getVersion: () => Promise<string>
      restartApp: () => Promise<void>
    }
  }
}
