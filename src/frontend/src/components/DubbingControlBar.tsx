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

  // 선택된 윈도우 미리보기 URL
  const previewImageUrl = selectedWindowHwnd
    ? ocrApi.getWindowImageUrl(selectedWindowHwnd)
    : null

  // 준비 안 됐으면 렌더링 안 함 (훅 호출 이후에 조건부 return)
  if (!isPrepared) return null

  return (
    <div className="bg-ark-dark border-t-2 border-ark-orange/30">
      <div className="flex items-center gap-4 px-4 py-4">
        {/* 윈도우 선택 */}
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <label className="text-sm text-ark-gray whitespace-nowrap">캡처 윈도우:</label>
          <select
            value={selectedWindowHwnd ?? ''}
            onChange={(e) => setWindow(Number(e.target.value))}
            className="ark-input text-sm flex-1 min-w-0"
            disabled={isDubbingMode}
          >
            <option value="">윈도우 선택...</option>
            {sortedWindows.map((win) => (
              <option key={win.hwnd} value={win.hwnd}>
                {win.title || `Window ${win.hwnd}`}
              </option>
            ))}
          </select>
          <button
            onClick={loadWindows}
            disabled={isDubbingMode}
            className="text-ark-gray hover:text-ark-white p-1 disabled:opacity-50"
            title="윈도우 목록 새로고침"
          >
            <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
              <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
            </svg>
          </button>
        </div>

        {/* 미리보기 썸네일 */}
        {previewImageUrl && (
          <div className="w-24 h-14 bg-ark-black/50 border border-ark-border rounded overflow-hidden flex-shrink-0">
            <img
              src={previewImageUrl}
              alt="윈도우 미리보기"
              className="w-full h-full object-contain"
              key={`preview-${selectedWindowHwnd}-${Date.now()}`}
            />
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
              className={`ark-btn ark-btn-primary px-6 py-2 font-bold ${
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
        <div className="px-4 pb-2 text-xs text-ark-yellow">
          * 캡처할 윈도우를 선택하세요
        </div>
      )}
    </div>
  )
}
