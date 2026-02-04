import { useState, useMemo, useRef, useEffect } from 'react'
import { useAppStore } from '../stores/appStore'
import { ttsApi } from '../services/api'

type SortBy = 'ready' | 'files' | 'name'

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
    canFinetune,
    // 별칭 관련
    characterAliases,
    loadCharacterAliases,
    addCharacterAlias,
    removeCharacterAlias,
  } = useAppStore()

  // 로컬 상태
  const [searchQuery, setSearchQuery] = useState('')
  const [sortBy, setSortBy] = useState<SortBy>('ready')

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

  // 모달 열릴 때 데이터 로드
  useEffect(() => {
    if (isOpen) {
      loadVoiceCharacters()
      loadTrainedModels()
      loadCharacterAliases()
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
    }
  }, [isOpen, loadVoiceCharacters, loadTrainedModels, loadCharacterAliases])

  // 정렬된 캐릭터 목록
  const sortedCharacters = useMemo(() => {
    let result = [...voiceCharacters]

    // 검색 필터
    if (searchQuery) {
      result = result.filter(c => c.name.toLowerCase().includes(searchQuery.toLowerCase()))
    }

    // 정렬
    switch (sortBy) {
      case 'ready':
        result.sort((a, b) => {
          // 1순위: 기본 캐릭터 (여성/남성)
          const aIsDefault = defaultFemaleVoices.includes(a.char_id) || defaultMaleVoices.includes(a.char_id) ? 1 : 0
          const bIsDefault = defaultFemaleVoices.includes(b.char_id) || defaultMaleVoices.includes(b.char_id) ? 1 : 0
          if (aIsDefault !== bIsDefault) return bIsDefault - aIsDefault
          // 2순위: 준비됨
          const aReady = trainedCharIds.has(a.char_id) ? 1 : 0
          const bReady = trainedCharIds.has(b.char_id) ? 1 : 0
          return bReady - aReady || b.file_count - a.file_count
        })
        break
      case 'files':
        result.sort((a, b) => b.file_count - a.file_count)
        break
      case 'name':
        result.sort((a, b) => a.name.localeCompare(b.name, 'ko'))
        break
    }

    return result
  }, [voiceCharacters, trainedCharIds, searchQuery, sortBy, defaultFemaleVoices, defaultMaleVoices])

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

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 백드롭 */}
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />

      {/* 모달 */}
      <div className="relative bg-ark-dark border border-ark-border rounded-lg shadow-2xl w-[900px] max-h-[85vh] flex flex-col">
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
              <option value="ready">준비됨 우선</option>
              <option value="files">파일 수</option>
              <option value="name">이름순</option>
            </select>
          </div>
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
            <div className="grid grid-cols-4 gap-3">
              {sortedCharacters.map((char) => {
                const isReady = trainedCharIds.has(char.char_id)
                const isFemaleDefault = defaultFemaleVoices.includes(char.char_id)
                const isMaleDefault = defaultMaleVoices.includes(char.char_id)
                const isNarrator = narratorCharId === char.char_id
                const isTraining = isTrainingActive && currentTrainingJob?.char_id === char.char_id
                const aliases = characterAliases[char.char_id] || []
                const isEditingAlias = editingAliasCharId === char.char_id

                return (
                  <div
                    key={char.char_id}
                    className={`p-3 rounded border transition-colors ${
                      isReady
                        ? 'bg-green-500/10 border-green-500/30'
                        : 'bg-ark-black/30 border-ark-border'
                    }`}
                  >
                    {/* 이름 + 뱃지 */}
                    <div className="flex items-start justify-between gap-1 mb-2">
                      <span className="text-sm text-ark-white font-medium truncate" title={char.name}>
                        {char.name}
                      </span>
                      <div className="flex gap-1 flex-shrink-0">
                        {isFemaleDefault && (
                          <span className="text-[10px] px-1 py-0.5 rounded bg-pink-500/20 text-pink-400">
                            여성
                          </span>
                        )}
                        {isMaleDefault && (
                          <span className="text-[10px] px-1 py-0.5 rounded bg-blue-500/20 text-blue-400">
                            남성
                          </span>
                        )}
                        {isNarrator && (
                          <span className="text-[10px] px-1 py-0.5 rounded bg-purple-500/20 text-purple-400">
                            나레이션
                          </span>
                        )}
                      </div>
                    </div>

                    {/* 정보 */}
                    <div className="text-xs text-ark-gray mb-2">
                      <div className="flex justify-between">
                        <span>음성 파일</span>
                        <span className="text-ark-white">{char.file_count}개</span>
                      </div>
                      {isReady && (
                        <div className="flex justify-between text-green-400/80">
                          <span>전처리 세그먼트</span>
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
                            className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] bg-amber-500/20 text-amber-400 rounded"
                            title={`별칭: ${alias}`}
                          >
                            {alias}
                            {isEditingAlias && (
                              <button
                                onClick={() => handleRemoveAlias(alias)}
                                className="hover:text-red-400"
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
                            className="ark-input text-[10px] py-0.5 px-1.5 flex-1"
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleAddAlias(char.char_id)
                            }}
                          />
                          <button
                            onClick={() => handleAddAlias(char.char_id)}
                            disabled={!newAliasInput.trim()}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 disabled:opacity-50"
                          >
                            추가
                          </button>
                        </div>
                        {aliasError && editingAliasCharId === char.char_id && (
                          <p className="text-[9px] text-red-400">{aliasError}</p>
                        )}
                      </div>
                    )}

                    {/* 상태 */}
                    <div className="flex items-center gap-1 mb-2">
                      {isReady ? (
                        getModelType(char.char_id) === 'finetuned' ? (
                          <span className="text-xs text-purple-400 flex items-center gap-1">
                            <svg viewBox="0 0 24 24" className="w-3 h-3" fill="currentColor">
                              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                            </svg>
                            학습됨
                          </span>
                        ) : (
                          <span className="text-xs text-green-400 flex items-center gap-1">
                            <svg viewBox="0 0 24 24" className="w-3 h-3" fill="currentColor">
                              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                            </svg>
                            준비됨
                          </span>
                        )
                      ) : isTraining ? (
                        <span className="text-xs text-ark-orange flex items-center gap-1 ark-pulse">
                          <span className="w-2 h-2 rounded-full bg-ark-orange" />
                          {currentTrainingJob?.mode === 'finetune' ? '학습 중...' : '준비 중...'}
                        </span>
                      ) : (
                        <span className="text-xs text-ark-gray/50">준비 필요</span>
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
                                ? 'bg-pink-500/30 text-pink-400'
                                : 'bg-ark-panel text-ark-gray hover:text-ark-white'
                            }`}
                          >
                            {isFemaleDefault ? '여성 해제' : '여성'}
                          </button>
                          <button
                            onClick={() => handleToggleMaleDefault(char.char_id)}
                            className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                              isMaleDefault
                                ? 'bg-blue-500/30 text-blue-400'
                                : 'bg-ark-panel text-ark-gray hover:text-ark-white'
                            }`}
                          >
                            {isMaleDefault ? '남성 해제' : '남성'}
                          </button>
                          <button
                            onClick={() => handleToggleNarrator(char.char_id)}
                            className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                              isNarrator
                                ? 'bg-purple-500/30 text-purple-400'
                                : 'bg-ark-panel text-ark-gray hover:text-ark-white'
                            }`}
                          >
                            {isNarrator ? '나레이션 해제' : '나레이션'}
                          </button>
                          <button
                            onClick={() => handleToggleAliasEdit(char.char_id)}
                            className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                              isEditingAlias
                                ? 'bg-amber-500/30 text-amber-400'
                                : 'bg-ark-panel text-ark-gray hover:text-ark-white'
                            }`}
                            title="NPC 이름을 이 캐릭터에 매핑"
                          >
                            {isEditingAlias ? '별칭 닫기' : `별칭${aliases.length > 0 ? `(${aliases.length})` : ''}`}
                          </button>
                          <button
                            onClick={() => handleSelectForTest(char.char_id)}
                            className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                              testCharId === char.char_id
                                ? 'bg-cyan-500/30 text-cyan-400'
                                : 'bg-ark-panel text-ark-gray hover:text-ark-white'
                            }`}
                          >
                            테스트
                          </button>
                          {/* 준비된 캐릭터도 Fine-tune 가능 (finetuned가 아닌 경우) */}
                          {getModelType(char.char_id) !== 'finetuned' && (
                            <button
                              onClick={() => handleFinetuneCharacter(char.char_id)}
                              disabled={isTrainingActive}
                              className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 disabled:opacity-50"
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
                            className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400 hover:bg-green-500/30 disabled:opacity-50"
                          >
                            준비
                          </button>
                          <button
                            disabled={true}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400/40 cursor-not-allowed"
                            title="먼저 '준비'를 완료해야 학습할 수 있습니다"
                          >
                            학습
                          </button>
                          <button
                            onClick={() => handleToggleFemaleDefault(char.char_id)}
                            className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                              isFemaleDefault
                                ? 'bg-pink-500/30 text-pink-400'
                                : 'bg-ark-panel text-ark-gray hover:text-ark-white'
                            }`}
                          >
                            {isFemaleDefault ? '여성 해제' : '여성'}
                          </button>
                          <button
                            onClick={() => handleToggleMaleDefault(char.char_id)}
                            className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                              isMaleDefault
                                ? 'bg-blue-500/30 text-blue-400'
                                : 'bg-ark-panel text-ark-gray hover:text-ark-white'
                            }`}
                          >
                            {isMaleDefault ? '남성 해제' : '남성'}
                          </button>
                          <button
                            onClick={() => handleToggleNarrator(char.char_id)}
                            className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                              isNarrator
                                ? 'bg-purple-500/30 text-purple-400'
                                : 'bg-ark-panel text-ark-gray hover:text-ark-white'
                            }`}
                          >
                            {isNarrator ? '나레이션 해제' : '나레이션'}
                          </button>
                          <button
                            onClick={() => handleToggleAliasEdit(char.char_id)}
                            className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                              isEditingAlias
                                ? 'bg-amber-500/30 text-amber-400'
                                : 'bg-ark-panel text-ark-gray hover:text-ark-white'
                            }`}
                            title="NPC 이름을 이 캐릭터에 매핑"
                          >
                            {isEditingAlias ? '별칭 닫기' : `별칭${aliases.length > 0 ? `(${aliases.length})` : ''}`}
                          </button>
                        </>
                      )}
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
          {testError && (
            <p className="text-xs text-red-400">{testError}</p>
          )}
        </div>
      </div>
    </div>
  )
}
