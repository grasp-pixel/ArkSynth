import { useAppStore } from '../stores/appStore'
import type { DialogueInfo } from '../services/api'

export default function DialogueViewer() {
  const {
    selectedEpisode,
    isLoadingEpisode,
    playDialogue,
    isPlaying,
    currentDialogue,
  } = useAppStore()

  if (isLoadingEpisode) {
    return (
      <div className="flex items-center justify-center h-full text-ark-gray">
        <div className="ark-pulse">로딩 중...</div>
      </div>
    )
  }

  if (!selectedEpisode) {
    return (
      <div className="flex items-center justify-center h-full text-ark-gray">
        에피소드를 선택하세요
      </div>
    )
  }

  const handlePlayClick = (dialogue: DialogueInfo) => {
    if (!isPlaying || currentDialogue?.id !== dialogue.id) {
      playDialogue(dialogue)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div className="p-5 border-b border-ark-border bg-ark-dark/80 backdrop-blur">
        <h2 className="text-lg font-bold text-ark-white">
          {selectedEpisode.title || selectedEpisode.id}
        </h2>
        <div className="flex items-center gap-4 text-sm text-ark-gray mt-2">
          <span className="flex items-center gap-1">
            <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
              <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
            </svg>
            {selectedEpisode.dialogues.length}개 대사
          </span>
          <span className="flex items-center gap-1">
            <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
              <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
            </svg>
            {selectedEpisode.characters.length}명 캐릭터
          </span>
        </div>
      </div>

      {/* 대사 목록 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {selectedEpisode.dialogues.map((dialogue, index) => (
          <DialogueItem
            key={dialogue.id}
            dialogue={dialogue}
            index={index}
            isPlaying={isPlaying && currentDialogue?.id === dialogue.id}
            onPlay={() => handlePlayClick(dialogue)}
          />
        ))}
      </div>
    </div>
  )
}

interface DialogueItemProps {
  dialogue: DialogueInfo
  index: number
  isPlaying: boolean
  onPlay: () => void
}

function DialogueItem({ dialogue, index, isPlaying, onPlay }: DialogueItemProps) {
  const isNarration = !dialogue.speaker_name

  return (
    <div
      className={`ark-dialogue ${isPlaying ? 'playing' : ''} ${isNarration ? 'narration' : ''}`}
    >
      <div className="flex items-start gap-3">
        {/* 인덱스 */}
        <span className="text-xs text-ark-gray font-mono w-8 shrink-0 pt-0.5">
          #{String(index + 1).padStart(3, '0')}
        </span>

        {/* 내용 */}
        <div className="flex-1 min-w-0">
          {/* 화자 */}
          {dialogue.speaker_name && (
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-medium text-ark-orange">
                {dialogue.speaker_name}
              </span>
              {dialogue.speaker_id && (
                <span className="text-xs text-ark-gray">
                  [{dialogue.speaker_id}]
                </span>
              )}
            </div>
          )}

          {/* 대사 */}
          <p className={`text-sm leading-relaxed ${isNarration ? 'text-ark-gray italic' : 'text-ark-white'}`}>
            {dialogue.text}
          </p>
        </div>

        {/* 재생 버튼 */}
        <button
          onClick={onPlay}
          className={`shrink-0 w-9 h-9 flex items-center justify-center transition-all ${
            isPlaying
              ? 'bg-ark-orange text-ark-black ark-glow'
              : 'bg-ark-panel text-ark-gray hover:bg-ark-border hover:text-ark-white'
          }`}
          title={isPlaying ? '재생 중...' : '재생'}
        >
          {isPlaying ? (
            <svg viewBox="0 0 24 24" className="w-4 h-4 ark-pulse" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
            </svg>
          )}
        </button>
      </div>
    </div>
  )
}
