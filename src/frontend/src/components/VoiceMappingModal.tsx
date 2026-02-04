import { useEffect, useState, useMemo, useRef, useCallback } from 'react'
import { useAppStore, AUTO_VOICE_FEMALE, AUTO_VOICE_MALE, simpleHash } from '../stores/appStore'
import { voiceApi, type GroupCharacterInfo, API_BASE } from '../services/api'

// 저장 아이콘 (디스크)
function SaveIcon({ className = '' }: { className?: string }) {
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 20 20">
      <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/>
    </svg>
  )
}

// 체크 아이콘
function CheckIcon({ className = '' }: { className?: string }) {
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 20 20">
      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
    </svg>
  )
}

interface VoiceMappingModalProps {
  isOpen: boolean
  onClose: () => void
}

// 캐릭터 이미지 컴포넌트
function CharacterStanding({
  charId,
  alt,
  className = '',
  showPlaceholder = true,
}: {
  charId: string | null | undefined
  alt: string
  className?: string
  showPlaceholder?: boolean
}) {
  const [hasError, setHasError] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const imageUrl = charId ? `${API_BASE}/api/voice/images/${charId}` : null

  if (!imageUrl || hasError) {
    return showPlaceholder ? (
      <div className={`bg-ark-black/50 border border-ark-border flex flex-col items-center justify-center text-ark-gray/50 p-1 ${className}`}>
        <span className="text-xl">?</span>
        {charId && (
          <span className="text-[8px] text-center break-all leading-tight mt-1 opacity-70">
            {charId.replace(/^(avg_|char_)/, '').substring(0, 12)}
          </span>
        )}
      </div>
    ) : null
  }

  return (
    <div className={`bg-ark-black/30 border border-ark-border overflow-hidden flex items-end justify-center relative ${className}`}>
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center text-ark-gray/30">
          <span className="text-sm">...</span>
        </div>
      )}
      <img
        src={imageUrl}
        alt={alt}
        className="max-w-full max-h-full object-contain object-bottom"
        onLoad={() => setIsLoading(false)}
        onError={() => { setHasError(true); setIsLoading(false) }}
      />
    </div>
  )
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

  // 메타데이터 (성별, 영구 매핑)
  const [genders, setGenders] = useState<Record<string, string>>({})
  const [persistentMappings, setPersistentMappings] = useState<Record<string, string>>({})
  const [isLoadingMeta, setIsLoadingMeta] = useState(false)

  // 메타데이터 로드 (성별 + 영구 매핑)
  useEffect(() => {
    if (!isOpen) return

    setIsLoadingMeta(true)
    Promise.all([
      voiceApi.listGenders().catch(() => ({ genders: {} })),
      voiceApi.listVoiceMappings().catch(() => ({ mappings: {} })),
    ]).then(([genderRes, mappingRes]) => {
      setGenders(genderRes.genders)
      setPersistentMappings(mappingRes.mappings)
      setIsLoadingMeta(false)
    })
  }, [isOpen])

  // 영구 매핑 저장
  const handleSaveMapping = useCallback(async (spriteId: string, voiceCharId: string) => {
    await voiceApi.addVoiceMapping(spriteId, voiceCharId)
    setPersistentMappings(prev => ({ ...prev, [spriteId]: voiceCharId }))
  }, [])

  // 영구 매핑 삭제
  const handleDeleteMapping = useCallback(async (spriteId: string) => {
    await voiceApi.removeVoiceMapping(spriteId)
    setPersistentMappings(prev => {
      const next = { ...prev }
      delete next[spriteId]
      return next
    })
  }, [])

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
        className="bg-ark-panel border border-ark-border rounded-lg shadow-xl w-[640px] max-h-[85vh] flex flex-col overflow-hidden"
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
          <div className="flex items-center gap-3">
            <span className="text-xs text-ark-gray">
              매핑: {mappedCount}/{voicelessCharacters.length}
            </span>
            <span className="text-xs text-green-400">
              영구 저장: {Object.keys(persistentMappings).length}
            </span>
          </div>
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
            <div className="space-y-2">
              {voicelessCharacters.map((char, idx) => (
                <CharacterMappingRow
                  key={`${char.char_id ?? 'n'}-${char.name}-${idx}`}
                  char={char}
                  genders={genders}
                  availableVoices={availableVoices}
                  voiceCharacters={voiceCharacters}
                  speakerVoiceMap={speakerVoiceMap}
                  setSpeakerVoice={setSpeakerVoice}
                  getSpeakerVoice={getSpeakerVoice}
                  defaultFemaleVoices={defaultFemaleVoices}
                  defaultMaleVoices={defaultMaleVoices}
                  trainedCharIds={trainedCharIds}
                  persistentMappings={persistentMappings}
                  onSaveMapping={handleSaveMapping}
                  onDeleteMapping={handleDeleteMapping}
                />
              ))}
            </div>
          )}
        </div>

        {/* 푸터 */}
        <div className="p-4 border-t border-ark-border flex justify-between items-center">
          <div className="text-xs text-ark-gray/70 space-y-0.5">
            <p>* 자동: 이름 기반 분배 / 여성·남성: 성별 고정</p>
            <p>* 💾: 영구 저장 (다른 에피소드에서도 적용)</p>
          </div>
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

