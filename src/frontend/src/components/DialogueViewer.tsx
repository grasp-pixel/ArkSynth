import { useEffect, useRef, useMemo, useState } from 'react'
import { useAppStore } from '../stores/appStore'
import { voiceApi, type DialogueInfo } from '../services/api'

// 디버그 모드 (캐릭터 ID 표시)
const DEBUG_SHOW_CHAR_ID = true

// 문자열 해시 → HSL 색상 (부드러운 톤으로 제한)
function getColorFromName(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    const char = name.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash
  }
  hash = Math.abs(hash)

  // HSL로 색상 생성 (부드러운 톤으로 제한)
  const hue = hash % 360                    // 0-360 전체 색상
  const saturation = 45 + (hash % 25)       // 45-70% 채도 (너무 선명하지 않게)
  const lightness = 60 + (hash % 15)        // 60-75% 밝기 (어두운 배경에서 잘 보이게)

  return `hsl(${hue}, ${saturation}%, ${lightness}%)`
}

// 화자 미니 카드 (캐릭터 스프라이트 이미지)
function SpeakerCard({ speakerId, speakerName, speakerColor, dialogueType }: {
  speakerId: string | null
  speakerName: string | null
  speakerColor?: string
  dialogueType: string
}) {
  const [hasError, setHasError] = useState(false)
  const [showFull, setShowFull] = useState(false)

  // 나레이션/자막/스티커/팝업은 빈 공간으로 정렬 유지
  const isNonDialogue = dialogueType !== 'dialogue'
  if (isNonDialogue && !speakerId) {
    return <div className="w-10 h-14 shrink-0" />
  }

  // 이미지 없거나 로드 실패 시 이니셜 폴백
  if (!speakerId || hasError) {
    const initial = speakerName ? speakerName.charAt(0) : '?'
    return (
      <div
        className="w-10 h-14 shrink-0 rounded bg-ark-panel border border-ark-border flex items-center justify-center"
        title={speakerName || '알 수 없음'}
      >
        <span
          className="text-sm font-bold"
          style={{ color: speakerColor || '#8a8a8a' }}
        >
          {initial}
        </span>
      </div>
    )
  }

  const imageUrl = voiceApi.getImageUrl(speakerId)
  const alt = speakerName || speakerId

  return (
    <>
      <div
        className="w-10 h-14 shrink-0 rounded bg-ark-black/30 border border-ark-border overflow-hidden cursor-pointer hover:border-ark-orange/50 transition-colors"
        onClick={() => setShowFull(true)}
        title="클릭하여 크게 보기"
      >
        <img
          src={imageUrl}
          alt={alt}
          loading="lazy"
          className="w-full h-full object-cover object-top"
          onError={() => setHasError(true)}
        />
      </div>

      {/* 확대 모달 */}
      {showFull && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 cursor-pointer"
          onClick={() => setShowFull(false)}
        >
          <div className="relative max-w-[90vw] max-h-[90vh]">
            <img
              src={imageUrl}
              alt={alt}
              className="max-w-full max-h-[90vh] object-contain rounded-lg shadow-2xl"
            />
            <div className="absolute bottom-4 left-0 right-0 text-center">
              <span className="bg-black/70 text-white px-3 py-1.5 rounded text-sm">
                {alt}
              </span>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default function DialogueViewer() {
  const {
    selectedEpisode,
    isLoadingEpisode,
    playDialogue,
    isPlaying,
    currentDialogue,
    isDubbingMode,
    isPrepared,
    matchedDialogue,
    matchedIndex,
    matchSimilarity,
    groupCharacters,
    renderProgress,
    isRendering,
    getSpeakerVoice,
    narratorCharId,
    defaultFemaleVoices,
    defaultVoices,
    voiceCharacters,
  } = useAppStore()

  // 디버그: 캐릭터 ID 표시 토글
  const [showCharIds, setShowCharIds] = useState(DEBUG_SHOW_CHAR_ID)

  // 음성 있는 캐릭터 ID Set (빠른 조회용)
  const voicedCharacterIds = useMemo(() => {
    const ids = new Set<string>()
    groupCharacters
      .filter(c => c.has_voice && c.char_id)
      .forEach(c => ids.add(c.char_id!))
    return ids
  }, [groupCharacters])

  // 음성 있는 캐릭터 이름 Set
  const voicedCharacterNames = useMemo(() => {
    const names = new Set<string>()
    groupCharacters
      .filter(c => c.has_voice)
      .forEach(c => names.add(c.name))
    return names
  }, [groupCharacters])

  const matchedRef = useRef<HTMLDivElement>(null)

  // 매칭된 대사로 자동 스크롤
  useEffect(() => {
    if (matchedRef.current && matchedIndex >= 0) {
      matchedRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
    }
  }, [matchedIndex])

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
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-ark-white">
            {selectedEpisode.title || selectedEpisode.id}
          </h2>
          <div className="flex items-center gap-2">
            {/* 캐릭터 ID 표시 토글 */}
            <button
              onClick={() => setShowCharIds(!showCharIds)}
              className={`text-xs px-2 py-1 rounded transition-colors ${
                showCharIds
                  ? 'bg-ark-cyan/20 text-ark-cyan border border-ark-cyan/50'
                  : 'bg-ark-panel text-ark-gray border border-ark-border hover:border-ark-gray'
              }`}
              title="캐릭터 ID 표시"
            >
              ID
            </button>
            {isDubbingMode && (
              <span className="ark-tag text-ark-orange">
                더빙 모드
              </span>
            )}
          </div>
        </div>
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
        {selectedEpisode.dialogues.map((dialogue, index) => {
          const isMatched = isDubbingMode && matchedDialogue?.id === dialogue.id

          // 음성 있는 캐릭터인지 확인
          const hasVoice = dialogue.speaker_id
            ? voicedCharacterIds.has(dialogue.speaker_id)
            : voicedCharacterNames.has(dialogue.speaker_name || '')

          // 음성 있으면 이름 해시 기반 고유 색상
          const speakerColor = hasVoice && dialogue.speaker_name
            ? getColorFromName(dialogue.speaker_name)
            : undefined

          // 렌더링 상태 확인
          const isRendered = renderProgress ? index < renderProgress.completed : false

          // 사용될 캐릭터 ID 계산 (디버그용)
          // speaker_id 우선 (수동 매핑이 speaker_id로 저장되므로), 없으면 name: 키
          let resolvedCharId: string | null = null
          if (showCharIds) {
            if (dialogue.speaker_id) {
              // speaker_id가 있으면 먼저 조회 (VoiceMappingModal에서 char_id로 매핑 저장)
              resolvedCharId = getSpeakerVoice(dialogue.speaker_id, dialogue.speaker_name || undefined)
            } else if (dialogue.speaker_name) {
              // speaker_id가 없으면 name: 키로 조회
              const nameKey = `name:${dialogue.speaker_name}`
              resolvedCharId = getSpeakerVoice(nameKey, dialogue.speaker_name)
            } else {
              // 나레이션
              resolvedCharId = narratorCharId || (defaultFemaleVoices.length > 0 ? defaultFemaleVoices[0] : (defaultVoices.length > 0 ? defaultVoices[0] : null))
            }
          }

          // 캐릭터 이름 조회
          const resolvedCharName = resolvedCharId
            ? voiceCharacters.find(v => v.char_id === resolvedCharId)?.name
            : null

          return (
            <div
              key={dialogue.id}
              ref={isMatched ? matchedRef : null}
            >
              <DialogueItem
                dialogue={dialogue}
                index={index}
                isPlaying={isPlaying && currentDialogue?.id === dialogue.id}
                isMatched={isMatched}
                matchSimilarity={isMatched ? matchSimilarity : 0}
                speakerColor={speakerColor}
                isPrepared={isPrepared}
                isRendered={isRendered}
                isRendering={isRendering && renderProgress?.completed === index}
                onPlay={() => handlePlayClick(dialogue)}
                showCharId={showCharIds}
                resolvedCharId={resolvedCharId}
                resolvedCharName={resolvedCharName}
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}

interface DialogueItemProps {
  dialogue: DialogueInfo
  index: number
  isPlaying: boolean
  isMatched?: boolean
  matchSimilarity?: number
  speakerColor?: string  // 음성 있는 캐릭터의 고유 색상
  isPrepared?: boolean   // 더빙 준비 완료 여부
  isRendered?: boolean   // 사전 렌더링 완료 여부
  isRendering?: boolean  // 현재 렌더링 중인 대사
  onPlay: () => void
  showCharId?: boolean   // 캐릭터 ID 표시 여부
  resolvedCharId?: string | null  // 실제 사용될 캐릭터 ID
  resolvedCharName?: string | null  // 캐릭터 이름
}

function DialogueItem({ dialogue, index, isPlaying, isMatched, matchSimilarity, speakerColor, isPrepared, isRendered, isRendering, onPlay, showCharId, resolvedCharId, resolvedCharName }: DialogueItemProps) {
  const { getModelType } = useAppStore()
  const isSubtitle = dialogue.dialogue_type === 'subtitle'
  const isSticker = dialogue.dialogue_type === 'sticker'
  const isPopup = dialogue.dialogue_type === 'popup'
  const isNarration = dialogue.dialogue_type === 'narration'
  const hasVoice = !!speakerColor

  return (
    <div
      className={`ark-dialogue ${isPlaying ? 'playing' : ''} ${isNarration ? 'narration' : ''} ${isSubtitle || isSticker ? 'subtitle' : ''} ${isPopup ? 'popup' : ''} ${
        isMatched ? 'ring-2 ring-ark-orange bg-ark-orange/10' : ''
      }`}
    >
      <div className="flex items-start gap-3">
        {/* 인덱스 + 렌더링 상태 */}
        <div className="flex items-center gap-1 shrink-0 pt-0.5">
          <span className="text-xs text-ark-gray font-mono w-8">
            #{String(index + 1).padStart(3, '0')}
          </span>
          {/* 렌더링 상태 표시 */}
          {isRendering ? (
            <span className="w-2 h-2 rounded-full bg-ark-orange ark-pulse" title="렌더링 중" />
          ) : isRendered ? (
            <span className="w-2 h-2 rounded-full bg-green-500" title="렌더링 완료" />
          ) : null}
        </div>

        {/* 화자 스프라이트 미니 카드 */}
        <SpeakerCard
          speakerId={dialogue.speaker_id}
          speakerName={dialogue.speaker_name}
          speakerColor={speakerColor}
          dialogueType={dialogue.dialogue_type}
        />

        {/* 내용 */}
        <div className="flex-1 min-w-0">
          {/* 화자 + 캐릭터 ID + 매칭 표시 */}
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            {/* 특수 대사 타입 라벨 */}
            {isNarration && (
              <span className="text-xs px-1.5 py-0.5 bg-ark-cyan/20 text-ark-cyan rounded font-medium">
                나레이션
              </span>
            )}
            {isSubtitle && (
              <span className="text-xs px-1.5 py-0.5 bg-purple-500/20 text-purple-400 rounded font-medium">
                자막
              </span>
            )}
            {isSticker && (
              <span className="text-xs px-1.5 py-0.5 bg-pink-500/20 text-pink-400 rounded font-medium">
                스티커
              </span>
            )}
            {isPopup && (
              <span className="text-xs px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 rounded font-medium">
                팝업
              </span>
            )}
            {dialogue.speaker_name && (
              <>
                <span
                  className="text-sm font-medium"
                  style={{ color: speakerColor || '#9CA3AF' }}  // 음성 있으면 고유색, 없으면 회색
                >
                  {dialogue.speaker_name}
                </span>
                {hasVoice && (
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: speakerColor }}
                    title="음성 있음"
                  />
                )}
              </>
            )}
            {/* 캐릭터 ID 표시 (디버그) */}
            {showCharId && resolvedCharId && (() => {
              const modelType = getModelType(resolvedCharId)
              const colorClass = modelType === 'finetuned'
                ? 'bg-purple-500/20 text-purple-400'
                : modelType === 'prepared'
                  ? 'bg-green-500/20 text-green-400'
                  : 'bg-ark-cyan/20 text-ark-cyan'
              return (
                <span
                  className={`text-xs px-1.5 py-0.5 ${colorClass} rounded font-mono`}
                  title={`음성: ${resolvedCharId}${resolvedCharName ? ` (${resolvedCharName})` : ''} [${modelType}]`}
                >
                  → {resolvedCharName || resolvedCharId}
                </span>
              )
            })()}
            {showCharId && !resolvedCharId && (
              <span className="text-xs px-1.5 py-0.5 bg-red-500/20 text-red-400 rounded">
                음성 없음
              </span>
            )}
            {isMatched && matchSimilarity !== undefined && (
              <span className="ml-auto text-xs px-2 py-0.5 bg-ark-orange text-ark-black rounded font-medium">
                매칭 {(matchSimilarity * 100).toFixed(0)}%
              </span>
            )}
          </div>

          {/* 대사 */}
          <p className={`text-sm leading-relaxed ${
            isSubtitle ? 'text-purple-300 italic' :
            isSticker ? 'text-pink-300 italic' :
            isPopup ? 'text-yellow-300' :
            isNarration ? 'text-ark-cyan-dark italic' :
            'text-ark-white'
          }`}>
            {dialogue.text}
          </p>
        </div>

        {/* 재생 버튼 - 더빙 준비 완료 시에만 활성화 */}
        {isPrepared ? (
          <button
            onClick={onPlay}
            className={`shrink-0 w-9 h-9 flex items-center justify-center rounded transition-all ${
              isPlaying
                ? 'bg-ark-orange text-ark-black ark-glow'
                : isMatched
                  ? 'bg-ark-orange/30 text-ark-orange hover:bg-ark-orange hover:text-ark-black'
                  : 'bg-ark-panel text-ark-white hover:bg-ark-orange hover:text-ark-black border border-ark-border hover:border-ark-orange'
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
        ) : (
          <div
            className="shrink-0 w-9 h-9 flex items-center justify-center rounded bg-ark-black/30 text-ark-gray/30"
            title="더빙 준비 후 사용 가능"
          >
            <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </div>
        )}
      </div>
    </div>
  )
}
