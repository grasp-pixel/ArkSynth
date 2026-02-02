import { useAppStore } from '../stores/appStore'

export default function StatusBar() {
  const { backendStatus, selectedEpisode, isPlaying, currentDialogue } = useAppStore()

  return (
    <footer className="ark-statusbar px-4 py-2 flex items-center justify-between text-xs">
      {/* 왼쪽: 현재 상태 */}
      <div className="flex items-center gap-6">
        {/* 서버 상태 */}
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              backendStatus === 'connected'
                ? 'bg-green-500'
                : backendStatus === 'checking'
                ? 'bg-yellow-500 ark-pulse'
                : 'bg-red-500'
            }`}
          />
          <span className="text-ark-gray uppercase tracking-wider">
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

        {/* 버전 */}
        <div className="text-ark-gray/50 tracking-wider">
          AVT v0.1.0
        </div>
      </div>
    </footer>
  )
}
