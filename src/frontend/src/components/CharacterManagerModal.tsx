import { useState, useMemo, useRef, useEffect } from 'react'
import { useAppStore } from '../stores/appStore'
import { ttsApi, voiceApi, createAvatarDownloadStream, type AvatarDownloadProgress, API_BASE } from '../services/api'

type SortBy = 'dialogues' | 'files' | 'name' | 'id'

interface CharacterManagerModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function CharacterManagerModal({ isOpen, onClose }: CharacterManagerModalProps) {
  const {
    voiceCharacters,
    isLoadingVoiceCharacters,
    loadVoiceCharacters,
    trainedCharIds,
    defaultFemaleVoices,
    addDefaultFemaleVoice,
    removeDefaultFemaleVoice,
    defaultMaleVoices,
    addDefaultMaleVoice,
    removeDefaultMaleVoice,
    narratorCharId,
    setNarratorCharId,
    startBatchTraining,
    isTrainingActive,
    currentTrainingJob,
    loadTrainedModels,
    clearAllTrainedModels,
    getModelType,
    getSegmentCount,
    gptSovitsStatus,
    checkGptSovitsStatus,
    // 별칭 관련
    characterAliases,
    loadCharacterAliases,
    addCharacterAlias,
    removeCharacterAlias,
  } = useAppStore()

  // 로컬 상태
  const [searchQuery, setSearchQuery] = useState('')
  const [sortBy, setSortBy] = useState<SortBy>('dialogues')
  const [readyFirst, setReadyFirst] = useState(true)
  const [defaultFirst, setDefaultFirst] = useState(true)  // 기본 음성/나레이터 우선

  // 테스트 관련 상태
  const [testCharId, setTestCharId] = useState<string | null>(null)
  const [testText, setTestText] = useState('의학 테스트 보고서 참고 결과 비감염자로 확인.')
  const [isTesting, setIsTesting] = useState(false)
  const [testError, setTestError] = useState<string | null>(null)
  const testAudioRef = useRef<HTMLAudioElement | null>(null)

  // 별칭 편집 상태
  const [editingAliasCharId, setEditingAliasCharId] = useState<string | null>(null)
  const [newAliasInput, setNewAliasInput] = useState('')
  const [aliasError, setAliasError] = useState<string | null>(null)

  // 성별/이미지 데이터
  const [genders, setGenders] = useState<Record<string, string>>({})
  const [avatars, setAvatars] = useState<Record<string, string>>({})  // 얼굴 아바타
  const [portraits, setPortraits] = useState<Record<string, string>>({})  // 스탠딩 이미지

  // 이미지 캐시 상태
  const [imageCacheStatus, setImageCacheStatus] = useState<{
    total: number
    avatars: { cached: number }
    portraits: { cached: number }
  } | null>(null)
  const [isDownloadingImages, setIsDownloadingImages] = useState(false)
  const [imageDownloadProgress, setImageDownloadProgress] = useState<AvatarDownloadProgress | null>(null)
  const imageDownloadRef = useRef<{ close: () => void } | null>(null)

  // 이미지 캐시 상태 로드 함수
  const loadImageCacheStatus = async () => {
    try {
      const status = await voiceApi.getAvatarCacheStatus()
      setImageCacheStatus({
        total: status.total,
        avatars: status.avatars,
        portraits: status.portraits,
      })
    } catch {
      // 무시
    }
  }

  // 이미지 목록 로드 함수
  const loadImages = async () => {
    const [avatarRes, portraitRes] = await Promise.all([
      voiceApi.listAvatars().catch(() => ({ avatars: {} })),
      voiceApi.listPortraits().catch(() => ({ portraits: {} })),
    ])
    // 상대 URL에 API_BASE 붙이기
    const avatarsWithBase: Record<string, string> = {}
    for (const [charId, url] of Object.entries(avatarRes.avatars)) {
      avatarsWithBase[charId] = `${API_BASE}${url}`
    }
    const portraitsWithBase: Record<string, string> = {}
    for (const [charId, url] of Object.entries(portraitRes.portraits)) {
      portraitsWithBase[charId] = `${API_BASE}${url}`
    }
    setAvatars(avatarsWithBase)
    setPortraits(portraitsWithBase)
  }

