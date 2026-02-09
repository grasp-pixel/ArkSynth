import { useEffect, useState, useMemo, useRef } from 'react'
import { useAppStore, AUTO_VOICE_FEMALE, AUTO_VOICE_MALE, simpleHash, isMysteryName } from '../stores/appStore'
import { voiceApi, type GroupCharacterInfo, API_BASE } from '../services/api'

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
  characters?: GroupCharacterInfo[]  // 전달되면 사용, 없으면 episodeCharacters 사용
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
  // 에러가 발생한 charId를 저장 (다른 charId로 바뀌면 에러 상태 무효화)
  const [errorCharId, setErrorCharId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [showFullImage, setShowFullImage] = useState(false)
  const imageUrl = charId ? `${API_BASE}/api/voice/images/${charId}` : null

  // 현재 charId에서 에러가 발생했는지 확인
  const hasError = errorCharId === charId

  // char_empty인 경우 placeholder 표시 (이미지 로드 시도 안 함)
  if (charId === 'char_empty') {
    return showPlaceholder ? (
      <div className={`bg-ark-black/50 border border-ark-border flex flex-col items-center justify-center text-ark-gray/50 p-1 ${className}`}>
        <span className="text-xl">?</span>
      </div>
    ) : null
  }

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
    <>
      <div
        className={`bg-ark-black/30 border border-ark-border overflow-hidden flex items-start justify-center relative cursor-pointer hover:border-ark-accent/50 transition-colors ${className}`}
        onClick={() => setShowFullImage(true)}
        title="클릭하여 크게 보기"
      >
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center text-ark-gray/30">
            <span className="text-sm">...</span>
          </div>
        )}
        <img
          src={imageUrl}
          alt={alt}
          className="w-full h-full object-cover object-top"
          onLoad={() => setIsLoading(false)}
          onError={() => { setErrorCharId(charId ?? null); setIsLoading(false) }}
        />
      </div>

      {/* 확대 모달 */}
      {showFullImage && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 cursor-pointer"
          onClick={() => setShowFullImage(false)}
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

export default function VoiceMappingModal({ isOpen, onClose, characters }: VoiceMappingModalProps) {
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

  // 사용할 캐릭터 목록 (전달된 값 우선, 없으면 에피소드 캐릭터)
  const targetCharacters = characters ?? episodeCharacters

  // 메타데이터 (성별)
  const [genders, setGenders] = useState<Record<string, string>>({})
  const [isLoadingMeta, setIsLoadingMeta] = useState(false)

  // 메타데이터 로드 (성별만 - 매핑은 appStore에서 관리)
  useEffect(() => {
    if (!isOpen) return

    setIsLoadingMeta(true)
    voiceApi.listGenders()
      .then((res) => setGenders(res.genders))
      .catch(() => setGenders({}))
      .finally(() => setIsLoadingMeta(false))
  }, [isOpen])

  // 이름 → char_id 매핑 (같은 이름의 char_id 있는 캐릭터에서 이미지 상속)
  const nameToCharId = useMemo(() => {
    const map: Record<string, string> = {}
    for (const c of targetCharacters) {
      if (c.char_id && c.name && !map[c.name] && !isMysteryName(c.name)) {
        map[c.name] = c.char_id
      }
    }
    return map
  }, [targetCharacters])

  // 음성 없는 캐릭터 (매핑 대상)
  // name-only 미스터리 이름(???)은 제외 (알 수 없는 화자 전용 슬롯으로 처리)
  const voicelessCharacters = useMemo(() => {
    return targetCharacters.filter(c => {
      if (!c.name || c.has_voice) return false
      // 미스터리 이름(???) 제외 - char_id 없는 경우와 char_id 자체가 '?'인 경우 모두
      if (isMysteryName(c.name) && (!c.char_id || isMysteryName(c.char_id))) return false
      return true
    })
  }, [targetCharacters])

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
        className="bg-ark-panel border border-ark-border rounded-lg shadow-xl w-[780px] max-h-[85vh] flex flex-col overflow-hidden"
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
          <span className={`text-xs ${mappedCount > 0 ? 'text-green-400' : 'text-ark-gray'}`}>
            매핑 설정: {mappedCount}/{voicelessCharacters.length}명
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
            <div className="space-y-3">
              {voicelessCharacters.map((char, idx) => (
                <CharacterMappingRow
                  key={`${char.char_id ?? 'n'}-${char.name}-${idx}`}
                  char={char}
                  imageCharId={char.char_id || nameToCharId[char.name] || null}
                  genders={genders}
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
          <div className="text-xs text-ark-gray/70 space-y-0.5">
            <p>* 자동: 이름 기반 분배 / 여성·남성: 성별 고정</p>
            <p>* 변경 시 자동 저장 (다른 에피소드에서도 적용)</p>
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

// 인라인 음성 선택 버튼들
interface VoiceSelectButtonsProps {
  value: string
  onChange: (value: string | null) => void
  options: { char_id: string; name: string }[]
  genders: Record<string, string>
  trainedCharIds: Set<string>
  autoVoiceName: string | null
  autoFemaleName: string | null
  autoMaleName: string | null
  hasDefaultFemale: boolean
  hasDefaultMale: boolean
  defaultFemaleVoices: string[]
  defaultMaleVoices: string[]
}

function VoiceSelectButtons({
  value,
  onChange,
  options,
  genders,
  trainedCharIds,
  autoVoiceName,
  autoFemaleName,
  autoMaleName,
  hasDefaultFemale,
  hasDefaultMale,
  defaultFemaleVoices,
  defaultMaleVoices,
}: VoiceSelectButtonsProps) {
  const [showSearch, setShowSearch] = useState(false)
  const [search, setSearch] = useState('')
  const [apiResults, setApiResults] = useState<Array<{ char_id: string; name: string; has_voice: boolean }>>([])
  const [isSearching, setIsSearching] = useState(false)
  const searchRef = useRef<HTMLInputElement>(null)

  // 검색어 변경 시 API 호출 (debounce)
  useEffect(() => {
    if (!search) {
      setApiResults([])
      return
    }

    const timer = setTimeout(async () => {
      setIsSearching(true)
      try {
        const result = await voiceApi.searchCharacters(search, 30)
        setApiResults(result.characters)
      } catch (err) {
        console.error('캐릭터 검색 실패:', err)
      } finally {
        setIsSearching(false)
      }
    }, 300) // 300ms debounce

    return () => clearTimeout(timer)
  }, [search])

  // 검색 필터링: 기존 options + API 결과 병합
  const filteredOptions = useMemo(() => {
    if (!search) return options.slice(0, 20) // 기본 20개만

    const lower = search.toLowerCase()
    // 기존 options에서 필터링
    const fromOptions = options.filter(o =>
      o.name.toLowerCase().includes(lower) ||
      o.char_id.toLowerCase().includes(lower)
    )

    // API 결과 중 options에 없는 것만 추가
    const optionIds = new Set(options.map(o => o.char_id))
    const fromApi = apiResults
      .filter(r => !optionIds.has(r.char_id))
      .map(r => ({ char_id: r.char_id, name: r.name }))

    return [...fromOptions, ...fromApi].slice(0, 30)
  }, [options, search, apiResults])

  // 검색 패널 열릴 때 포커스
  useEffect(() => {
    if (showSearch && searchRef.current) {
      searchRef.current.focus()
    }
  }, [showSearch])

  const handleSelect = (charId: string | null) => {
    onChange(charId)
    setShowSearch(false)
    setSearch('')
    setApiResults([])
  }

  // 현재 선택된 캐릭터 이름 (options에 없으면 apiResults, 그래도 없으면 char_id에서 추출)
  const selectedName = useMemo(() => {
    if (!value || value === AUTO_VOICE_FEMALE || value === AUTO_VOICE_MALE) return null
    const fromOptions = options.find(o => o.char_id === value)?.name
    if (fromOptions) return fromOptions
    const fromApi = apiResults.find(r => r.char_id === value)?.name
    if (fromApi) return fromApi
    // char_id에서 이름 추출 (char_XXX_name → name)
    const match = value.match(/^char_\d+_(.+)$/)
    return match ? match[1] : value
  }, [value, options, apiResults])

  const isAuto = !value
  const isFemale = value === AUTO_VOICE_FEMALE
  const isMale = value === AUTO_VOICE_MALE
  const isSpecific = value && !isFemale && !isMale

  return (
    <div className="space-y-2">
      {/* 프리셋 버튼들 */}
      <div className="flex flex-wrap gap-1.5">
        <button
          onClick={() => handleSelect(null)}
          className={`px-2.5 py-1.5 text-xs rounded transition-colors ${
            isAuto
              ? 'bg-ark-accent text-white'
              : 'bg-ark-black/40 text-ark-gray hover:bg-ark-black/60'
          }`}
          title={autoVoiceName ? `자동: ${autoVoiceName}` : '자동 선택'}
        >
          자동
        </button>
        {hasDefaultFemale && (
          <>
            <button
              onClick={() => handleSelect(AUTO_VOICE_FEMALE)}
              className={`px-2.5 py-1.5 text-xs rounded transition-colors ${
                isFemale
                  ? 'bg-pink-500 text-white'
                  : 'bg-ark-black/40 text-pink-400 hover:bg-ark-black/60'
              }`}
              title={autoFemaleName ? `여성: ${autoFemaleName}` : '여성 음성'}
            >
              ♀
            </button>
            <button
              onClick={() => {
                const randomVoice = defaultFemaleVoices[Math.floor(Math.random() * defaultFemaleVoices.length)]
                if (randomVoice) handleSelect(randomVoice)
              }}
              className="px-2.5 py-1.5 text-xs rounded transition-colors bg-ark-black/40 text-pink-400 hover:bg-pink-500/30"
              title="여성 기본 음성 중 랜덤 선택"
            >
              ♀🎲
            </button>
          </>
        )}
        {hasDefaultMale && (
          <>
            <button
              onClick={() => handleSelect(AUTO_VOICE_MALE)}
              className={`px-2.5 py-1.5 text-xs rounded transition-colors ${
                isMale
                  ? 'bg-blue-500 text-white'
                  : 'bg-ark-black/40 text-blue-400 hover:bg-ark-black/60'
              }`}
              title={autoMaleName ? `남성: ${autoMaleName}` : '남성 음성'}
            >
              ♂
            </button>
            <button
              onClick={() => {
                const randomVoice = defaultMaleVoices[Math.floor(Math.random() * defaultMaleVoices.length)]
                if (randomVoice) handleSelect(randomVoice)
              }}
              className="px-2.5 py-1.5 text-xs rounded transition-colors bg-ark-black/40 text-blue-400 hover:bg-blue-500/30"
              title="남성 기본 음성 중 랜덤 선택"
            >
              ♂🎲
            </button>
          </>
        )}
        <button
          onClick={() => setShowSearch(!showSearch)}
          className={`px-2.5 py-1.5 text-xs rounded transition-colors flex items-center gap-1 ${
            isSpecific
              ? 'bg-green-600 text-white'
              : 'bg-ark-black/40 text-ark-gray hover:bg-ark-black/60'
          }`}
          title="캐릭터 검색"
        >
          <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
          </svg>
          {selectedName ? (
            <span className="truncate max-w-[80px]">{selectedName}</span>
          ) : (
            '검색'
          )}
        </button>
      </div>

      {/* 검색 패널 (인라인) */}
      {showSearch && (
        <div className="bg-ark-black/60 rounded border border-ark-border p-2.5 space-y-2">
          <input
            ref={searchRef}
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="캐릭터 검색..."
            className="ark-input text-sm w-full py-1.5 px-2.5"
          />
          <div className="max-h-40 overflow-y-auto space-y-1">
            {isSearching ? (
              <div className="text-xs text-ark-gray text-center py-2">검색 중...</div>
            ) : filteredOptions.length === 0 ? (
              <div className="text-xs text-ark-gray text-center py-2">검색 결과 없음</div>
            ) : (
              filteredOptions.map(opt => {
                const isPrepared = trainedCharIds.has(opt.char_id)
                const gender = genders[opt.char_id]
                const isSelected = value === opt.char_id
                // API에서만 온 결과인지 (기존 options에 없는 캐릭터)
                const isFromApi = !options.some(o => o.char_id === opt.char_id)
                return (
                  <button
                    key={opt.char_id}
                    onClick={() => handleSelect(opt.char_id)}
                    className={`w-full text-left px-2.5 py-1.5 text-xs rounded hover:bg-ark-black/40 flex items-center gap-1.5 ${
                      isSelected ? 'bg-ark-accent/20 text-ark-accent' : 'text-ark-white'
                    }`}
                  >
                    <span className="truncate flex-1">{opt.name}</span>
                    {gender && (
                      <span className={gender === 'female' ? 'text-pink-400' : 'text-blue-400'}>
                        {gender === 'female' ? '♀' : '♂'}
                      </span>
                    )}
                    {isFromApi && <span className="text-yellow-500/70 text-[10px]">테이블</span>}
                    {!isPrepared && !isFromApi && <span className="text-ark-gray/50 text-[10px]">기본</span>}
                  </button>
                )
              })
            )}
          </div>
          <button
            onClick={() => { setShowSearch(false); setSearch(''); setApiResults([]) }}
            className="w-full text-xs text-ark-gray hover:text-ark-white py-1.5"
          >
            닫기
          </button>
        </div>
      )}
    </div>
  )
}

// 개별 캐릭터 매핑 카드
interface CharacterMappingRowProps {
  char: GroupCharacterInfo
  imageCharId: string | null  // 이미지용 char_id (이름 매칭으로 상속 가능)
  genders: Record<string, string>
  availableVoices: { char_id: string; name: string }[]
  voiceCharacters: { char_id: string; name: string }[]
  speakerVoiceMap: Record<string, string>
  setSpeakerVoice: (speakerId: string, voiceId: string | null) => Promise<void>
  getSpeakerVoice: (speakerId: string, speakerName?: string) => string | null
  defaultFemaleVoices: string[]
  defaultMaleVoices: string[]
  trainedCharIds: Set<string>
}

function CharacterMappingRow({
  char,
  imageCharId,
  genders,
  availableVoices,
  voiceCharacters,
  speakerVoiceMap,
  setSpeakerVoice,
  getSpeakerVoice,
  defaultFemaleVoices,
  defaultMaleVoices,
  trainedCharIds,
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

  // 매핑 상태: setSpeakerVoice가 백엔드에 자동 저장하므로 speakerVoiceMap에 값이 있으면 저장됨
  const isSaved = currentMapping !== undefined && currentMapping !== null

  // 매핑 초기화 (자동 선택으로 되돌리기)
  const handleClearMapping = async () => {
    setIsSaving(true)
    try {
      setSpeakerVoice(mappingKey, null)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="rounded-lg bg-ark-black/40 hover:bg-ark-black/50 transition-colors overflow-hidden border border-ark-border/50">
      <div className="flex">
        {/* 이미지 영역: NPC → 매핑 캐릭터 */}
        <div className="flex gap-2 p-3 bg-ark-black/30">
          {/* NPC 이미지 (이름 매칭으로 상속) */}
          <CharacterStanding
            charId={imageCharId}
            alt={char.name}
            className="w-28 h-44 rounded"
          />
          {/* 화살표 */}
          <div className="flex items-center px-1 text-ark-gray/50">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </div>
          {/* 매핑된 캐릭터 이미지 */}
          <CharacterStanding
            charId={mappedCharId}
            alt={mappedCharName ?? '매핑 필요'}
            className="w-28 h-44 rounded"
            showPlaceholder={true}
          />
        </div>

        {/* 정보 영역 */}
        <div className="flex-1 p-4 flex flex-col justify-between min-w-0">
          {/* 상단: 캐릭터 이름/정보 */}
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-medium text-ark-white truncate" title={char.name}>
                {char.name}
              </span>
              {charGender && (
                <span className={`text-xs px-1.5 py-0.5 rounded ${
                  charGender === 'female' ? 'bg-pink-500/20 text-pink-400' : 'bg-blue-500/20 text-blue-400'
                }`}>
                  {charGender === 'female' ? '♀' : '♂'}
                </span>
              )}
              {/* 저장 상태 표시 (자동 저장) */}
              {isSaved && (
                <span className="text-xs px-1.5 py-0.5 rounded bg-green-500/20 text-green-400 flex items-center gap-0.5">
                  <CheckIcon className="w-3 h-3" />
                  저장됨
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-1.5">
              <span className="text-xs text-ark-gray">{char.dialogue_count}대사</span>
              {char.char_id && (
                <span className="text-xs text-ark-gray/50 truncate" title={char.char_id}>
                  {char.char_id}
                </span>
              )}
            </div>
          </div>

          {/* 하단: 음성 선택 버튼들 */}
          <div className="mt-3">
            <div className="flex items-start gap-3">
              <div className="flex-1">
                <VoiceSelectButtons
                  value={currentMapping ?? ''}
                  onChange={(val) => setSpeakerVoice(mappingKey, val)}
                  options={availableVoices}
                  genders={genders}
                  trainedCharIds={trainedCharIds}
                  autoVoiceName={autoVoiceName ?? null}
                  autoFemaleName={autoFemaleName ?? null}
                  autoMaleName={autoMaleName ?? null}
                  hasDefaultFemale={defaultFemaleVoices.length > 0}
                  hasDefaultMale={defaultMaleVoices.length > 0}
                  defaultFemaleVoices={defaultFemaleVoices}
                  defaultMaleVoices={defaultMaleVoices}
                />
              </div>
              {/* 초기화 버튼 (매핑 삭제) */}
              {isSaved && (
                <div className="flex gap-1.5 shrink-0">
                  <button
                    onClick={handleClearMapping}
                    disabled={isSaving}
                    className="p-2 rounded bg-ark-black/40 text-ark-gray hover:bg-ark-black/60 hover:text-ark-white transition-colors disabled:opacity-50"
                    title="매핑 초기화 (자동 선택으로 되돌리기)"
                  >
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clipRule="evenodd" />
                    </svg>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
