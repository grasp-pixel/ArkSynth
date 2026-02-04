import { useEffect, useState, useMemo } from 'react'
import { useAppStore, AUTO_VOICE_FEMALE, AUTO_VOICE_MALE, simpleHash } from '../stores/appStore'
import { voiceApi, type GroupCharacterInfo, API_BASE } from '../services/api'

interface VoiceMappingModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function VoiceMappingModal({ isOpen, onClose }: VoiceMappingModalProps) {
  const {
    episodeCharacters,
    voiceCharacters,
    trainedCharIds,
    speakerVoiceMap,
    setSpeakerVoice,
    defaultFemaleVoices,
    defaultMaleVoices,
    getSpeakerVoice,
  } = useAppStore()

  // 성별/이미지 데이터
  const [genders, setGenders] = useState<Record<string, string>>({})
  const [images, setImages] = useState<Record<string, string>>({})
  const [isLoadingMeta, setIsLoadingMeta] = useState(false)

  // 성별/이미지 데이터 로드
  useEffect(() => {
    if (!isOpen) return

    setIsLoadingMeta(true)
    Promise.all([
      voiceApi.listGenders().catch(() => ({ genders: {} })),
      voiceApi.listImages().catch(() => ({ images: {} })),
    ]).then(([genderRes, imageRes]) => {
      setGenders(genderRes.genders)

      // 상대 URL에 API_BASE 붙이기
      const imagesWithBase: Record<string, string> = {}
      for (const [charId, url] of Object.entries(imageRes.images)) {
        imagesWithBase[charId] = `${API_BASE}${url}`
      }
      setImages(imagesWithBase)
      setIsLoadingMeta(false)
    })
  }, [isOpen])

  // 음성 없는 캐릭터 (매핑 대상)
  const voicelessCharacters = useMemo(() => {
    return episodeCharacters.filter(c => !c.has_voice && c.name)
  }, [episodeCharacters])

  // 선택 가능한 음성 목록: 준비된 캐릭터 + 기본 음성 캐릭터
  const availableVoices = useMemo(() => {
    const prepared = voiceCharacters.filter(c => trainedCharIds.has(c.char_id))
    const defaultIds = new Set([...defaultFemaleVoices, ...defaultMaleVoices])

    // 기본 음성 중 준비되지 않은 캐릭터 추가
    const defaultNotPrepared = voiceCharacters.filter(
      c => defaultIds.has(c.char_id) && !trainedCharIds.has(c.char_id)
    )

    // 중복 제거
    const all = [...prepared]
    for (const c of defaultNotPrepared) {
      if (!all.some(v => v.char_id === c.char_id)) {
        all.push(c)
      }
    }

    return all
  }, [voiceCharacters, trainedCharIds, defaultFemaleVoices, defaultMaleVoices])

  // 매핑 완료된 캐릭터 수
  const mappedCount = useMemo(() => {
    return voicelessCharacters.filter(c => {
      const key = c.char_id || `name:${c.name}`
      return speakerVoiceMap[key] !== undefined
    }).length
  }, [voicelessCharacters, speakerVoiceMap])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-ark-panel border border-ark-border rounded-lg shadow-xl w-[520px] max-h-[80vh] flex flex-col overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between p-4 border-b border-ark-border">
          <div>
            <h2 className="text-lg font-bold text-ark-white">음성 매핑 설정</h2>
            <p className="text-xs text-ark-gray mt-1">
              음성이 없는 캐릭터에 대체 음성을 지정합니다
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-ark-gray hover:text-ark-white p-1"
          >
            <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>

        {/* 요약 */}
        <div className="px-4 py-2 bg-ark-black/30 border-b border-ark-border flex items-center justify-between">
          <span className="text-xs text-ark-gray">
            음성 없는 캐릭터: {voicelessCharacters.length}명
          </span>
          <span className="text-xs text-ark-gray">
            매핑 완료: {mappedCount}/{voicelessCharacters.length}
          </span>
        </div>

        {/* 본문 */}
        <div className="flex-1 overflow-y-auto p-3">
          {isLoadingMeta ? (
            <div className="text-center text-ark-gray py-8 ark-pulse">
              메타데이터 로딩 중...
            </div>
          ) : voicelessCharacters.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <svg viewBox="0 0 24 24" className="w-12 h-12 text-green-500 mb-2" fill="currentColor">
                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
              </svg>
              <p className="text-ark-white">모든 캐릭터가 음성을 보유하고 있습니다</p>
            </div>
          ) : (
            <div className="space-y-1.5">
              {voicelessCharacters.map((char, idx) => (
                <CharacterMappingRow
                  key={`${char.char_id ?? 'n'}-${char.name}-${idx}`}
                  char={char}
                  genders={genders}
                  images={images}
                  availableVoices={availableVoices}
                  voiceCharacters={voiceCharacters}
                  speakerVoiceMap={speakerVoiceMap}
                  setSpeakerVoice={setSpeakerVoice}
                  getSpeakerVoice={getSpeakerVoice}
                  defaultFemaleVoices={defaultFemaleVoices}
                  defaultMaleVoices={defaultMaleVoices}
                  trainedCharIds={trainedCharIds}
                />
              ))}
            </div>
          )}
        </div>

        {/* 푸터 */}
        <div className="p-4 border-t border-ark-border flex justify-between items-center">
          <p className="text-xs text-ark-gray/70">
            * 자동: 이름 기반 분배 / 여성·남성: 성별 고정
          </p>
          <button
            onClick={onClose}
            className="ark-btn ark-btn-secondary text-sm"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  )
}

