import { useState, useEffect } from 'react'
import { useAppStore } from './stores/appStore'
import EpisodeSelector from './components/EpisodeSelector'
import DialogueViewer from './components/DialogueViewer'
import TTSPanel from './components/TTSPanel'
import StatusBar from './components/StatusBar'

function App() {
  const { selectedEpisode, backendStatus, checkBackendStatus } = useAppStore()
  const [activeTab, setActiveTab] = useState<'episodes' | 'dubbing'>('episodes')

  useEffect(() => {
    checkBackendStatus()
    const interval = setInterval(checkBackendStatus, 10000)
    return () => clearInterval(interval)
  }, [checkBackendStatus])

  return (
    <div className="flex flex-col h-screen bg-ark-black">
      {/* 헤더 */}
      <header className="ark-header relative px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* 로고 아이콘 */}
          <div className="w-8 h-8 flex items-center justify-center">
            <svg viewBox="0 0 24 24" className="w-6 h-6 text-ark-orange" fill="currentColor">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
                    stroke="currentColor" strokeWidth="2" fill="none"/>
            </svg>
          </div>
          <h1 className="text-xl font-bold text-ark-white tracking-wide">
            <span className="text-ark-orange">AVT</span>
            <span className="text-ark-gray mx-2">|</span>
            <span className="text-sm font-normal">ARKNIGHTS VOICE TOOLS</span>
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${
              backendStatus === 'connected' ? 'bg-green-500' : 'bg-red-500'
            }`} />
            <span className={`text-sm ${
              backendStatus === 'connected' ? 'text-ark-gray' : 'text-red-400'
            }`}>
              {backendStatus === 'connected' ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
        </div>
      </header>

      {/* 탭 네비게이션 */}
      <nav className="bg-ark-dark px-6 py-2 border-b border-ark-border flex gap-2">
        <button
          className={`ark-tab ${activeTab === 'episodes' ? 'active' : ''}`}
          onClick={() => setActiveTab('episodes')}
        >
          에피소드 탐색
        </button>
        <button
          className={`ark-tab ${activeTab === 'dubbing' ? 'active' : ''}`}
          onClick={() => setActiveTab('dubbing')}
        >
          실시간 더빙
        </button>
      </nav>

      {/* 메인 컨텐츠 */}
      <main className="flex-1 flex overflow-hidden">
        {activeTab === 'episodes' && (
          <>
            {/* 왼쪽: 에피소드 목록 */}
            <aside className="w-80 bg-ark-dark border-r border-ark-border overflow-y-auto">
              <EpisodeSelector />
            </aside>

            {/* 중앙: 대사 뷰어 */}
            <section className="flex-1 overflow-y-auto bg-ark-black ark-pattern">
              {selectedEpisode ? (
                <DialogueViewer />
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-ark-gray">
                  <svg viewBox="0 0 24 24" className="w-16 h-16 mb-4 opacity-30" fill="currentColor">
                    <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
                  </svg>
                  <p>에피소드를 선택하세요</p>
                </div>
              )}
            </section>

            {/* 오른쪽: TTS 패널 */}
            <aside className="w-80 bg-ark-dark border-l border-ark-border overflow-y-auto">
              <TTSPanel />
            </aside>
          </>
        )}

        {activeTab === 'dubbing' && (
          <div className="flex-1 flex flex-col items-center justify-center text-ark-gray ark-pattern">
            <svg viewBox="0 0 24 24" className="w-20 h-20 mb-4 opacity-30" fill="currentColor">
              <path d="M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.48 6-3.3 6-6.72h-1.7z"/>
            </svg>
            <p className="text-lg mb-2">실시간 더빙</p>
            <p className="text-sm opacity-50">준비 중...</p>
          </div>
        )}
      </main>

      {/* 상태 바 */}
      <StatusBar />
    </div>
  )
}

export default App
