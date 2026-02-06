import { useAppStore } from '../stores/appStore'
import { ocrApi } from '../services/api'

export default function DubbingDashboard() {
  const {
    isDubbingMode,
    isMonitoring,
    detectedText,
    detectedConfidence,
    matchedDialogue,
    matchSimilarity,
    isPlaying,
    currentDialogue,
    stopDubbing,
    stopPlayback,
    windows,
    selectedWindowHwnd,
    setWindow,
    loadWindows,
    startMonitoring,
    stopMonitoring,
    showCapturePreview,
    toggleCapturePreview,
    captureWindow,
    // 렌더링 상태
    isRendering,
    renderProgress,
    cancelRender,
    // 경고
    dubbingWarning,
  } = useAppStore()

  if (!isDubbingMode) {
    return null
  }

  const selectedWindow = windows.find((w) => w.hwnd === selectedWindowHwnd)

  // 캡처 이미지 URL
  const captureImageUrl = selectedWindowHwnd
    ? ocrApi.getWindowImageUrl(selectedWindowHwnd)
    : null

  return (
    <div className="bg-ark-dark border-t border-ark-border">
      {/* 렌더링 상태 바 */}
      {(isRendering || renderProgress) && (
        <div className="flex items-center gap-4 px-4 py-2 bg-ark-panel/50 border-b border-ark-border">
          <div className="flex items-center gap-2 text-sm">
            {isRendering ? (
              <>
                <span className="w-2 h-2 rounded-full bg-ark-orange ark-pulse" />
                <span className="text-ark-orange">렌더링 중</span>
              </>
            ) : renderProgress?.status === 'completed' ? (
              <>
                <span className="w-2 h-2 rounded-full bg-green-500" />
                <span className="text-green-400">렌더링 완료</span>
              </>
            ) : null}
          </div>

          {renderProgress && (
            <>
              <div className="flex-1 flex items-center gap-3">
                {/* 진행률 바 */}
                <div className="flex-1 h-1.5 bg-ark-border rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 ${
                      isRendering ? 'bg-ark-orange' : 'bg-green-500'
                    }`}
                    style={{ width: `${renderProgress.progress_percent}%` }}
                  />
                </div>
                {/* 진행률 텍스트 */}
                <span className="text-xs text-ark-gray min-w-16">
                  {renderProgress.completed}/{renderProgress.total}
                  <span className="ml-1">
                    ({renderProgress.progress_percent.toFixed(0)}%)
                  </span>
                </span>
              </div>

              {/* 현재 렌더링 중인 대사 */}
              {isRendering && renderProgress.current_text && (
                <div className="flex items-center gap-2 text-xs text-ark-gray max-w-48 truncate">
                  <span className="text-ark-white">{renderProgress.current_index}:</span>
                  <span className="truncate">{renderProgress.current_text}</span>
                </div>
              )}

              {/* 취소 버튼 */}
              {isRendering && (
                <button
                  onClick={cancelRender}
                  className="text-xs text-ark-gray hover:text-ark-white"
                >
                  취소
                </button>
              )}
            </>
          )}
        </div>
      )}

      <div className="flex items-center gap-4 p-4">
        {/* 윈도우 정보 */}
        <div className="flex items-center gap-3 min-w-48">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${
              isMonitoring ? 'bg-green-500 ark-pulse' : 'bg-ark-gray'
            }`} />
            <span className="text-ark-white text-sm font-medium">
              {selectedWindow?.title || '윈도우 없음'}
            </span>
          </div>
          {isMonitoring ? (
            <span className="text-xs text-green-400">모니터링 중</span>
          ) : (
            <span className="text-xs text-ark-gray">대기</span>
          )}
        </div>

        {/* 구분선 */}
        <div className="w-px h-10 bg-ark-border" />

        {/* OCR 결과 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-ark-gray">OCR:</span>
            {detectedText ? (
              <>
                <span className="text-ark-white text-sm truncate max-w-xs">
                  {detectedText}
                </span>
                <span className="text-xs text-ark-gray">
                  ({(detectedConfidence * 100).toFixed(0)}%)
                </span>
              </>
            ) : (
              <span className="text-ark-gray text-sm">대기 중...</span>
            )}
          </div>

          {/* 매칭 결과 */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-ark-gray">매칭:</span>
            {matchedDialogue ? (
              <>
                {matchedDialogue.speaker_name && (
                  <span className="text-ark-orange text-sm font-medium">
                    [{matchedDialogue.speaker_name}]
                  </span>
                )}
                <span className="text-ark-white text-sm truncate max-w-xs">
                  {matchedDialogue.text}
                </span>
                <span className="text-xs text-green-400">
                  ({(matchSimilarity * 100).toFixed(0)}%)
                </span>
              </>
            ) : (
              <span className="text-ark-gray text-sm">-</span>
            )}
          </div>
        </div>

        {/* 구분선 */}
        <div className="w-px h-10 bg-ark-border" />

        {/* 재생 상태 */}
        <div className="flex items-center gap-3 min-w-48">
          {isPlaying && currentDialogue ? (
            <div className="flex items-center gap-2">
              <span className="text-ark-orange ark-pulse">▶</span>
              <span className="text-ark-white text-sm truncate max-w-24">
                {currentDialogue.speaker_name || '나레이터'}
              </span>
            </div>
          ) : dubbingWarning ? (
            <span className="text-yellow-500 text-xs">{dubbingWarning}</span>
          ) : (
            <span className="text-ark-gray text-sm">재생 대기</span>
          )}
        </div>

        {/* 구분선 */}
        <div className="w-px h-10 bg-ark-border" />

        {/* 컨트롤 버튼 */}
        <div className="flex items-center gap-2">
          {/* 미리보기 토글 */}
          <button
            onClick={toggleCapturePreview}
            className={`ark-btn text-sm px-3 py-1.5 ${
              showCapturePreview ? 'bg-ark-orange/20 border-ark-orange/50' : ''
            }`}
            title="캡처 미리보기"
          >
            <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
              <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/>
            </svg>
          </button>

          {/* 캡처 버튼 */}
          <button
            onClick={captureWindow}
            disabled={!selectedWindowHwnd}
            className="ark-btn text-sm px-3 py-1.5"
            title="캡처"
          >
            <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
              <path d="M9.4 10.5l4.77-8.26C13.47 2.09 12.75 2 12 2c-2.4 0-4.6.85-6.32 2.25l3.66 6.35.06-.1zM21.54 9c-.92-2.92-3.15-5.26-6-6.34L11.88 9h9.66zm.26 1h-7.49l.29.5 4.76 8.25C21 16.97 22 14.61 22 12c0-.69-.07-1.35-.2-2zM8.54 12l-3.9-6.75C3.01 7.03 2 9.39 2 12c0 .69.07 1.35.2 2h7.49l-1.15-2zm-6.08 3c.92 2.92 3.15 5.26 6 6.34L12.12 15H2.46zm11.27 0l-3.9 6.76c.7.15 1.42.24 2.17.24 2.4 0 4.6-.85 6.32-2.25l-3.66-6.35-.93 1.6z"/>
            </svg>
          </button>

          {isMonitoring ? (
            <button
              onClick={stopMonitoring}
              className="ark-btn text-sm px-3 py-1.5"
              title="모니터링 일시정지"
            >
              <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
              </svg>
            </button>
          ) : (
            <button
              onClick={startMonitoring}
              className="ark-btn text-sm px-3 py-1.5"
              title="모니터링 재개"
            >
              <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                <path d="M8 5v14l11-7z"/>
              </svg>
            </button>
          )}

          {isPlaying && (
            <button
              onClick={stopPlayback}
              className="ark-btn text-sm px-3 py-1.5 bg-red-600/50 hover:bg-red-600/70 border-red-500/50"
              title="재생 중지"
            >
              <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                <path d="M6 6h12v12H6z"/>
              </svg>
            </button>
          )}

          <button
            onClick={stopDubbing}
            className="ark-btn text-sm px-4 py-1.5 bg-ark-panel hover:bg-ark-panel/80"
          >
            종료
          </button>
        </div>
      </div>

      {/* 윈도우 선택 (미선택 시) */}
      {!selectedWindowHwnd && (
        <div className="px-4 pb-4">
          <div className="flex items-center gap-2 p-3 bg-ark-orange/10 border border-ark-orange/30 rounded">
            <svg viewBox="0 0 24 24" className="w-5 h-5 text-ark-orange flex-shrink-0" fill="currentColor">
              <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
            </svg>
            <span className="text-ark-orange text-sm">캡처할 윈도우를 선택해주세요</span>
            <select
              value=""
              onChange={(e) => setWindow(Number(e.target.value))}
              className="ark-input text-sm py-1 px-2 ml-auto"
            >
              <option value="">윈도우 선택...</option>
              {windows.map((win) => (
                <option key={win.hwnd} value={win.hwnd}>
                  {win.title || `Window ${win.hwnd}`}
                </option>
              ))}
            </select>
            <button onClick={loadWindows} className="text-ark-gray hover:text-ark-white text-sm">
              새로고침
            </button>
          </div>
        </div>
      )}

      {/* 캡처 미리보기 */}
      {showCapturePreview && captureImageUrl && (
        <div className="px-4 pb-4">
          <div className="bg-ark-black/50 border border-ark-border rounded overflow-hidden">
            <img
              src={captureImageUrl}
              alt="캡처 미리보기"
              className="w-full h-48 object-contain"
              key={Date.now()}  // 강제 새로고침
            />
          </div>
        </div>
      )}
    </div>
  )
}