// 개별 캐릭터 매핑 행
interface CharacterMappingRowProps {
  char: GroupCharacterInfo
  genders: Record<string, string>
  images: Record<string, string>
  availableVoices: { char_id: string; name: string }[]
  voiceCharacters: { char_id: string; name: string }[]
  speakerVoiceMap: Record<string, string>
  setSpeakerVoice: (speakerId: string, voiceId: string | null) => void
  getSpeakerVoice: (speakerId: string, speakerName?: string) => string | null
  defaultFemaleVoices: string[]
  defaultMaleVoices: string[]
  trainedCharIds: Set<string>
}

function CharacterMappingRow({
  char,
  genders,
  images,
  availableVoices,
  voiceCharacters,
  speakerVoiceMap,
  setSpeakerVoice,
  getSpeakerVoice,
  defaultFemaleVoices,
  defaultMaleVoices,
  trainedCharIds,
}: CharacterMappingRowProps) {
  const mappingKey = char.char_id || `name:${char.name}`
  const currentMapping = speakerVoiceMap[mappingKey]
  const autoVoice = getSpeakerVoice(mappingKey, char.name)
  const autoVoiceName = autoVoice ? voiceCharacters.find(v => v.char_id === autoVoice)?.name : null

  // 해당 캐릭터의 성별/이미지
  const charGender = char.char_id ? genders[char.char_id] : null
  const charImage = char.char_id ? images[char.char_id] : null

  // 자동 여성/남성 선택 시 실제 선택될 캐릭터
  const hash = simpleHash(mappingKey)
  const autoFemaleVoice = defaultFemaleVoices.length > 0
    ? defaultFemaleVoices[hash % defaultFemaleVoices.length]
    : null
  const autoMaleVoice = defaultMaleVoices.length > 0
    ? defaultMaleVoices[hash % defaultMaleVoices.length]
    : null
  const autoFemaleName = autoFemaleVoice
    ? voiceCharacters.find(v => v.char_id === autoFemaleVoice)?.name
    : null
  const autoMaleName = autoMaleVoice
    ? voiceCharacters.find(v => v.char_id === autoMaleVoice)?.name
    : null

  return (
    <div className="grid grid-cols-[36px_1fr_160px] gap-3 items-center py-2 px-3 rounded bg-ark-black/40 hover:bg-ark-black/60 transition-colors">
      {/* 캐릭터 이미지 */}
      <div className="w-9 h-9 rounded-full bg-ark-black/50 overflow-hidden border border-ark-border">
        {charImage ? (
          <img
            src={charImage}
            alt={char.name}
            className="w-full h-full object-cover"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-ark-gray text-xs">?</div>
        )}
      </div>

      {/* 캐릭터 정보 */}
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-sm text-ark-white truncate" title={char.name}>
          {char.name}
        </span>
        {charGender && (
          <span className={`text-[10px] px-1 rounded whitespace-nowrap ${
            charGender === 'female' ? 'bg-pink-500/20 text-pink-400' : 'bg-blue-500/20 text-blue-400'
          }`}>
            {charGender === 'female' ? '♀' : '♂'}
          </span>
        )}
        {!char.char_id && (
          <span className="text-[10px] text-ark-gray/50 whitespace-nowrap">(이름)</span>
        )}
        <span className="text-[10px] text-ark-gray whitespace-nowrap">{char.dialogue_count}대사</span>
      </div>

      {/* 음성 선택 드롭다운 */}
      <select
        value={currentMapping ?? ''}
        onChange={(e) => setSpeakerVoice(mappingKey, e.target.value || null)}
        className="ark-input text-xs py-1.5 px-2 w-full"
      >
        <option value="">
          자동{autoVoiceName ? ` (${autoVoiceName})` : ''}
        </option>
        {defaultFemaleVoices.length > 0 && (
          <option value={AUTO_VOICE_FEMALE}>
            여성{autoFemaleName ? ` (${autoFemaleName})` : ''}
          </option>
        )}
        {defaultMaleVoices.length > 0 && (
          <option value={AUTO_VOICE_MALE}>
            남성{autoMaleName ? ` (${autoMaleName})` : ''}
          </option>
        )}
        <option disabled>────────</option>
        {availableVoices.map(v => {
          const isPrepared = trainedCharIds.has(v.char_id)
          const gender = genders[v.char_id]
          const genderLabel = gender === 'female' ? '♀' : gender === 'male' ? '♂' : ''
          return (
            <option key={v.char_id} value={v.char_id}>
              {v.name}{genderLabel ? ` ${genderLabel}` : ''}{!isPrepared ? ' (기본)' : ''}
            </option>
          )
        })}
      </select>
    </div>
  )
}
