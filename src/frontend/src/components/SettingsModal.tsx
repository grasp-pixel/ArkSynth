import { useEffect, useState } from 'react'
import { settingsApi, type SettingsResponse, type DependencyStatus, type FFmpegInstallGuide, type SevenZipInstallGuide } from '../services/api'
import GPTSoVITSInstallDialog from './GPTSoVITSInstallDialog'

interface SettingsModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [settings, setSettings] = useState<SettingsResponse | null>(null)
  const [ffmpegGuide, setFFmpegGuide] = useState<FFmpegInstallGuide | null>(null)
  const [sevenZipGuide, setSevenZipGuide] = useState<SevenZipInstallGuide | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showFFmpegGuide, setShowFFmpegGuide] = useState(false)
  const [show7ZipGuide, setShow7ZipGuide] = useState(false)
  const [showGptSovitsInstall, setShowGptSovitsInstall] = useState(false)

  useEffect(() => {
    if (isOpen) {
      loadSettings()
    }
  }, [isOpen])

  const loadSettings = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await settingsApi.getSettings()
      setSettings(data)
    } catch (err) {
      setError('설정을 불러오는데 실패했습니다')
      console.error(err)
    } finally {
      setIsLoading(false)
    }
  }

  const loadFFmpegGuide = async () => {
    try {
      const guide = await settingsApi.getFFmpegGuide()
      setFFmpegGuide(guide)
      setShowFFmpegGuide(true)
    } catch (err) {
      console.error(err)
    }
  }

  const load7ZipGuide = async () => {
    try {
      const guide = await settingsApi.get7ZipGuide()
      setSevenZipGuide(guide)
      setShow7ZipGuide(true)
    } catch (err) {
      console.error(err)
    }
  }

  const handleOpenFolder = async (path: string) => {
    try {
      await settingsApi.openFolder(path)
    } catch (err) {
      console.error('폴더 열기 실패:', err)
    }
  }

  const refreshDependencies = async () => {
    try {
      const data = await settingsApi.checkDependencies()
      if (settings) {
        setSettings({ ...settings, dependencies: data.dependencies })
      }
    } catch (err) {
      console.error(err)
    }
  }

  if (!isOpen) return null

  const getDependencyIcon = (dep: DependencyStatus) => {
    if (dep.installed) {
      return (
        <span className="w-5 h-5 flex items-center justify-center rounded-full bg-green-500/20 text-green-400">
          <svg viewBox="0 0 24 24" className="w-3 h-3" fill="currentColor">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
          </svg>
        </span>
      )
    }
    return (
      <span className="w-5 h-5 flex items-center justify-center rounded-full bg-red-500/20 text-red-400">
        <svg viewBox="0 0 24 24" className="w-3 h-3" fill="currentColor">
          <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
        </svg>
      </span>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 오버레이 */}
      <div
        className="absolute inset-0 bg-black/70"
        onClick={onClose}
      />

      {/* 모달 */}
      <div className="relative bg-ark-dark border border-ark-border rounded-lg w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        {/* 헤더 */}
        <div className="p-4 border-b border-ark-border flex items-center justify-between">
          <h2 className="text-lg font-bold text-ark-white flex items-center gap-2">
            <svg viewBox="0 0 24 24" className="w-5 h-5 text-ark-orange" fill="currentColor">
              <path d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
            </svg>
            설정
          </h2>
          <button
            onClick={onClose}
            className="text-ark-gray hover:text-ark-white transition-colors"
          >
            <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>

        {/* 컨텐츠 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <span className="text-ark-gray ark-pulse">로딩 중...</span>
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <p className="text-red-400 mb-4">{error}</p>
              <button
                onClick={loadSettings}
                className="ark-btn ark-btn-secondary text-sm"
              >
                다시 시도
              </button>
            </div>
          ) : settings && (
            <>
              {/* 의존성 상태 */}
              <section>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-medium text-ark-white">의존성</h3>
                  <button
                    onClick={refreshDependencies}
                    className="text-xs text-ark-gray hover:text-ark-white"
                  >
                    새로고침
                  </button>
                </div>
                <div className="space-y-2">
                  {settings.dependencies.map((dep) => (
                    <div
                      key={dep.name}
                      className="flex items-center justify-between p-3 bg-ark-black/50 rounded border border-ark-border"
                    >
                      <div className="flex items-center gap-3">
                        {getDependencyIcon(dep)}
                        <div>
                          <p className="text-sm text-ark-white font-medium">{dep.name}</p>
                          {dep.installed ? (
                            <p className="text-xs text-ark-gray">
                              {dep.version && `v${dep.version}`}
                              {dep.path && ` • ${dep.path}`}
                            </p>
                          ) : (
                            <p className="text-xs text-red-400">미설치</p>
                          )}
                        </div>
                      </div>
                      {!dep.installed && dep.name === 'FFmpeg' && (
                        <button
                          onClick={loadFFmpegGuide}
                          className="text-xs text-ark-orange hover:underline"
                        >
                          설치 방법
                        </button>
                      )}
                      {!dep.installed && dep.name === 'FFprobe' && (
                        <span className="text-xs text-ark-gray">FFmpeg에 포함</span>
                      )}
                      {!dep.installed && dep.name === '7-Zip' && (
                        <button
                          onClick={load7ZipGuide}
                          className="text-xs text-ark-orange hover:underline"
                        >
                          설치 방법
                        </button>
                      )}
                      {!dep.installed && dep.name === 'GPT-SoVITS' && (
                        <button
                          onClick={() => setShowGptSovitsInstall(true)}
                          className="text-xs text-ark-orange hover:underline"
                        >
                          자동 설치
                        </button>
                      )}
                    </div>
                  ))}
                </div>

                {/* FFmpeg 설치 가이드 */}
                {showFFmpegGuide && ffmpegGuide && (
                  <div className="mt-3 p-4 bg-ark-panel rounded border border-ark-border">
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="text-sm font-medium text-ark-white">FFmpeg 설치 방법</h4>
                      <button
                        onClick={() => setShowFFmpegGuide(false)}
                        className="text-ark-gray hover:text-ark-white"
                      >
                        <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                          <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                        </svg>
                      </button>
                    </div>

                    {/* winget 방법 */}
                    <div className="mb-4">
                      <p className="text-xs text-ark-gray mb-2">Windows (winget 사용):</p>
                      <div className="flex items-center gap-2">
                        <code className="flex-1 px-3 py-2 bg-ark-black rounded text-sm text-ark-white font-mono">
                          {ffmpegGuide.windows.command}
                        </code>
                        <button
                          onClick={() => navigator.clipboard.writeText(ffmpegGuide.windows.command)}
                          className="px-3 py-2 bg-ark-black rounded text-ark-gray hover:text-ark-white"
                          title="복사"
                        >
                          <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                            <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
                          </svg>
                        </button>
                      </div>
                    </div>

                    {/* 수동 설치 */}
                    <div>
                      <p className="text-xs text-ark-gray mb-2">수동 설치:</p>
                      <ol className="text-xs text-ark-white space-y-1">
                        {ffmpegGuide.manual_steps.map((step, i) => (
                          <li key={i}>{step}</li>
                        ))}
                      </ol>
                    </div>
                  </div>
                )}

                {/* 7-Zip 설치 가이드 */}
                {show7ZipGuide && sevenZipGuide && (
                  <div className="mt-3 p-4 bg-ark-panel rounded border border-ark-border">
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="text-sm font-medium text-ark-white">7-Zip 설치 방법</h4>
                      <button
                        onClick={() => setShow7ZipGuide(false)}
                        className="text-ark-gray hover:text-ark-white"
                      >
                        <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                          <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                        </svg>
                      </button>
                    </div>

                    {/* 안내 메시지 */}
                    <div className="mb-4 p-2 bg-blue-500/10 border border-blue-500/30 rounded">
                      <p className="text-xs text-blue-400">{sevenZipGuide.note}</p>
                    </div>

                    {/* winget 방법 */}
                    <div className="mb-4">
                      <p className="text-xs text-ark-gray mb-2">Windows (winget 사용):</p>
                      <div className="flex items-center gap-2">
                        <code className="flex-1 px-3 py-2 bg-ark-black rounded text-sm text-ark-white font-mono">
                          {sevenZipGuide.windows.command}
                        </code>
                        <button
                          onClick={() => navigator.clipboard.writeText(sevenZipGuide.windows.command)}
                          className="px-3 py-2 bg-ark-black rounded text-ark-gray hover:text-ark-white"
                          title="복사"
                        >
                          <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                            <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
                          </svg>
                        </button>
                      </div>
                    </div>

                    {/* 수동 설치 */}
                    <div>
                      <p className="text-xs text-ark-gray mb-2">수동 설치:</p>
                      <ol className="text-xs text-ark-white space-y-1">
                        {sevenZipGuide.manual_steps.map((step, i) => (
                          <li key={i}>{step}</li>
                        ))}
                      </ol>
                    </div>
                  </div>
                )}
              </section>

              {/* 경로 설정 */}
              <section>
                <h3 className="text-sm font-medium text-ark-white mb-3">경로</h3>
                <div className="space-y-2">
                  <PathItem
                    label="GPT-SoVITS"
                    path={settings.gpt_sovits_path}
                    onOpen={() => handleOpenFolder(settings.gpt_sovits_path)}
                  />
                  <PathItem
                    label="모델"
                    path={settings.models_path}
                    onOpen={() => handleOpenFolder(settings.models_path)}
                  />
                  <PathItem
                    label="추출된 음성"
                    path={settings.extracted_path}
                    onOpen={() => handleOpenFolder(settings.extracted_path)}
                  />
                  <PathItem
                    label="게임 데이터"
                    path={settings.gamedata_path}
                    onOpen={() => handleOpenFolder(settings.gamedata_path)}
                  />
                </div>
              </section>

              {/* 언어 설정 */}
              <section>
                <h3 className="text-sm font-medium text-ark-white mb-3">언어</h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 bg-ark-black/50 rounded border border-ark-border">
                    <p className="text-xs text-ark-gray mb-1">게임 언어</p>
                    <p className="text-sm text-ark-white">{settings.game_language}</p>
                  </div>
                  <div className="p-3 bg-ark-black/50 rounded border border-ark-border">
                    <p className="text-xs text-ark-gray mb-1">GPT-SoVITS 언어</p>
                    <p className="text-sm text-ark-white">{settings.gpt_sovits_language}</p>
                  </div>
                </div>
              </section>
            </>
          )}
        </div>

        {/* 푸터 */}
        <div className="p-4 border-t border-ark-border">
          <button
            onClick={onClose}
            className="w-full ark-btn ark-btn-secondary"
          >
            닫기
          </button>
        </div>
      </div>

      {/* GPT-SoVITS 설치 다이얼로그 */}
      <GPTSoVITSInstallDialog
        isOpen={showGptSovitsInstall}
        onClose={() => setShowGptSovitsInstall(false)}
        onInstallComplete={() => {
          refreshDependencies()
          setShowGptSovitsInstall(false)
        }}
      />
    </div>
  )
}

// 경로 아이템 컴포넌트
function PathItem({ label, path, onOpen }: { label: string; path: string; onOpen: () => void }) {
  return (
    <div className="flex items-center justify-between p-3 bg-ark-black/50 rounded border border-ark-border">
      <div className="flex-1 min-w-0 mr-3">
        <p className="text-xs text-ark-gray mb-1">{label}</p>
        <p className="text-sm text-ark-white truncate" title={path}>{path}</p>
      </div>
      <button
        onClick={onOpen}
        className="flex-shrink-0 px-3 py-1.5 text-xs text-ark-gray hover:text-ark-white bg-ark-panel rounded border border-ark-border hover:border-ark-orange transition-colors"
      >
        열기
      </button>
    </div>
  )
}
