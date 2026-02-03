import { useState } from 'react'
import { useAppStore } from '../stores/appStore'

export default function StatusBar() {
  const {
    backendStatus,
    selectedEpisode,
    isPlaying,
    currentDialogue,
    volume,
    isMuted,
    setVolume,
    toggleMute
  } = useAppStore()

  const [showVolumeSlider, setShowVolumeSlider] = useState(false)

  return (
    <footer className="ark-statusbar px-4 py-2 flex items-center justify-between text-xs">
      {/* 왼쪽: 현재 상태 */}
      <div className="flex items-center gap-6">
        {/* 서버 상태 */}
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              backendStatus === 'connected'
                ? 'bg-ark-cyan'
                : backendStatus === 'checking'
                ? 'bg-yellow-500 ark-pulse'
                : 'bg-red-500'
            }`}
          />
          <span className={`uppercase tracking-wider ${
            backendStatus === 'connected' ? 'text-ark-cyan' : 'text-ark-gray'
          }`}>
            {backendStatus === 'connected'
              ? 'Connected'
              : backendStatus === 'checking'
              ? 'Checking...'
              : 'Disconnected'}
          </span>
        </div>

        {/* 현재 에피소드 */}
        {selectedEpisode && (
          <div className="flex items-center gap-2 text-ark-gray">
            <svg viewBox="0 0 24 24" className="w-3.5 h-3.5" fill="currentColor">
              <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
            </svg>
            <span>{selectedEpisode.id}</span>
          </div>
        )}
      </div>

      {/* 오른쪽: 재생 상태 */}
      <div className="flex items-center gap-6">
        {isPlaying && currentDialogue && (
          <div className="flex items-center gap-2 text-ark-orange">
            <span className="ark-pulse">▶</span>
            <span className="max-w-xs truncate">
              {currentDialogue.speaker_name || 'Narration'}:{' '}
              {currentDialogue.text.slice(0, 30)}...
            </span>
          </div>
        )}

        {/* 볼륨 조절 */}
        <div
          className="relative flex items-center gap-1"
          onMouseEnter={() => setShowVolumeSlider(true)}
          onMouseLeave={() => setShowVolumeSlider(false)}
        >
          {/* 볼륨 슬라이더 (호버 시 표시) */}
          <div className={`absolute right-full mr-2 transition-all duration-200 ${
            showVolumeSlider ? 'opacity-100 visible' : 'opacity-0 invisible'
          }`}>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={isMuted ? 0 : volume}
              onChange={(e) => {
                const newVolume = parseFloat(e.target.value)
                setVolume(newVolume)
                if (newVolume > 0 && isMuted) toggleMute()
              }}
              className="w-20 h-1 bg-ark-black rounded-lg appearance-none cursor-pointer accent-ark-cyan"
            />
          </div>

          {/* 음소거/볼륨 버튼 */}
          <button
            onClick={toggleMute}
            className="p-1 text-ark-gray hover:text-ark-white transition-colors"
            title={isMuted ? '음소거 해제' : '음소거'}
          >
            {isMuted || volume === 0 ? (
              <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
              </svg>
            ) : volume < 0.5 ? (
              <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                <path d="M18.5 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM5 9v6h4l5 5V4L9 9H5z"/>
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
              </svg>
            )}
          </button>

          {/* 볼륨 수치 (호버 시) */}
          {showVolumeSlider && (
            <span className="text-ark-gray font-mono text-xs w-8">
              {Math.round((isMuted ? 0 : volume) * 100)}%
            </span>
          )}
        </div>

        {/* 버전 */}
        <div className="text-ark-gray/50 tracking-wider">
          ArkSynth v0.1.0
        </div>
      </div>
    </footer>
  )
}
