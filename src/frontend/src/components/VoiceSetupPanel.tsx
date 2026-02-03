import { useEffect, useMemo, useState, useRef } from 'react'
import { useAppStore } from '../stores/appStore'
import { ocrApi, ttsApi } from '../services/api'

export default function VoiceSetupPanel() {
  const {
    groupCharacters,
    isLoadingCharacters,
    defaultCharId,
    setDefaultCharId,
    narratorCharId,
    setNarratorCharId,
    voiceCharacters,
    isLoadingVoiceCharacters,
    loadVoiceCharacters,
    autoPlayOnMatch,
    toggleAutoPlay,
    selectedWindowHwnd,
    windows,
    loadWindows,
    setWindow,
    startDubbing,
    isDubbingMode,
    cancelPrepare,
    // 학습 관련
    isTrainingActive,
    currentTrainingJob,
    trainingQueue,
    trainedCharIds,
    loadTrainingStatus,
    loadTrainedModels,
    startBatchTraining,
    cancelTraining,
    clearAllTrainedModels,
    unsubscribeFromTrainingProgress,
    // 에피소드 관련
    selectedEpisode,
    // GPT-SoVITS (앱 레벨 상태)
    gptSovitsStatus,
  } = useAppStore()

  // 테스트 관련 상태
  const [testCharId, setTestCharId] = useState<string | null>(null)
  const [testText, setTestText] = useState('')
  const [isTesting, setIsTesting] = useState(false)
  const [testError, setTestError] = useState<string | null>(null)
  const testAudioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    loadWindows()
    loadTrainingStatus()
    loadTrainedModels()
    loadVoiceCharacters()

    return () => {
      unsubscribeFromTrainingProgress()
      // 테스트 오디오 정리
      if (testAudioRef.current) {
        testAudioRef.current.pause()
        testAudioRef.current = null
      }
    }
  }, [])

  // 에피소드 첫 대사로 테스트 텍스트 기본값 설정
  useEffect(() => {
    if (selectedEpisode?.dialogues?.length && !testText) {
      const firstDialogue = selectedEpisode.dialogues[0]
      setTestText(firstDialogue.text)
      // 첫 대사 화자가 학습되어 있으면 자동 선택
      if (firstDialogue.speaker_id && trainedCharIds.has(firstDialogue.speaker_id)) {
        setTestCharId(firstDialogue.speaker_id)
      }
    }
  }, [selectedEpisode, trainedCharIds])

  // 게임 관련 윈도우 우선 정렬
  const sortedWindows = useMemo(() => {
    const priorityKeywords = ['arknights', '명일방주', 'android', 'bluestacks', 'nox', 'ldplayer', 'mumu']

    return [...windows].sort((a, b) => {
      const aTitle = (a.title || '').toLowerCase()
      const bTitle = (b.title || '').toLowerCase()

      const aIsPriority = priorityKeywords.some(kw => aTitle.includes(kw))
      const bIsPriority = priorityKeywords.some(kw => bTitle.includes(kw))

      if (aIsPriority && !bIsPriority) return -1
      if (!aIsPriority && bIsPriority) return 1
      return 0
    })
  }, [windows])

  // 대사 개수 기준 캐릭터 정렬 (전체 스토리 기준)
  const sortedVoiceCharacters = useMemo(() => {
    return [...voiceCharacters].sort((a, b) => {
      // 대사 개수 내림차순
      return (b.dialogue_count ?? 0) - (a.dialogue_count ?? 0)
    })
  }, [voiceCharacters])

  // 선택된 윈도우 캡처 URL
  const previewImageUrl = selectedWindowHwnd
    ? ocrApi.getWindowImageUrl(selectedWindowHwnd)
    : null

  // 캐릭터 통계
  const characterStats = useMemo(() => {
    const withVoice = groupCharacters.filter(c => c.has_voice).length
    const trained = groupCharacters.filter(c => c.char_id && trainedCharIds.has(c.char_id)).length
    const total = groupCharacters.length
    return { withVoice, trained, total }
  }, [groupCharacters, trainedCharIds])

  // 학습 가능한 캐릭터 (음성 있고 미학습)
  const trainableCharacters = useMemo(() => {
    return groupCharacters.filter(
      c => c.has_voice && c.char_id && !trainedCharIds.has(c.char_id)
    )
  }, [groupCharacters, trainedCharIds])

  // 테스트 가능한 캐릭터 (학습 완료된 캐릭터만)
  const testableCharacters = useMemo(() => {
    return voiceCharacters.filter(c => trainedCharIds.has(c.char_id))
  }, [voiceCharacters, trainedCharIds])

  // 음성 테스트 실행
  const handleTestVoice = async () => {
    if (!testCharId || !testText.trim()) return

    setIsTesting(true)
    setTestError(null)

    // 기존 테스트 오디오 중지
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

  // 일괄 학습 시작
  const handleStartBatchTraining = async () => {
    console.log('[VoiceSetup] 일괄 학습 버튼 클릭')
    console.log('[VoiceSetup] trainableCharacters:', trainableCharacters.length, trainableCharacters.map(c => c.name))
    const charIds = trainableCharacters.map(c => c.char_id!).filter(Boolean)

    // 기본 음성 캐릭터 포함 (미학습 시)
    if (defaultCharId && !trainedCharIds.has(defaultCharId) && !charIds.includes(defaultCharId)) {
      charIds.push(defaultCharId)
      console.log('[VoiceSetup] 기본 음성 추가:', defaultCharId)
    }

    // 나레이션 캐릭터도 포함 (미학습 시)
    if (narratorCharId && !trainedCharIds.has(narratorCharId) && !charIds.includes(narratorCharId)) {
      charIds.push(narratorCharId)
      console.log('[VoiceSetup] 나레이션 추가:', narratorCharId)
    }

    console.log('[VoiceSetup] charIds:', charIds)
    if (charIds.length > 0) {
      console.log('[VoiceSetup] startBatchTraining 호출')
      await startBatchTraining(charIds)
      console.log('[VoiceSetup] startBatchTraining 완료')
      // subscribeToTrainingProgress는 startBatchTraining 내부에서 이미 호출됨
    } else {
      console.log('[VoiceSetup] 학습할 캐릭터 없음')
    }
  }

  // 학습 취소
  const handleCancelTraining = async () => {
    if (currentTrainingJob) {
      await cancelTraining(currentTrainingJob.job_id)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div className="p-4 border-b border-ark-border bg-ark-panel/50 flex items-center justify-between">
        <h3 className="font-bold text-ark-white flex items-center gap-2">
          <svg viewBox="0 0 24 24" className="w-5 h-5 text-ark-orange" fill="currentColor">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.91-3c-.49 0-.9.36-.98.85C16.52 14.2 14.47 16 12 16s-4.52-1.8-4.93-4.15c-.08-.49-.49-.85-.98-.85-.61 0-1.09.54-1 1.14.49 3 2.89 5.35 5.91 5.78V20c0 .55.45 1 1 1s1-.45 1-1v-2.08c3.02-.43 5.42-2.78 5.91-5.78.1-.6-.39-1.14-1-1.14z"/>
          </svg>
          더빙 설정
        </h3>
        <button
          onClick={cancelPrepare}
          className="text-ark-gray hover:text-ark-white text-sm"
        >
          취소
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* 캐릭터 목록 (등장인물) */}
        <div className="p-4 border-b border-ark-border">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-ark-gray">등장 캐릭터</h4>
            <span className="text-xs text-ark-gray">
              음성 {characterStats.withVoice}/{characterStats.total}
            </span>
          </div>
          {isLoadingCharacters ? (
            <div className="text-center text-ark-gray py-4 ark-pulse">로딩 중...</div>
          ) : groupCharacters.length === 0 ? (
            <div className="text-center text-ark-gray py-4">캐릭터 없음</div>
          ) : (
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {groupCharacters.map((char) => (
                <div
                  key={char.char_id ?? '_narrator'}
                  className="flex items-center justify-between p-2 bg-ark-black/30 rounded text-sm"
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      char.has_voice ? 'bg-green-500' : 'bg-ark-gray/50'
                    }`} title={char.has_voice ? '음성 보유' : '음성 없음'} />
                    <span className="text-ark-white truncate">{char.name}</span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-xs text-ark-gray">
                      {char.dialogue_count}대사
                    </span>
                    {char.char_id && trainedCharIds.has(char.char_id) ? (
                      <span className="text-xs text-green-400 font-medium">준비됨</span>
                    ) : char.has_voice ? (
                      <span className="text-xs text-ark-yellow">준비 필요</span>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="mt-2 text-xs text-ark-gray/70">
            * 녹색 = 음성 데이터 보유
          </p>
        </div>

        {/* GPT-SoVITS 연결 상태 */}
        <div className="p-4 border-b border-ark-border">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium text-ark-gray">GPT-SoVITS</h4>
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${
                gptSovitsStatus?.synthesizing
                  ? 'bg-cyan-500 ark-pulse'
                  : gptSovitsStatus?.api_running
                    ? 'bg-green-500'
                    : 'bg-yellow-500'
              }`} />
              <span className={`text-xs ${
                gptSovitsStatus?.synthesizing
                  ? 'text-cyan-400'
                  : gptSovitsStatus?.api_running
                    ? 'text-green-400'
                    : 'text-yellow-400'
              }`}>
                {gptSovitsStatus?.synthesizing
                  ? '합성 중...'
                  : gptSovitsStatus?.api_running
                    ? '연결됨'
                    : '대기 중'}
              </span>
            </div>
          </div>
          {!gptSovitsStatus?.api_running && (
            <p className="mt-2 text-xs text-ark-gray/70">
              * 상단 헤더에서 GPT-SoVITS를 시작하세요
            </p>
          )}
        </div>

        {/* 음성 준비 섹션 */}
        <div className="p-4 border-b border-ark-border">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-ark-gray">음성 준비</h4>
            <span className="text-xs text-ark-gray">
              준비 완료 {characterStats.trained}/{characterStats.withVoice}
            </span>
          </div>

          {isTrainingActive && currentTrainingJob ? (
            // 학습 진행 중 - 상세 대시보드
            <div className="space-y-3">
              {/* 현재 학습 캐릭터 */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-ark-orange ark-pulse" />
                  <span className="text-sm text-ark-white font-medium">
                    {currentTrainingJob.char_name}
                  </span>
                </div>
                <span className="text-xs px-2 py-0.5 rounded bg-ark-orange/20 text-ark-orange">
                  {currentTrainingJob.status === 'preprocessing' && '오디오 분석 중'}
                  {currentTrainingJob.status === 'training' && '준비 중'}
                  {currentTrainingJob.status === 'pending' && '대기'}
                </span>
              </div>

              {/* 진행률 바 */}
              <div className="space-y-1">
                <div className="w-full bg-ark-black rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-ark-orange h-2 rounded-full transition-all duration-300"
                    style={{ width: `${(currentTrainingJob.progress * 100)}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-ark-white font-mono">
                    {(currentTrainingJob.progress * 100).toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* 로그 메시지 */}
              <div className="bg-ark-black/50 rounded p-2 border border-ark-border">
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-ark-gray font-mono">LOG</span>
                  <span className="text-ark-white truncate">
                    {currentTrainingJob.message || '준비 중...'}
                  </span>
                </div>
              </div>

              {/* 대기열 */}
              {trainingQueue.length > 0 && (
                <div className="text-xs text-ark-gray">
                  <span>대기열: </span>
                  <span className="text-ark-white">{trainingQueue.length}개</span>
                  <span className="ml-2 text-ark-gray/70">
                    ({trainingQueue.slice(0, 3).map(j => j.char_name).join(', ')}
                    {trainingQueue.length > 3 && ` 외 ${trainingQueue.length - 3}개`})
                  </span>
                </div>
              )}

              <button
                onClick={handleCancelTraining}
                className="w-full ark-btn text-sm text-red-400 hover:text-red-300 border-red-400/30"
              >
                준비 취소
              </button>
            </div>
          ) : trainableCharacters.length > 0 || (defaultCharId && !trainedCharIds.has(defaultCharId)) || (narratorCharId && !trainedCharIds.has(narratorCharId)) ? (
            // 학습 대기 상태
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="text-ark-gray">
                  {trainableCharacters.length
                    + (defaultCharId && !trainedCharIds.has(defaultCharId) && !trainableCharacters.some(c => c.char_id === defaultCharId) ? 1 : 0)
                    + (narratorCharId && !trainedCharIds.has(narratorCharId) && !trainableCharacters.some(c => c.char_id === narratorCharId) && narratorCharId !== defaultCharId ? 1 : 0)
                  }개 캐릭터 준비 가능
                </span>
              </div>
              <button
                onClick={handleStartBatchTraining}
                className="w-full ark-btn ark-btn-secondary text-sm"
              >
                음성 일괄 준비
              </button>
              <p className="text-xs text-ark-gray/50 text-center">
                * 참조 오디오 자동 선택 (Zero-shot)
              </p>
            </div>
          ) : characterStats.withVoice > 0 || defaultCharId || narratorCharId ? (
            // 모든 캐릭터 준비 완료
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-green-400">
                <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                </svg>
                <span className="text-sm">모든 캐릭터 준비 완료</span>
              </div>
              <button
                onClick={clearAllTrainedModels}
                className="w-full ark-btn text-sm text-ark-gray hover:text-ark-white border-ark-border"
              >
                준비 초기화
              </button>
            </div>
          ) : (
            // 학습 가능한 캐릭터 없음
            <p className="text-xs text-ark-gray/70">
              음성 데이터가 있는 캐릭터가 없습니다
            </p>
          )}
        </div>

        {/* 음성 설정 */}
        <div className="p-4 border-b border-ark-border space-y-4">
          <h4 className="text-sm font-medium text-ark-gray">음성 설정</h4>

          {/* 기본 음성 */}
          <div>
            <label className="block text-xs text-ark-gray mb-1">
              기본 음성 (음성 모델 없는 캐릭터용)
            </label>
            <select
              value={defaultCharId ?? ''}
              onChange={(e) => setDefaultCharId(e.target.value || null)}
              className="ark-input text-sm"
              disabled={isLoadingVoiceCharacters}
            >
              <option value="">선택 안 함</option>
              {sortedVoiceCharacters.map((char) => (
                <option key={char.char_id} value={char.char_id}>
                  {char.name} ({char.dialogue_count ?? 0}대사)
                </option>
              ))}
            </select>
            {defaultCharId && !trainedCharIds.has(defaultCharId) && (
              <p className="mt-1 text-xs text-ark-yellow">
                * 준비 필요
              </p>
            )}
          </div>

          {/* 나레이션 */}
          <div>
            <label className="block text-xs text-ark-gray mb-1">
              나레이션
            </label>
            <select
              value={narratorCharId ?? ''}
              onChange={(e) => setNarratorCharId(e.target.value || null)}
              className="ark-input text-sm"
              disabled={isLoadingVoiceCharacters}
            >
              <option value="">선택 안 함</option>
              {sortedVoiceCharacters.map((char) => (
                <option key={char.char_id} value={char.char_id}>
                  {char.name} ({char.dialogue_count ?? 0}대사)
                </option>
              ))}
            </select>
            {narratorCharId && !trainedCharIds.has(narratorCharId) && (
              <p className="mt-1 text-xs text-ark-yellow">
                * 준비 필요
              </p>
            )}
          </div>

          {/* 자동 재생 */}
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={autoPlayOnMatch}
              onChange={toggleAutoPlay}
              className="w-4 h-4 rounded border-ark-border bg-ark-black text-ark-orange focus:ring-ark-orange"
            />
            <span className="text-ark-white text-sm">매칭 시 자동 재생</span>
          </label>
        </div>

        {/* 음성 테스트 */}
        <div className="p-4 border-b border-ark-border space-y-3">
          <h4 className="text-sm font-medium text-ark-gray">음성 테스트</h4>

          {testableCharacters.length === 0 ? (
            <p className="text-xs text-ark-gray/70">
              준비된 캐릭터가 없습니다. 먼저 음성을 준비하세요.
            </p>
          ) : (
            <>
              {/* 캐릭터 선택 */}
              <div>
                <label className="block text-xs text-ark-gray mb-1">
                  테스트 캐릭터
                </label>
                <select
                  value={testCharId ?? ''}
                  onChange={(e) => setTestCharId(e.target.value || null)}
                  className="ark-input text-sm"
                >
                  <option value="">캐릭터 선택...</option>
                  {testableCharacters.map((char) => (
                    <option key={char.char_id} value={char.char_id}>
                      {char.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* 테스트 대사 */}
              <div>
                <label className="block text-xs text-ark-gray mb-1">
                  테스트 대사
                </label>
                <textarea
                  value={testText}
                  onChange={(e) => setTestText(e.target.value)}
                  placeholder="테스트할 대사를 입력하세요"
                  rows={2}
                  className="ark-input text-sm resize-none"
                />
                {selectedEpisode?.dialogues?.length && (
                  <button
                    onClick={() => {
                      const first = selectedEpisode.dialogues[0]
                      setTestText(first.text)
                      if (first.speaker_id && trainedCharIds.has(first.speaker_id)) {
                        setTestCharId(first.speaker_id)
                      }
                    }}
                    className="mt-1 text-xs text-ark-orange hover:underline"
                  >
                    에피소드 첫 대사 사용
                  </button>
                )}
              </div>

              {/* 에러 메시지 */}
              {testError && (
                <p className="text-xs text-red-400">{testError}</p>
              )}

              {/* 테스트 버튼 */}
              <button
                onClick={isTesting ? handleStopTest : handleTestVoice}
                disabled={!testCharId || !testText.trim()}
                className={`w-full ark-btn text-sm ${
                  isTesting
                    ? 'bg-red-500/20 text-red-400 border-red-400/30'
                    : 'ark-btn-secondary'
                } ${!testCharId || !testText.trim() ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                {isTesting ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="ark-pulse">●</span> 합성 중... (클릭하여 중지)
                  </span>
                ) : (
                  <span className="flex items-center justify-center gap-2">
                    <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                      <path d="M8 5v14l11-7z"/>
                    </svg>
                    음성 테스트
                  </span>
                )}
              </button>
              <p className="text-xs text-ark-gray/50 text-center">
                * 첫 합성은 GPT-SoVITS 서버 시작으로 시간이 걸릴 수 있습니다
              </p>
            </>
          )}
        </div>

        {/* 윈도우 선택 */}
        <div className="p-4">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-medium text-ark-gray">캡처 윈도우</h4>
            <button
              onClick={loadWindows}
              className="text-xs text-ark-gray hover:text-ark-white"
            >
              새로고침
            </button>
          </div>
          <select
            value={selectedWindowHwnd ?? ''}
            onChange={(e) => setWindow(Number(e.target.value))}
            className="ark-input text-sm"
          >
            <option value="">윈도우 선택...</option>
            {sortedWindows.map((win) => (
              <option key={win.hwnd} value={win.hwnd}>
                {win.title || `Window ${win.hwnd}`}
              </option>
            ))}
          </select>

          {/* 윈도우 미리보기 */}
          {previewImageUrl && (
            <div className="mt-3 bg-ark-black/50 border border-ark-border rounded overflow-hidden">
              <img
                src={previewImageUrl}
                alt="윈도우 미리보기"
                className="w-full h-32 object-contain"
                key={`preview-${selectedWindowHwnd}-${Date.now()}`}
              />
            </div>
          )}
        </div>
      </div>

      {/* 더빙 시작 버튼 */}
      <div className="p-4 border-t border-ark-border bg-ark-panel/50">
        <button
          onClick={startDubbing}
          disabled={isDubbingMode || !selectedWindowHwnd}
          className={`w-full ark-btn ark-btn-primary py-3 text-lg font-bold ${
            isDubbingMode || !selectedWindowHwnd ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {isDubbingMode ? (
            <span className="flex items-center justify-center gap-2">
              <span className="ark-pulse">●</span> 더빙 중...
            </span>
          ) : (
            <span className="flex items-center justify-center gap-2">
              <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor">
                <path d="M8 5v14l11-7z"/>
              </svg>
              더빙 시작
            </span>
          )}
        </button>
        {!selectedWindowHwnd && (
          <p className="mt-2 text-xs text-ark-gray text-center">
            캡처 윈도우를 선택하세요
          </p>
        )}
      </div>
    </div>
  )
}