  // 모달 열릴 때 데이터 로드
  useEffect(() => {
    if (isOpen) {
      loadVoiceCharacters()
      loadTrainedModels()
      loadCharacterAliases()
      loadImageCacheStatus()
      loadImages()

      // 성별 데이터 로드
      voiceApi.listGenders().catch(() => ({ genders: {} })).then((res) => {
        setGenders(res.genders)
      })
    }
    return () => {
      // 모달 닫힐 때 테스트 오디오 정리
      if (testAudioRef.current) {
        testAudioRef.current.pause()
        testAudioRef.current = null
      }
      // 별칭 편집 상태 초기화
      setEditingAliasCharId(null)
      setNewAliasInput('')
      setAliasError(null)
      // 이미지 다운로드 스트림 정리
      if (imageDownloadRef.current) {
        imageDownloadRef.current.close()
        imageDownloadRef.current = null
      }
    }
  }, [isOpen, loadVoiceCharacters, loadTrainedModels, loadCharacterAliases])

  // 정렬된 캐릭터 목록
  const sortedCharacters = useMemo(() => {
    let result = [...voiceCharacters]

    // 검색 필터
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(c =>
        c.name.toLowerCase().includes(query) ||
        c.char_id.toLowerCase().includes(query)
      )
    }

    // 기본 정렬
    const sortFn = (a: typeof result[0], b: typeof result[0]) => {
      switch (sortBy) {
        case 'dialogues':
          return (b.dialogue_count || 0) - (a.dialogue_count || 0)
        case 'files':
          return b.file_count - a.file_count
        case 'name':
          return a.name.localeCompare(b.name, 'ko')
        case 'id':
          // char_XXX_name 형식에서 숫자 추출하여 정렬 (출시순에 가까움)
          const aNum = parseInt(a.char_id.match(/char_(\d+)/)?.[1] || '0')
          const bNum = parseInt(b.char_id.match(/char_(\d+)/)?.[1] || '0')
          return bNum - aNum  // 최신순
        default:
          return 0
      }
    }

    result.sort((a, b) => {
      // 기본 음성/나레이터 우선 토글이 켜져 있으면 먼저
      if (defaultFirst) {
        const aDefault = (
          defaultFemaleVoices.includes(a.char_id) ||
          defaultMaleVoices.includes(a.char_id) ||
          narratorCharId === a.char_id
        ) ? 1 : 0
        const bDefault = (
          defaultFemaleVoices.includes(b.char_id) ||
          defaultMaleVoices.includes(b.char_id) ||
          narratorCharId === b.char_id
        ) ? 1 : 0
        if (aDefault !== bDefault) return bDefault - aDefault
      }
      // 준비됨 우선 토글이 켜져 있으면 준비된 캐릭터 먼저
      if (readyFirst) {
        const aReady = trainedCharIds.has(a.char_id) ? 1 : 0
        const bReady = trainedCharIds.has(b.char_id) ? 1 : 0
        if (aReady !== bReady) return bReady - aReady
      }
      return sortFn(a, b)
    })

    return result
  }, [voiceCharacters, trainedCharIds, searchQuery, sortBy, readyFirst, defaultFirst, defaultFemaleVoices, defaultMaleVoices, narratorCharId])

  // 통계
  const stats = useMemo(() => ({
    total: voiceCharacters.length,
    ready: voiceCharacters.filter(c => trainedCharIds.has(c.char_id)).length,
    femaleCount: defaultFemaleVoices.length,
    maleCount: defaultMaleVoices.length,
  }), [voiceCharacters, trainedCharIds, defaultFemaleVoices, defaultMaleVoices])

  // 여성 기본 음성 토글
  const handleToggleFemaleDefault = (charId: string) => {
    const index = defaultFemaleVoices.indexOf(charId)
    if (index >= 0) {
      removeDefaultFemaleVoice(index)
    } else {
      addDefaultFemaleVoice(charId)
    }
  }

  // 남성 기본 음성 토글
  const handleToggleMaleDefault = (charId: string) => {
    const index = defaultMaleVoices.indexOf(charId)
    if (index >= 0) {
      removeDefaultMaleVoice(index)
    } else {
      addDefaultMaleVoice(charId)
    }
  }

  // 나레이션 토글
  const handleToggleNarrator = (charId: string) => {
    if (narratorCharId === charId) {
      setNarratorCharId(null)
    } else {
      setNarratorCharId(charId)
    }
  }

  // 개별 캐릭터 준비 (Zero-shot)
  const handlePrepareCharacter = async (charId: string) => {
    await startBatchTraining([charId], 'prepare')
  }

  // 개별 캐릭터 학습 (Fine-tuning)
  const handleFinetuneCharacter = async (charId: string) => {
    await startBatchTraining([charId], 'finetune')
  }

  // 음성 테스트
  const handleTestVoice = async () => {
    if (!testCharId || !testText.trim()) return

    setIsTesting(true)
    setTestError(null)

    if (testAudioRef.current) {
      testAudioRef.current.pause()
      URL.revokeObjectURL(testAudioRef.current.src)
      testAudioRef.current = null
    }

    try {
      const audioBlob = await ttsApi.synthesize(testText.trim(), testCharId)
      const audioUrl = URL.createObjectURL(audioBlob)

      const audio = new Audio(audioUrl)
      testAudioRef.current = audio

      audio.onended = () => {
        setIsTesting(false)
        URL.revokeObjectURL(audioUrl)
      }
      audio.onerror = () => {
        setIsTesting(false)
        setTestError('오디오 재생 실패')
        URL.revokeObjectURL(audioUrl)
      }

      await audio.play()
    } catch (error: any) {
      console.error('[Test] 음성 합성 실패:', error)
      setTestError(error?.response?.data?.detail || error?.message || '음성 합성 실패')
      setIsTesting(false)
    }
  }

  // 테스트 중지
  const handleStopTest = () => {
    if (testAudioRef.current) {
      testAudioRef.current.pause()
      testAudioRef.current = null
    }
    setIsTesting(false)
  }

  // 캐릭터를 테스트 대상으로 선택
  const handleSelectForTest = (charId: string) => {
    setTestCharId(charId)
  }

  // 별칭 편집 토글
  const handleToggleAliasEdit = (charId: string) => {
    if (editingAliasCharId === charId) {
      setEditingAliasCharId(null)
      setNewAliasInput('')
      setAliasError(null)
    } else {
      setEditingAliasCharId(charId)
      setNewAliasInput('')
      setAliasError(null)
    }
  }

  // 별칭 추가
  const handleAddAlias = async (charId: string) => {
    const alias = newAliasInput.trim()
    if (!alias) return

    try {
      setAliasError(null)
      await addCharacterAlias(charId, alias)
      setNewAliasInput('')
    } catch (error: any) {
      setAliasError(error?.response?.data?.detail || '별칭 추가 실패')
    }
  }

  // 별칭 삭제
  const handleRemoveAlias = async (alias: string) => {
    try {
      setAliasError(null)
      await removeCharacterAlias(alias)
    } catch (error: any) {
      setAliasError(error?.response?.data?.detail || '별칭 삭제 실패')
    }
  }

  // 이미지 다운로드 시작 (avatar + portrait 둘 다)
  const handleStartImageDownload = () => {
    if (isDownloadingImages) return

    setIsDownloadingImages(true)
    setImageDownloadProgress({ status: 'starting', total: 0, completed: 0 })

    imageDownloadRef.current = createAvatarDownloadStream(undefined, {
      onProgress: (progress) => {
        setImageDownloadProgress(progress)
      },
      onComplete: () => {
        setIsDownloadingImages(false)
        setImageDownloadProgress(null)
        loadImageCacheStatus()
        loadImages()
      },
      onError: (error) => {
        console.error('[Image] 다운로드 실패:', error)
        setIsDownloadingImages(false)
        setImageDownloadProgress({ status: 'error', total: 0, completed: 0, error })
      },
    })
  }

  // 이미지 캐시 삭제
  const handleClearImageCache = async () => {
    try {
      await voiceApi.clearImageCache('both')
      setImageCacheStatus(prev => prev ? {
        ...prev,
        avatars: { cached: 0 },
        portraits: { cached: 0 },
      } : null)
      setAvatars({})
      setPortraits({})
    } catch (error) {
      console.error('[Image] 캐시 삭제 실패:', error)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 백드롭 */}
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />

      {/* 모달 */}
      <div className="relative bg-ark-dark border border-ark-border rounded-lg shadow-2xl w-[1100px] max-h-[85vh] flex flex-col">
        {/* 헤더 */}
        <div className="flex items-center justify-between p-4 border-b border-ark-border">
          <h2 className="text-lg font-bold text-ark-white flex items-center gap-2">
            <svg viewBox="0 0 24 24" className="w-5 h-5 text-ark-orange" fill="currentColor">
              <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
            </svg>
            캐릭터 음성 관리
          </h2>
          <button onClick={onClose} className="text-ark-gray hover:text-ark-white">
            <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>

        {/* 검색 및 정렬 */}
        <div className="p-4 border-b border-ark-border flex items-center gap-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="캐릭터 검색..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="ark-input w-full"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-ark-gray">정렬:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortBy)}
              className="ark-input text-sm"
            >
              <option value="dialogues">대사 수</option>
              <option value="files">파일 수</option>
              <option value="id">출시순</option>
              <option value="name">이름순</option>
            </select>
          </div>
          <label className="flex items-center gap-1.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={defaultFirst}
              onChange={(e) => setDefaultFirst(e.target.checked)}
              className="w-3.5 h-3.5 rounded border-ark-border bg-ark-black text-ark-orange focus:ring-ark-orange"
            />
            <span className="text-xs text-ark-gray">기본 우선</span>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={readyFirst}
              onChange={(e) => setReadyFirst(e.target.checked)}
              className="w-3.5 h-3.5 rounded border-ark-border bg-ark-black text-ark-orange focus:ring-ark-orange"
            />
            <span className="text-xs text-ark-gray">준비됨 우선</span>
          </label>
          <div className="flex items-center gap-3">
            <span className="text-sm text-ark-gray">
              {stats.ready}/{stats.total} 준비됨
            </span>
            {stats.ready > 0 && (
              <button
                onClick={clearAllTrainedModels}
                className="text-xs px-2 py-1 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
                title="모든 준비 데이터 초기화"
              >
                준비 초기화
              </button>
            )}
          </div>
        </div>

        {/* 기본 음성 & 나레이션 표시 */}
        <div className="p-4 border-b border-ark-border bg-ark-black/30 space-y-2">
          {/* 여성 기본 음성 */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-ark-gray whitespace-nowrap w-24">기본(여성):</span>
            <div className="flex flex-wrap gap-1 flex-1">
              {defaultFemaleVoices.length === 0 ? (
                <span className="text-xs text-ark-gray/50">설정 안 됨</span>
              ) : (
                defaultFemaleVoices.map((charId, idx) => {
                  const char = voiceCharacters.find(c => c.char_id === charId)
                  return (
                    <span
                      key={charId}
                      className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-pink-500/20 text-pink-400 rounded"
                    >
                      {char?.name || charId}
                      <button
                        onClick={() => removeDefaultFemaleVoice(idx)}
                        className="hover:text-red-400"
                      >
                        ×
                      </button>
                    </span>
                  )
                })
              )}
            </div>
          </div>

          {/* 남성 기본 음성 */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-ark-gray whitespace-nowrap w-24">기본(남성):</span>
            <div className="flex flex-wrap gap-1 flex-1">
              {defaultMaleVoices.length === 0 ? (
                <span className="text-xs text-ark-gray/50">설정 안 됨</span>
              ) : (
                defaultMaleVoices.map((charId, idx) => {
                  const char = voiceCharacters.find(c => c.char_id === charId)
                  return (
                    <span
                      key={charId}
                      className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-blue-500/20 text-blue-400 rounded"
                    >
                      {char?.name || charId}
                      <button
                        onClick={() => removeDefaultMaleVoice(idx)}
                        className="hover:text-red-400"
                      >
                        ×
                      </button>
                    </span>
                  )
                })
              )}
            </div>
          </div>

          {/* 나레이션 */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-ark-gray whitespace-nowrap w-24">나레이션:</span>
            <div className="flex flex-wrap gap-1 flex-1">
              {narratorCharId ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-purple-500/20 text-purple-400 rounded">
                  {voiceCharacters.find(c => c.char_id === narratorCharId)?.name || narratorCharId}
                  <button
                    onClick={() => setNarratorCharId(null)}
                    className="hover:text-red-400"
                  >
                    ×
                  </button>
                </span>
              ) : (
                <span className="text-xs text-ark-gray/50">설정 안 됨</span>
              )}
            </div>
          </div>
          <p className="text-[10px] text-ark-gray/50 mt-1">
            * 기본(여성): 일반 캐릭터 / 기본(남성): "남자", "남성", "소년", "청년" 포함 캐릭터
          </p>

          {/* 이미지 캐시 관리 */}
          <div className="flex items-center justify-between pt-2 mt-2 border-t border-ark-border/30">
            <div className="flex items-center gap-3 text-xs text-ark-gray">
              <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/>
              </svg>
              <span>
                얼굴: {imageCacheStatus ? `${imageCacheStatus.avatars.cached}/${imageCacheStatus.total}` : '...'}
              </span>
              <span>
                스탠딩: {imageCacheStatus ? `${imageCacheStatus.portraits.cached}/${imageCacheStatus.total}` : '...'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {isDownloadingImages ? (
                <div className="flex items-center gap-2">
                  <div className="w-24 h-2 bg-ark-border rounded-full overflow-hidden">
                    <div
                      className="h-full bg-ark-orange transition-all"
                      style={{
                        width: imageDownloadProgress?.total
                          ? `${(imageDownloadProgress.completed / imageDownloadProgress.total) * 100}%`
                          : '0%'
                      }}
                    />
                  </div>
                  <span className="text-[10px] text-ark-gray">
                    {imageDownloadProgress?.completed || 0}/{imageDownloadProgress?.total || 0}
                  </span>
                </div>
              ) : (
                <>
                  <button
                    onClick={handleStartImageDownload}
                    className="text-[10px] px-2 py-1 rounded bg-ark-orange/20 text-ark-orange hover:bg-ark-orange/30"
                  >
                    다운로드
                  </button>
                  {imageCacheStatus && (imageCacheStatus.avatars.cached > 0 || imageCacheStatus.portraits.cached > 0) && (
                    <button
                      onClick={handleClearImageCache}
                      className="text-[10px] px-2 py-1 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20"
                    >
                      캐시 삭제
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        {/* 캐릭터 그리드 */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoadingVoiceCharacters ? (
            <div className="text-center text-ark-gray py-8 ark-pulse">로딩 중...</div>
          ) : sortedCharacters.length === 0 ? (
            <div className="text-center text-ark-gray py-8">
              {searchQuery ? '검색 결과가 없습니다' : '캐릭터가 없습니다'}
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-4">
              {sortedCharacters.map((char) => {
                const isReady = trainedCharIds.has(char.char_id)
                const isFemaleDefault = defaultFemaleVoices.includes(char.char_id)
                const isMaleDefault = defaultMaleVoices.includes(char.char_id)
                const isNarrator = narratorCharId === char.char_id
                const isTraining = isTrainingActive && currentTrainingJob?.char_id === char.char_id
                const aliases = characterAliases[char.char_id] || []
                const isEditingAlias = editingAliasCharId === char.char_id

                const charGender = genders[char.char_id]
                const charAvatar = avatars[char.char_id]  // 얼굴 (원형 초상화용)
                const charPortrait = portraits[char.char_id]  // 스탠딩 (배경용)

                return (
                  <div
                    key={char.char_id}
                    className={`relative rounded-lg border overflow-hidden min-h-[180px] ${
                      isReady
                        ? 'border-green-500/50'
                        : 'border-ark-border'
                    }`}
                  >
                    {/* 기본 배경 */}
                    <div className={`absolute inset-0 ${isReady ? 'bg-green-500/10' : 'bg-ark-black/50'}`} />

                    {/* 스탠딩 이미지 (우측에, mask로 페이드) */}
                    {charPortrait && (
                      <div className="absolute -right-4 top-0 bottom-0 w-1/2 pointer-events-none">
                        <img
                          src={charPortrait}
                          alt=""
                          className="w-full h-full object-cover object-top"
                          style={{
                            maskImage: 'linear-gradient(to left, black 30%, transparent 90%)',
                            WebkitMaskImage: 'linear-gradient(to left, black 30%, transparent 90%)',
                          }}
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = 'none'
                          }}
                        />
                      </div>
                    )}

                    {/* 컨텐츠 */}
                    <div className="relative z-10 p-3 h-full flex flex-col">
                      {/* 헤더: 아바타 + 이름 + 뱃지 */}
                      <div className="flex items-start gap-2 mb-2">
                        {/* 원형 아바타 (얼굴 이미지) */}
                        <div className="w-12 h-12 rounded-full bg-ark-black/70 overflow-hidden flex-shrink-0 border-2 border-white/20">
                          {charAvatar ? (
                            <img
                              src={charAvatar}
                              alt={char.name}
                              className="w-full h-full object-cover"
                              onError={(e) => {
                                (e.target as HTMLImageElement).style.display = 'none'
                              }}
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center text-ark-gray text-sm">
                              ?
                            </div>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="text-base text-white font-bold truncate drop-shadow-lg" title={char.name}>
                              {char.name}
                            </span>
                            {/* 성별 */}
                            {charGender && (
                              <span className={`text-xs px-1.5 py-0.5 rounded ${
                                charGender === 'female'
                                  ? 'bg-pink-500/30 text-pink-300'
                                  : 'bg-blue-500/30 text-blue-300'
                              }`}>
                                {charGender === 'female' ? '♀' : '♂'}
                              </span>
                            )}
                          </div>
                          {/* 기본 음성 뱃지 */}
                          <div className="flex gap-1 mt-1 flex-wrap">
                            {isFemaleDefault && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-pink-500/40 text-pink-200">
                                기본(여)
                              </span>
                            )}
                            {isMaleDefault && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/40 text-blue-200">
                                기본(남)
                              </span>
                            )}
                            {isNarrator && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/40 text-purple-200">
                                나레이션
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* 정보 - 하단에 고정 */}
                      <div className="mt-auto">
                        <div className="text-xs text-white/80 space-y-0.5 mb-2 bg-black/40 rounded px-1.5 py-1 inline-block">
                          <div className="flex justify-between">
                            <span>대사</span>
                            <span className="text-white font-medium">{char.dialogue_count?.toLocaleString() || 0}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>음성</span>
                            <span className="text-white font-medium">{char.file_count}개</span>
                          </div>
                          {isReady && (
                            <div className="flex justify-between text-green-300">
                              <span>세그먼트</span>
                              <span>{getSegmentCount(char.char_id)}개</span>
                            </div>
                          )}
                        </div>

                        {/* 별칭 표시 */}
                        {aliases.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-2">
                            {aliases.map((alias) => (
                              <span
                                key={alias}
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] bg-amber-500/40 text-amber-200 rounded"
                                title={`별칭: ${alias}`}
                              >
                                {alias}
                                {isEditingAlias && (
                                  <button
                                    onClick={() => handleRemoveAlias(alias)}
                                    className="hover:text-red-300"
                                  >
                                    ×
                                  </button>
                                )}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* 별칭 편집 UI */}
                        {isEditingAlias && (
                          <div className="mb-2 space-y-1">
                            <div className="flex gap-1">
                              <input
                                type="text"
                                value={newAliasInput}
                                onChange={(e) => setNewAliasInput(e.target.value)}
                                placeholder="별칭 추가..."
                                className="ark-input text-[10px] py-0.5 px-1.5 flex-1 bg-black/50"
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') handleAddAlias(char.char_id)
                                }}
                              />
                              <button
                                onClick={() => handleAddAlias(char.char_id)}
                                disabled={!newAliasInput.trim()}
                                className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/40 text-amber-200 hover:bg-amber-500/60 disabled:opacity-50"
                              >
                                추가
                              </button>
                            </div>
                            {aliasError && editingAliasCharId === char.char_id && (
                              <p className="text-[9px] text-red-300">{aliasError}</p>
                            )}
                          </div>
                        )}

                        {/* 상태 */}
                        <div className="flex items-center gap-1 mb-2">
                          {isReady ? (
                            getModelType(char.char_id) === 'finetuned' ? (
                              <span className="text-xs text-purple-300 flex items-center gap-1">
                                <svg viewBox="0 0 24 24" className="w-3 h-3" fill="currentColor">
                                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                                </svg>
                                학습됨
                              </span>
                            ) : (
                              <span className="text-xs text-green-300 flex items-center gap-1">
                                <svg viewBox="0 0 24 24" className="w-3 h-3" fill="currentColor">
                                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                                </svg>
                                준비됨
                              </span>
                            )
                          ) : isTraining ? (
                            <div className="flex flex-col gap-1 w-full">
                              <div className="flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-ark-orange ark-pulse" />
                                <span className="text-xs text-ark-orange">
                                  {currentTrainingJob?.mode === 'finetune' ? '학습 중' : '준비 중'}
                                  {currentTrainingJob?.progress != null && ` ${Math.round(currentTrainingJob.progress * 100)}%`}
                                </span>
                              </div>
                              {currentTrainingJob?.progress != null && (
                                <div className="w-full h-1 bg-white/20 rounded-full overflow-hidden">
                                  <div
                                    className="h-full bg-ark-orange transition-all duration-300"
                                    style={{ width: `${Math.round(currentTrainingJob.progress * 100)}%` }}
                                  />
                                </div>
                              )}
                              {currentTrainingJob?.message && (
                                <span className="text-[10px] text-white/50 truncate" title={currentTrainingJob.message}>
                                  {currentTrainingJob.message}
                                </span>
                              )}
                            </div>
                          ) : (
                            <span className="text-xs text-white/40">준비 필요</span>
                          )}
                        </div>

                        {/* 액션 버튼 */}
                        <div className="flex flex-wrap gap-1">
                          {isReady ? (
                            <>
                              <button
                                onClick={() => handleToggleFemaleDefault(char.char_id)}
                                className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                                  isFemaleDefault
                                    ? 'bg-pink-500/50 text-pink-200'
                                    : 'bg-white/10 text-white/70 hover:bg-white/20'
                                }`}
                              >
                                {isFemaleDefault ? '여성 해제' : '여성'}
                              </button>
                              <button
                                onClick={() => handleToggleMaleDefault(char.char_id)}
                                className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                                  isMaleDefault
                                    ? 'bg-blue-500/50 text-blue-200'
                                    : 'bg-white/10 text-white/70 hover:bg-white/20'
                                }`}
                              >
                                {isMaleDefault ? '남성 해제' : '남성'}
                              </button>
                              <button
                                onClick={() => handleToggleNarrator(char.char_id)}
                                className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                                  isNarrator
                                    ? 'bg-purple-500/50 text-purple-200'
                                    : 'bg-white/10 text-white/70 hover:bg-white/20'
                                }`}
                              >
                                {isNarrator ? '나레이션 해제' : '나레이션'}
                              </button>
                              <button
                                onClick={() => handleToggleAliasEdit(char.char_id)}
                                className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                                  isEditingAlias
                                    ? 'bg-amber-500/50 text-amber-200'
                                    : 'bg-white/10 text-white/70 hover:bg-white/20'
                                }`}
                                title="NPC 이름을 이 캐릭터에 매핑"
                              >
                                {isEditingAlias ? '별칭 닫기' : `별칭${aliases.length > 0 ? `(${aliases.length})` : ''}`}
                              </button>
                              <button
                                onClick={() => handleSelectForTest(char.char_id)}
                                className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                                  testCharId === char.char_id
                                    ? 'bg-cyan-500/50 text-cyan-200'
                                    : 'bg-white/10 text-white/70 hover:bg-white/20'
                                }`}
                              >
                                테스트
                              </button>
                              {getModelType(char.char_id) !== 'finetuned' && (
                                <button
                                  onClick={() => handleFinetuneCharacter(char.char_id)}
                                  disabled={isTrainingActive}
                                  className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/40 text-purple-200 hover:bg-purple-500/60 disabled:opacity-50"
                                  title="실제 모델 학습 (시간 소요)"
                                >
                                  학습
                                </button>
                              )}
                            </>
                          ) : (
                            <>
                              <button
                                onClick={() => handlePrepareCharacter(char.char_id)}
                                disabled={isTrainingActive}
                                className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/40 text-green-200 hover:bg-green-500/60 disabled:opacity-50"
                              >
                                준비
                              </button>
                              <button
                                disabled={true}
                                className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300/40 cursor-not-allowed"
                                title="먼저 '준비'를 완료해야 학습할 수 있습니다"
                              >
                                학습
                              </button>
                              <button
                                onClick={() => handleToggleFemaleDefault(char.char_id)}
                                className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                                  isFemaleDefault
                                    ? 'bg-pink-500/50 text-pink-200'
                                    : 'bg-white/10 text-white/70 hover:bg-white/20'
                                }`}
                              >
                                {isFemaleDefault ? '여성 해제' : '여성'}
                              </button>
                              <button
                                onClick={() => handleToggleMaleDefault(char.char_id)}
                                className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                                  isMaleDefault
                                    ? 'bg-blue-500/50 text-blue-200'
                                    : 'bg-white/10 text-white/70 hover:bg-white/20'
                                }`}
                              >
                                {isMaleDefault ? '남성 해제' : '남성'}
                              </button>
                              <button
                                onClick={() => handleToggleNarrator(char.char_id)}
                                className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                                  isNarrator
                                    ? 'bg-purple-500/50 text-purple-200'
                                    : 'bg-white/10 text-white/70 hover:bg-white/20'
                                }`}
                              >
                                {isNarrator ? '나레이션 해제' : '나레이션'}
                              </button>
                              <button
                                onClick={() => handleToggleAliasEdit(char.char_id)}
                                className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                                  isEditingAlias
                                    ? 'bg-amber-500/50 text-amber-200'
                                    : 'bg-white/10 text-white/70 hover:bg-white/20'
                                }`}
                                title="NPC 이름을 이 캐릭터에 매핑"
                              >
                                {isEditingAlias ? '별칭 닫기' : `별칭${aliases.length > 0 ? `(${aliases.length})` : ''}`}
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* 음성 테스트 섹션 */}
        <div className="p-4 border-t border-ark-border bg-ark-black/30 space-y-3">
          <div className="flex items-center gap-3">
            <span className="text-sm text-ark-gray whitespace-nowrap">음성 테스트:</span>
            <select
              value={testCharId ?? ''}
              onChange={(e) => setTestCharId(e.target.value || null)}
              className="ark-input text-sm flex-1"
            >
              <option value="">캐릭터 선택...</option>
              {voiceCharacters
                .filter(c => trainedCharIds.has(c.char_id))
                .map(c => (
                  <option key={c.char_id} value={c.char_id}>{c.name}</option>
                ))}
            </select>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={testText}
              onChange={(e) => setTestText(e.target.value)}
              placeholder="테스트 텍스트 입력..."
              className="ark-input text-sm flex-1"
            />
            <button
              onClick={isTesting ? handleStopTest : handleTestVoice}
              disabled={!testCharId || !testText.trim()}
              className={`ark-btn text-sm px-4 py-2 flex-shrink-0 ${
                isTesting
                  ? 'bg-red-500/20 text-red-400 border-red-400/30'
                  : 'ark-btn-primary'
              } ${!testCharId || !testText.trim() ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {isTesting ? '중지' : '테스트'}
            </button>
          </div>
          {/* 제로샷 강제 모드 토글 (테스트/비교용) */}
          <div className="flex items-center justify-between pt-2 border-t border-ark-border/50">
            <div className="flex items-center gap-2">
              <span className="text-xs text-ark-gray">제로샷 강제 모드</span>
              <span className="text-[10px] text-ark-gray/50">(학습 모델 무시, 품질 비교용)</span>
            </div>
            <button
              onClick={async () => {
                try {
                  const newState = !gptSovitsStatus?.force_zero_shot
                  await ttsApi.setForceZeroShot(newState)
                  checkGptSovitsStatus()
                } catch (e) {
                  console.error('제로샷 모드 토글 실패:', e)
                }
              }}
              disabled={!gptSovitsStatus?.api_running}
              className={`relative w-10 h-5 rounded-full transition-colors ${
                !gptSovitsStatus?.api_running
                  ? 'bg-ark-gray/20 cursor-not-allowed'
                  : gptSovitsStatus?.force_zero_shot
                    ? 'bg-amber-500'
                    : 'bg-ark-gray/30'
              }`}
              title={!gptSovitsStatus?.api_running
                ? 'GPT-SoVITS 연결 필요'
                : gptSovitsStatus?.force_zero_shot
                  ? '클릭하면 학습 모델 사용으로 전환'
                  : '클릭하면 제로샷 모드로 전환'}
            >
              <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                gptSovitsStatus?.force_zero_shot ? 'translate-x-5' : 'translate-x-0.5'
              }`} />
            </button>
          </div>
          {testError && (
            <p className="text-xs text-red-400">{testError}</p>
          )}
        </div>
      </div>
    </div>
  )
}
