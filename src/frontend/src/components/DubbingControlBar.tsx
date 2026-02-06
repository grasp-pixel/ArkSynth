import { useMemo } from 'react'
import { useAppStore } from '../stores/appStore'
import { ocrApi } from '../services/api'

export default function DubbingControlBar() {
  const {
    isPrepared,
    isDubbingMode,
    selectedWindowHwnd,
    windows,
    loadWindows,
    setWindow,
    startDubbing,
    stopDubbing,
    isRendering,
  } = useAppStore()

  // 게임 관련 윈도우 우선 정렬 (훅은 조건부 return 전에 호출해야 함)
  const sortedWindows = useMemo(() => {
    const priorityKeywords = ['arknights', '명일방주', 'android', 'bluestacks', 'nox', 'ldplayer', 'mumu']
    return [...windows].sort((a, b) => {
      const aTitle = (a.title || '').toLowerCase()
      const bTitle = (b.title || '').toLowerCase()
      const aIsPriority = priorityKeywords.some(kw => aTitle.includes(kw))
      const bIsPriority = priorityKeywords.some(kw => bTitle.includes(kw))
      if (aIsPriority && !bIsPriority) return -1
      if (!aIsPriority && bIsPriority) return 1
      return 0
    })
  }, [windows])

  // 준비 안 됐으면 렌더링 안 함 (훅 호출 이후에 조건부 return)
  if (!isPrepared) return null

  return (
    <div className="bg-ark-dark border-t-2 border-ark-orange/30">
      <div className="flex items-center gap-4 px-4 py-4">
        {/* 윈도우 선택 */}
        <div className={`flex items-center gap-2 flex-[2] min-w-0 px-3 py-2 rounded-lg transition-all duration-300 ${
          !selectedWindowHwnd && !isDubbingMode
            ? 'bg-ark-orange/10 border-2 border-ark-orange/60 ark-pulse'
            : 'border-2 border-transparent'
        }`}>
          <div className={`flex items-center gap-2 ${!selectedWindowHwnd && !isDubbingMode ? 'text-ark-orange' : 'text-ark-gray'}`}>
            <svg viewBox="0 0 24 24" className="w-5 h-5 flex-shrink-0" fill="currentColor">
              <path d="M21 2H3c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h7v2H8v2h8v-2h-2v-2h7c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H3V4h18v12z"/>
            </svg>
            <label className="text-sm font-medium whitespace-nowrap">캡처 윈도우</label>
          </div>
          <select
            value={selectedWindowHwnd ?? ''}
            onChange={(e) => setWindow(Number(e.target.value))}
            className={`ark-input text-sm flex-1 min-w-0 ${
              !selectedWindowHwnd && !isDubbingMode
                ? 'border-ark-orange focus:border-ark-yellow'
                : ''
            }`}
            disabled={isDubbingMode}
          >
            <option value="">⚠ 윈도우를 선택하세요</option>
            {sortedWindows.map((win) => (
              <option key={win.hwnd} value={win.hwnd}>
                {win.title || `Window ${win.hwnd}`}
              </option>
            ))}
          </select>
          <button
            onClick={loadWindows}
            disabled={isDubbingMode}
            className="text-ark-gray hover:text-ark-orange p-1.5 disabled:opacity-50 transition-colors"
            title="윈도우 목록 새로고침"
          >
            <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
              <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
            </svg>
          </button>
        </div>

        {/* 미리보기 썸네일 - 대사 영역 + 자막 영역 */}
        {selectedWindowHwnd && (
          <div className="flex-1 min-w-0 flex gap-2">
            {/* 대사 영역 */}
            <div className="flex-1 bg-ark-black/50 border border-ark-border rounded overflow-hidden">
              <div className="px-1.5 py-0.5 bg-ark-panel/50 border-b border-ark-border">
                <span className="text-[10px] text-ark-orange">대사</span>
              </div>
              <img
                src={ocrApi.getWindowRegionImageUrl(selectedWindowHwnd, 'dialogue')}
                alt="대사 영역"
                className="w-full h-auto object-contain"
                key={`dialogue-${selectedWindowHwnd}-${Date.now()}`}
              />
            </div>
            {/* 자막 영역 */}
            <div className="flex-1 bg-ark-black/50 border border-ark-border rounded overflow-hidden">
              <div className="px-1.5 py-0.5 bg-ark-panel/50 border-b border-ark-border">
                <span className="text-[10px] text-purple-400">자막</span>
              </div>
              <img
                src={ocrApi.getWindowRegionImageUrl(selectedWindowHwnd, 'subtitle')}
                alt="자막 영역"
                className="w-full h-auto object-contain"
                key={`subtitle-${selectedWindowHwnd}-${Date.now()}`}
              />
            </div>
          </div>
        )}

        {/* 더빙 버튼 */}
        <div className="flex-shrink-0">
          {isDubbingMode ? (
            <button
              onClick={stopDubbing}
              className="ark-btn px-6 py-2 bg-red-500/20 text-red-400 border-red-400/30 hover:bg-red-500/30"
            >
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-red-400 ark-pulse" />
                더빙 중지
              </span>
            </button>
          ) : (
            <button
              onClick={startDubbing}
              disabled={!selectedWindowHwnd}
              className={`ark-btn-dual ark-corner-cut px-6 py-2.5 ${
                !selectedWindowHwnd ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              <span className="flex items-center gap-2">
                <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                  <path d="M8 5v14l11-7z"/>
                </svg>
                더빙 시작
              </span>
            </button>
          )}
        </div>
      </div>

      {/* 윈도우 미선택 경고 */}
      {!selectedWindowHwnd && !isDubbingMode && (
        <div className="mx-4 mb-3 ark-warning-box ark-corner-cut-sm flex items-center gap-2">
          <svg viewBox="0 0 24 24" className="w-5 h-5 text-ark-orange flex-shrink-0" fill="currentColor">
            <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
          </svg>
          <span className="text-sm text-ark-orange font-medium">
            더빙을 시작하려면 캡처할 윈도우를 먼저 선택하세요
          </span>
        </div>
      )}

      {/* VRAM 경고 - 사전 더빙 + 실시간 더빙 동시 실행 */}
      {isDubbingMode && isRendering && (
        <div className="mx-4 mb-3 bg-ark-yellow/10 border border-ark-yellow/30 rounded px-3 py-2 flex items-start gap-2">
          <svg viewBox="0 0 24 24" className="w-5 h-5 text-ark-yellow flex-shrink-0 mt-0.5" fill="currentColor">
            <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
          </svg>
          <div className="text-xs text-ark-yellow">
            <p className="font-medium">사전 더빙과 실시간 더빙 동시 실행 중</p>
            <p className="text-ark-yellow/70 mt-0.5">VRAM 부족 시 OCR 품질 저하 또는 크래시가 발생할 수 있습니다</p>
          </div>
        </div>
      )}
    </div>
  )
}
