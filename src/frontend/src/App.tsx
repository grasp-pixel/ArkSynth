import { useState, useEffect } from 'react'
import { useAppStore } from './stores/appStore'
import EpisodeSelector from './components/EpisodeSelector'
import DialogueViewer from './components/DialogueViewer'
import TTSPanel from './components/TTSPanel'
import OCRPanel from './components/OCRPanel'
import StatusBar from './components/StatusBar'

function DubbingPreview() {
  const {
    isMonitoring,
    detectedText,
    detectedConfidence,
    capturedImage,
    playDialogue,
    isPlaying,
  } = useAppStore()

  const handlePlayDetected = () => {
    if (detectedText) {
      playDialogue({
        id: 'ocr-detected',
        speaker_id: null,
        speaker_name: '',
        text: detectedText,
        line_number: 0,
      })
    }
  }

  return (
    <div className="flex flex-col h-full p-6">
      {/* 상태 표시 */}
      <div className="mb-6">
        <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm ${
          isMonitoring
            ? 'bg-ark-orange/20 text-ark-orange border border-ark-orange/30'
            : 'bg-ark-panel text-ark-gray border border-ark-border'
        }`}>
          <span className={isMonitoring ? 'ark-pulse' : ''}>●</span>
          {isMonitoring ? '실시간 모니터링 중' : '대기 중'}
        </div>
      </div>

      {/* 캡처된 이미지 */}
      {capturedImage ? (
        <div className="mb-6">
          <h3 className="text-sm font-medium text-ark-gray mb-3">캡처된 화면</h3>
          <div className="border border-ark-border rounded overflow-hidden bg-ark-dark">
            <img
              src={`data:image/png;base64,${capturedImage}`}
              alt="Captured screen"
              className="w-full h-auto max-h-64 object-contain"
            />
          </div>
        </div>
      ) : (
        <div className="mb-6 flex flex-col items-center justify-center py-16 border border-dashed border-ark-border rounded bg-ark-dark/30">
          <svg viewBox="0 0 24 24" className="w-16 h-16 mb-4 text-ark-gray opacity-30" fill="currentColor">
            <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/>
          </svg>
          <p className="text-ark-gray text-sm">화면을 캡처하거나 모니터링을 시작하세요</p>
        </div>
      )}

      {/* 감지된 텍스트 */}
      {detectedText ? (
        <div className="flex-1">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-ark-gray">감지된 대사</h3>
            <span className="text-xs text-ark-gray">
              신뢰도: {(detectedConfidence * 100).toFixed(1)}%
            </span>
          </div>
          <div className="p-6 bg-ark-dark border border-ark-border rounded mb-4">
            <p className="text-lg text-ark-white leading-relaxed whitespace-pre-wrap">
              {detectedText}
            </p>
          </div>
          <button
            onClick={handlePlayDetected}
            disabled={isPlaying}
            className={`ark-btn ark-btn-primary w-full ${isPlaying ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {isPlaying ? (
              <span className="flex items-center justify-center gap-2">
                <span className="ark-pulse">▶</span> 재생 중...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                  <path d="M8 5v14l11-7z"/>
                </svg>
                TTS로 재생
              </span>
            )}
          </button>
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center text-ark-gray">
          <svg viewBox="0 0 24 24" className="w-12 h-12 mb-3 opacity-30" fill="currentColor">
            <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/>
          </svg>
          <p className="text-sm">아직 감지된 대사가 없습니다</p>
        </div>
      )}
    </div>
  )
}

function App() {
  const {
    selectedEpisode,
    backendStatus,
    checkBackendStatus,
    categories,
    selectedCategoryId,
    selectCategory,
    isLoadingCategories,
    loadCategories,
  } = useAppStore()
  const [activeTab, setActiveTab] = useState<'episodes' | 'dubbing'>('episodes')

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
      <main className="flex-1 flex flex-col overflow-hidden">
        {activeTab === 'episodes' && (
          <>
            {/* 카테고리 탭 - 전체 너비 */}
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

            {/* 컨텐츠 영역 */}
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
                  </div>
                )}
              </section>

              {/* 오른쪽: TTS 패널 */}
              <aside className="w-80 bg-ark-dark border-l border-ark-border overflow-y-auto">
                <TTSPanel />
              </aside>
            </div>
          </>
        )}

        {activeTab === 'dubbing' && (
          <div className="flex-1 flex overflow-hidden">
            {/* 왼쪽: OCR 패널 */}
            <aside className="w-80 bg-ark-dark border-r border-ark-border overflow-y-auto">
              <OCRPanel />
            </aside>

            {/* 중앙: 실시간 더빙 미리보기 */}
            <section className="flex-1 overflow-y-auto bg-ark-black ark-pattern">
              <DubbingPreview />
            </section>

            {/* 오른쪽: TTS 패널 */}
            <aside className="w-80 bg-ark-dark border-l border-ark-border overflow-y-auto">
              <TTSPanel />
            </aside>
          </div>
        )}
      </main>

      {/* 상태 바 */}
      <StatusBar />
    </div>
  )
}

export default App
