import { useEffect } from 'react'
import { useAppStore } from './stores/appStore'
import EpisodeSelector from './components/EpisodeSelector'
import DialogueViewer from './components/DialogueViewer'
import VoiceSetupPanel from './components/VoiceSetupPanel'
import DubbingDashboard from './components/DubbingDashboard'
import StatusBar from './components/StatusBar'

function App() {
  const {
    selectedEpisode,
    selectedGroupId,
    backendStatus,
    checkBackendStatus,
    categories,
    selectedCategoryId,
    selectCategory,
    isLoadingCategories,
    loadCategories,
    isDubbingMode,
    isPrepared,
    prepareForDubbing,
    isLoadingCharacters,
  } = useAppStore()

  useEffect(() => {
    checkBackendStatus()
    const interval = setInterval(checkBackendStatus, 10000)
    return () => clearInterval(interval)
  }, [checkBackendStatus])

  useEffect(() => {
    if (backendStatus === 'connected') {
      loadCategories()
    }
  }, [backendStatus, loadCategories])

  // 준비 버튼 핸들러
  const handlePrepare = () => {
    if (!selectedGroupId) {
      alert('스토리 그룹을 먼저 선택하세요')
      return
    }
    prepareForDubbing()
  }

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
          {/* 더빙 상태 표시 */}
          {isDubbingMode && (
            <div className="flex items-center gap-2 px-4 py-2 rounded bg-ark-orange text-ark-black font-medium">
              <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.91-3c-.49 0-.9.36-.98.85C16.52 14.2 14.47 16 12 16s-4.52-1.8-4.93-4.15c-.08-.49-.49-.85-.98-.85-.61 0-1.09.54-1 1.14.49 3 2.89 5.35 5.91 5.78V20c0 .55.45 1 1 1s1-.45 1-1v-2.08c3.02-.43 5.42-2.78 5.91-5.78.1-.6-.39-1.14-1-1.14z"/>
              </svg>
              <span>더빙 중</span>
              <span className="w-2 h-2 rounded-full bg-ark-black ark-pulse" />
            </div>
          )}

          {/* 백엔드 상태 */}
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

      {/* 카테고리 탭 */}
      <div className="flex border-b border-ark-border bg-ark-dark">
        {isLoadingCategories ? (
          <div className="p-3 text-ark-gray text-sm ark-pulse">로딩 중...</div>
        ) : (
          categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => selectCategory(cat.id)}
              className={`px-5 py-3 text-sm font-medium whitespace-nowrap transition-all border-b-2 ${
                selectedCategoryId === cat.id
                  ? 'bg-ark-orange/10 text-ark-orange border-ark-orange'
                  : 'text-ark-gray hover:text-ark-white hover:bg-ark-panel/50 border-transparent'
              }`}
            >
              {cat.name}
              <span className="ml-1.5 text-xs opacity-70">({cat.group_count})</span>
            </button>
          ))
        )}
      </div>

      {/* 메인 컨텐츠 */}
      <main className={`flex-1 flex flex-col overflow-hidden transition-all ${
        isDubbingMode ? 'pb-16' : ''
      }`}>
        <div className="flex-1 flex overflow-hidden">
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
                {!selectedGroupId && (
                  <p className="mt-2 text-sm text-ark-gray/70">
                    왼쪽 목록에서 스토리 그룹을 펼쳐 에피소드를 선택하세요
                  </p>
                )}
              </div>
            )}
          </section>

          {/* 오른쪽: 조건부 패널 */}
          <aside className="w-80 bg-ark-dark border-l border-ark-border overflow-y-auto flex flex-col">
            {isPrepared ? (
              <VoiceSetupPanel />
            ) : (
              <div className="flex flex-col h-full">
                {/* 준비 버튼 */}
                <div className="p-4 border-b border-ark-border bg-ark-panel/50">
                  <button
                    onClick={handlePrepare}
                    disabled={!selectedGroupId || isLoadingCharacters}
                    className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded font-bold transition-all ${
                      selectedGroupId && !isLoadingCharacters
                        ? 'bg-ark-orange text-ark-black hover:bg-ark-orange/90'
                        : 'bg-ark-panel border border-ark-border text-ark-gray/50 cursor-not-allowed'
                    }`}
                  >
                    {isLoadingCharacters ? (
                      <span className="ark-pulse">로딩 중...</span>
                    ) : (
                      <>
                        <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                          <path d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
                        </svg>
                        <span>더빙 준비</span>
                      </>
                    )}
                  </button>
                  {!selectedGroupId && (
                    <p className="mt-2 text-xs text-ark-gray text-center">
                      스토리 그룹을 먼저 선택하세요
                    </p>
                  )}
                </div>

                {/* 안내 */}
                <div className="flex-1 p-4 space-y-4">
                  <div className="p-4 bg-ark-black/50 border border-ark-border rounded text-xs text-ark-gray space-y-3">
                    <h4 className="font-medium text-ark-white flex items-center gap-2">
                      <svg viewBox="0 0 24 24" className="w-4 h-4 text-ark-orange" fill="currentColor">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
                      </svg>
                      사용 방법
                    </h4>
                    <p className="flex items-start gap-2">
                      <span className="text-ark-orange font-bold">1.</span>
                      왼쪽에서 스토리 그룹을 선택하세요
                    </p>
                    <p className="flex items-start gap-2">
                      <span className="text-ark-orange font-bold">2.</span>
                      에피소드를 선택하여 대사를 확인하세요
                    </p>
                    <p className="flex items-start gap-2">
                      <span className="text-ark-orange font-bold">3.</span>
                      "더빙 준비" 버튼을 눌러 설정을 시작하세요
                    </p>
                    <p className="flex items-start gap-2">
                      <span className="text-ark-orange font-bold">4.</span>
                      캐릭터 음성 모델을 학습하고 더빙을 시작하세요
                    </p>
                  </div>
                </div>
              </div>
            )}
          </aside>
        </div>
      </main>

      {/* 더빙 대시보드 (더빙 모드 시 하단 고정) */}
      <DubbingDashboard />

      {/* 상태 바 */}
      <StatusBar />
    </div>
  )
}

export default App