// 검색 가능한 캐릭터 선택 드롭다운
interface VoiceSelectProps {
  value: string
  onChange: (value: string | null) => void
  options: { char_id: string; name: string }[]
  genders: Record<string, string>
  trainedCharIds: Set<string>
  autoOptions: {
    autoVoiceName: string | null
    autoFemaleName: string | null
    autoMaleName: string | null
    hasDefaultFemale: boolean
    hasDefaultMale: boolean
  }
}

function VoiceSelect({
  value,
  onChange,
  options,
  genders,
  trainedCharIds,
  autoOptions,
}: VoiceSelectProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [search, setSearch] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)

  // 외부 클릭 감지
  useEffect(() => {
    if (!isOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
        setSearch('')
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen])

  // 현재 선택된 값의 표시 이름
  const getDisplayName = () => {
    if (!value) return `자동${autoOptions.autoVoiceName ? ` (${autoOptions.autoVoiceName})` : ''}`
    if (value === AUTO_VOICE_FEMALE) return `여성${autoOptions.autoFemaleName ? ` (${autoOptions.autoFemaleName})` : ''}`
    if (value === AUTO_VOICE_MALE) return `남성${autoOptions.autoMaleName ? ` (${autoOptions.autoMaleName})` : ''}`
    const found = options.find(o => o.char_id === value)
    return found?.name ?? value
  }

  // 검색 필터링
  const filteredOptions = useMemo(() => {
    if (!search) return options
    const lower = search.toLowerCase()
    return options.filter(o =>
      o.name.toLowerCase().includes(lower) ||
      o.char_id.toLowerCase().includes(lower)
    )
  }, [options, search])

  const handleSelect = (charId: string | null) => {
    onChange(charId)
    setIsOpen(false)
    setSearch('')
  }

  return (
    <div ref={containerRef} className="relative w-full">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="ark-input text-xs py-1.5 px-2 w-full text-left flex items-center justify-between"
      >
        <span className="truncate">{getDisplayName()}</span>
        <svg className={`w-3 h-3 ml-1 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute z-50 mt-1 w-64 right-0 bg-ark-panel border border-ark-border rounded shadow-xl max-h-64 overflow-hidden flex flex-col">
          {/* 검색 입력 */}
          <div className="p-2 border-b border-ark-border">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="캐릭터 검색..."
              className="ark-input text-xs w-full py-1 px-2"
              autoFocus
            />
          </div>

          {/* 옵션 목록 */}
          <div className="overflow-y-auto flex-1">
            {/* 자동 옵션들 */}
            {!search && (
              <>
                <button
                  onClick={() => handleSelect(null)}
                  className={`w-full text-left px-3 py-2 text-xs hover:bg-ark-black/40 ${!value ? 'bg-ark-accent/20 text-ark-accent' : 'text-ark-white'}`}
                >
                  자동{autoOptions.autoVoiceName ? ` (${autoOptions.autoVoiceName})` : ''}
                </button>
                {autoOptions.hasDefaultFemale && (
                  <button
                    onClick={() => handleSelect(AUTO_VOICE_FEMALE)}
                    className={`w-full text-left px-3 py-2 text-xs hover:bg-ark-black/40 ${value === AUTO_VOICE_FEMALE ? 'bg-ark-accent/20 text-ark-accent' : 'text-ark-white'}`}
                  >
                    여성{autoOptions.autoFemaleName ? ` (${autoOptions.autoFemaleName})` : ''}
                  </button>
                )}
                {autoOptions.hasDefaultMale && (
                  <button
                    onClick={() => handleSelect(AUTO_VOICE_MALE)}
                    className={`w-full text-left px-3 py-2 text-xs hover:bg-ark-black/40 ${value === AUTO_VOICE_MALE ? 'bg-ark-accent/20 text-ark-accent' : 'text-ark-white'}`}
                  >
                    남성{autoOptions.autoMaleName ? ` (${autoOptions.autoMaleName})` : ''}
                  </button>
                )}
                <div className="border-t border-ark-border my-1" />
              </>
            )}

            {/* 캐릭터 옵션 */}
            {filteredOptions.length === 0 ? (
              <div className="px-3 py-4 text-xs text-ark-gray text-center">검색 결과 없음</div>
            ) : (
              filteredOptions.map(opt => {
                const isPrepared = trainedCharIds.has(opt.char_id)
                const gender = genders[opt.char_id]
                const isSelected = value === opt.char_id
                return (
                  <button
                    key={opt.char_id}
                    onClick={() => handleSelect(opt.char_id)}
                    className={`w-full text-left px-3 py-2 text-xs hover:bg-ark-black/40 flex items-center gap-2 ${isSelected ? 'bg-ark-accent/20 text-ark-accent' : 'text-ark-white'}`}
                  >
                    <span className="truncate flex-1">{opt.name}</span>
                    {gender && (
                      <span className={gender === 'female' ? 'text-pink-400' : 'text-blue-400'}>
                        {gender === 'female' ? '♀' : '♂'}
                      </span>
                    )}
                    {!isPrepared && <span className="text-ark-gray/50">(기본)</span>}
                  </button>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// 개별 캐릭터 매핑 카드
interface CharacterMappingRowProps {
  char: GroupCharacterInfo
  genders: Record<string, string>
  availableVoices: { char_id: string; name: string }[]
  voiceCharacters: { char_id: string; name: string }[]
  speakerVoiceMap: Record<string, string>
  setSpeakerVoice: (speakerId: string, voiceId: string | null) => void
  getSpeakerVoice: (speakerId: string, speakerName?: string) => string | null
  defaultFemaleVoices: string[]
  defaultMaleVoices: string[]
  trainedCharIds: Set<string>
  persistentMappings: Record<string, string>
  onSaveMapping: (spriteId: string, voiceCharId: string) => Promise<void>
  onDeleteMapping: (spriteId: string) => Promise<void>
}

function CharacterMappingRow({
  char,
  genders,
  availableVoices,
  voiceCharacters,
  speakerVoiceMap,
  setSpeakerVoice,
  getSpeakerVoice,
  defaultFemaleVoices,
  defaultMaleVoices,
  trainedCharIds,
  persistentMappings,
  onSaveMapping,
  onDeleteMapping,
}: CharacterMappingRowProps) {
  const [isSaving, setIsSaving] = useState(false)
  const mappingKey = char.char_id || `name:${char.name}`
  const currentMapping = speakerVoiceMap[mappingKey]
  const autoVoice = getSpeakerVoice(mappingKey, char.name)
  const autoVoiceName = autoVoice ? voiceCharacters.find(v => v.char_id === autoVoice)?.name : null

  // 해당 캐릭터의 성별
  const charGender = char.char_id ? genders[char.char_id] : null

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

  // 매핑된 캐릭터 (실제 선택 또는 자동)
  const mappedCharId = currentMapping && currentMapping !== AUTO_VOICE_FEMALE && currentMapping !== AUTO_VOICE_MALE
    ? currentMapping
    : autoVoice
  const mappedCharName = mappedCharId
    ? voiceCharacters.find(v => v.char_id === mappedCharId)?.name
    : null

  // 영구 매핑 상태
  const persistentMapping = char.char_id ? persistentMappings[char.char_id] : null
  const isPersistentlySaved = persistentMapping === currentMapping
  const canSavePersistently = char.char_id && currentMapping && currentMapping !== AUTO_VOICE_FEMALE && currentMapping !== AUTO_VOICE_MALE

  const handleSaveMapping = async () => {
    if (!char.char_id || !currentMapping || currentMapping === AUTO_VOICE_FEMALE || currentMapping === AUTO_VOICE_MALE) return
    setIsSaving(true)
    try {
      await onSaveMapping(char.char_id, currentMapping)
    } finally {
      setIsSaving(false)
    }
  }

  const handleDeleteMapping = async () => {
    if (!char.char_id || !persistentMapping) return
    setIsSaving(true)
    try {
      await onDeleteMapping(char.char_id)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="rounded-lg bg-ark-black/40 hover:bg-ark-black/50 transition-colors overflow-hidden border border-ark-border/50">
      <div className="flex">
        {/* 이미지 영역: NPC → 매핑 캐릭터 */}
        <div className="flex gap-1 p-2 bg-ark-black/30">
          {/* NPC 이미지 */}
          <CharacterStanding
            charId={char.char_id}
            alt={char.name}
            className="w-16 h-24 rounded"
          />
          {/* 화살표 */}
          <div className="flex items-center px-1 text-ark-gray/50">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </div>
          {/* 매핑된 캐릭터 이미지 */}
          <CharacterStanding
            charId={mappedCharId}
            alt={mappedCharName ?? '매핑 필요'}
            className="w-16 h-24 rounded"
            showPlaceholder={true}
          />
        </div>

        {/* 정보 영역 */}
        <div className="flex-1 p-3 flex flex-col justify-between min-w-0">
          {/* 상단: 캐릭터 이름/정보 */}
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-ark-white truncate" title={char.name}>
                {char.name}
              </span>
              {charGender && (
                <span className={`text-[10px] px-1 rounded ${
                  charGender === 'female' ? 'bg-pink-500/20 text-pink-400' : 'bg-blue-500/20 text-blue-400'
                }`}>
                  {charGender === 'female' ? '♀' : '♂'}
                </span>
              )}
              {/* 영구 저장 상태 표시 */}
              {isPersistentlySaved && (
                <span className="text-[10px] px-1 rounded bg-green-500/20 text-green-400 flex items-center gap-0.5">
                  <CheckIcon className="w-2.5 h-2.5" />
                  저장됨
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-1">
              {!char.char_id && (
                <span className="text-[10px] text-ark-gray/50">(이름만)</span>
              )}
              <span className="text-[10px] text-ark-gray">{char.dialogue_count}대사</span>
              {char.char_id && (
                <span className="text-[10px] text-ark-gray/50 truncate" title={char.char_id}>
                  {char.char_id}
                </span>
              )}
            </div>
          </div>

          {/* 하단: 음성 선택 + 저장 버튼 */}
          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1">
              <VoiceSelect
                value={currentMapping ?? ''}
                onChange={(val) => setSpeakerVoice(mappingKey, val)}
                options={availableVoices}
                genders={genders}
                trainedCharIds={trainedCharIds}
                autoOptions={{
                  autoVoiceName: autoVoiceName ?? null,
                  autoFemaleName: autoFemaleName ?? null,
                  autoMaleName: autoMaleName ?? null,
                  hasDefaultFemale: defaultFemaleVoices.length > 0,
                  hasDefaultMale: defaultMaleVoices.length > 0,
                }}
              />
            </div>
            {/* 영구 저장/삭제 버튼 */}
            {canSavePersistently && !isPersistentlySaved && (
              <button
                onClick={handleSaveMapping}
                disabled={isSaving}
                className="p-1.5 rounded bg-ark-accent/20 text-ark-accent hover:bg-ark-accent/30 transition-colors disabled:opacity-50"
                title="영구 매핑으로 저장"
              >
                <SaveIcon className="w-4 h-4" />
              </button>
            )}
            {persistentMapping && (
              <button
                onClick={handleDeleteMapping}
                disabled={isSaving}
                className="p-1.5 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors disabled:opacity-50"
                title="영구 매핑 삭제"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
