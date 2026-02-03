import { useEffect, useMemo } from 'react'
import { useAppStore, AUTO_VOICE_FEMALE, AUTO_VOICE_MALE, simpleHash } from '../stores/appStore'

export default function VoiceSetupPanel() {
  const {
    groupCharacters,
    episodeCharacters,
    episodeNarrationCount,
    isLoadingCharacters,
    isLoadingEpisodeCharacters,
    voiceCharacters,
    loadVoiceCharacters,
    autoPlayOnMatch,
    toggleAutoPlay,
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
    unsubscribeFromTrainingProgress,
    // 에피소드 관련
    selectedEpisodeId,
    loadEpisodeCharacters,
    // GPT-SoVITS (앱 레벨 상태)
    gptSovitsStatus,
    // 렌더링 (사전 더빙)
    isRendering,
    renderProgress,
    cachedEpisodes,
    startRender,
    cancelRender,
    deleteRenderCache,
    loadRenderStatus,
    // 음성 매핑
    speakerVoiceMap,
    setSpeakerVoice,
    defaultFemaleVoices,
    defaultMaleVoices,
    getSpeakerVoice,
  } = useAppStore()

  useEffect(() => {
    loadTrainingStatus()
    loadTrainedModels()
    loadVoiceCharacters()
    loadRenderStatus()

    return () => {
      unsubscribeFromTrainingProgress()
    }
  }, [])

  // 현재 에피소드 캐릭터 로드 (에피소드 변경 시)
  useEffect(() => {
    if (selectedEpisodeId) {
      console.log('[VoiceSetupPanel] 에피소드 캐릭터 로드:', selectedEpisodeId)
      loadEpisodeCharacters(selectedEpisodeId)
    }
  }, [selectedEpisodeId, loadEpisodeCharacters])

  // 캐릭터 통계 (현재 에피소드 기준, voice_char_id로 학습 완료 체크)
  const characterStats = useMemo(() => {
    const withVoice = episodeCharacters.filter(c => c.has_voice).length
    // voice_char_id가 있으면 그걸로 체크, 없으면 char_id로 체크
    const trained = episodeCharacters.filter(c => {
      const voiceId = c.voice_char_id || c.char_id
      return voiceId && trainedCharIds.has(voiceId)
    }).length
    const total = episodeCharacters.length
    return { withVoice, trained, total }
  }, [episodeCharacters, trainedCharIds])

  // 학습 가능한 캐릭터 (음성 있고 미학습) - 현재 에피소드 기준
  const trainableCharacters = useMemo(() => {
    return episodeCharacters.filter(c => {
      if (!c.has_voice) return false
      const voiceId = c.voice_char_id || c.char_id
      return voiceId && !trainedCharIds.has(voiceId)
    })
  }, [episodeCharacters, trainedCharIds])

  // 미학습 기본 캐릭터 수
  const untrainedDefaultCount = useMemo(() => {
    return [...defaultFemaleVoices, ...defaultMaleVoices].filter(id => !trainedCharIds.has(id)).length
  }, [defaultFemaleVoices, defaultMaleVoices, trainedCharIds])

  // 전체 준비 대상 수 (에피소드 캐릭터 + 기본 캐릭터, 중복 제거)
  const totalTrainableCount = useMemo(() => {
    const episodeIds = trainableCharacters.map(c => c.voice_char_id || c.char_id).filter((id): id is string => id !== null)
    const defaultIds = [...defaultFemaleVoices, ...defaultMaleVoices].filter(id => !trainedCharIds.has(id))
    return new Set([...episodeIds, ...defaultIds]).size
  }, [trainableCharacters, defaultFemaleVoices, defaultMaleVoices, trainedCharIds])

  // 음성 없는 캐릭터 (수동 매핑 대상) - 에피소드 캐릭터 목록 기준
  // char_id가 null이어도 name이 있으면 매핑 가능
  const voicelessCharacters = useMemo(() => {
    return episodeCharacters.filter(c => !c.has_voice && c.name)
  }, [episodeCharacters])

  // 매핑 가능한 음성 목록 (학습 완료된 것만)
  const availableVoices = useMemo(() => {
    return voiceCharacters.filter(c => trainedCharIds.has(c.char_id))
  }, [voiceCharacters, trainedCharIds])

  // 현재 에피소드 캐시 상태
  const episodeCacheStatus = useMemo(() => {
    if (!selectedEpisodeId) return 'none'
    const safeId = selectedEpisodeId.replace(/\//g, '_').replace(/\\/g, '_')

    // renderProgress가 있으면 이를 기준으로 판정 (더 정확함)
    if (renderProgress && renderProgress.episode_id === safeId) {
      if (renderProgress.status === 'rendering') return 'rendering'
      // 전체 완료 판정: completed >= total
      if (renderProgress.completed >= renderProgress.total && renderProgress.total > 0) {
        return 'completed'
      }
      // 부분 완료 판정: 일부만 렌더링됨
      if (renderProgress.completed > 0) {
        return 'partial'
      }
    }

    // cachedEpisodes만 있는 경우 (이전에 완료된 캐시)
    if (cachedEpisodes.includes(safeId)) return 'completed'

    return 'none'
  }, [selectedEpisodeId, cachedEpisodes, renderProgress])

  // 사전 더빙 시작
  const handleStartRender = async (force: boolean = false) => {
    if (selectedEpisodeId) {
      await startRender(selectedEpisodeId, force)
    }
  }

  // 일괄 학습 시작 (voice_char_id 사용 + 기본 캐릭터 포함)
  const handleStartBatchTraining = async () => {
    // voice_char_id가 있으면 사용, 없으면 char_id 사용
    const charIdsFromEpisode = trainableCharacters
      .map(c => c.voice_char_id || c.char_id)
      .filter((id): id is string => id !== null)

    // 기본 캐릭터 중 미학습 캐릭터 추가
    const defaultCharIds = [...defaultFemaleVoices, ...defaultMaleVoices]
      .filter(id => !trainedCharIds.has(id))

    // 중복 제거 후 합치기
    const allCharIds = [...new Set([...defaultCharIds, ...charIdsFromEpisode])]

    if (allCharIds.length > 0) {
      await startBatchTraining(allCharIds)
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
        {/* 캐릭터 목록 (현재 에피소드 기준) */}
        <div className="p-4 border-b border-ark-border">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-ark-gray">등장 캐릭터</h4>
            <span className="text-xs text-ark-gray">
              음성 {characterStats.withVoice}/{characterStats.total}
            </span>
          </div>
          {isLoadingEpisodeCharacters ? (
            <div className="text-center text-ark-gray py-4 ark-pulse">로딩 중...</div>
          ) : episodeCharacters.length === 0 ? (
            <div className="text-center text-ark-gray py-4">캐릭터 없음</div>
          ) : (
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {episodeCharacters.map((char, idx) => (
                <div
                  key={`${char.char_id ?? 'narrator'}-${char.name}-${idx}`}
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
                    {(() => {
                      const voiceId = char.voice_char_id || char.char_id
                      if (voiceId && trainedCharIds.has(voiceId)) {
                        return <span className="text-xs text-green-400 font-medium">준비됨</span>
                      } else if (char.has_voice) {
                        return <span className="text-xs text-ark-yellow">준비 필요</span>
                      }
                      return null
                    })()}
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="mt-2 text-xs text-ark-gray/70">
            * 녹색 = 음성 데이터 보유
          </p>

          {/* 나레이션 대사 수 */}
          {episodeNarrationCount > 0 && (
            <div className="mt-3 p-2 bg-purple-500/10 rounded border border-purple-500/20">
              <div className="flex items-center justify-between">
                <span className="text-xs text-purple-400">나레이션</span>
                <span className="text-xs text-purple-300">{episodeNarrationCount}대사</span>
              </div>
              <p className="text-[10px] text-purple-400/70 mt-1">
                캐릭터 관리에서 설정한 나레이션 음성 사용
              </p>
            </div>
          )}
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
          ) : totalTrainableCount > 0 ? (
            // 학습 대기 상태
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="text-ark-gray">
                  {totalTrainableCount}개 캐릭터 준비 가능
                  {untrainedDefaultCount > 0 && (
                    <span className="text-ark-orange ml-1">(기본 {untrainedDefaultCount})</span>
                  )}
                </span>
              </div>
              <button
                onClick={handleStartBatchTraining}
                className="w-full ark-btn ark-btn-secondary text-sm ark-pulse-subtle"
              >
                음성 일괄 준비
              </button>
              <p className="text-xs text-ark-gray/50 text-center">
                * 참조 오디오 자동 선택 (Zero-shot)
              </p>
            </div>
          ) : characterStats.withVoice > 0 ? (
            // 모든 캐릭터 준비 완료
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-green-400">
                <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                </svg>
                <span className="text-sm">모든 캐릭터 준비 완료</span>
              </div>
              <p className="text-xs text-ark-gray/70">
                * 초기화는 캐릭터 관리에서 가능합니다
              </p>
            </div>
          ) : (
            // 학습 가능한 캐릭터 없음
            <p className="text-xs text-ark-gray/70">
              음성 데이터가 있는 캐릭터가 없습니다
            </p>
          )}
        </div>

        {/* 음성 매핑 (현재 에피소드 - 음성 없는 캐릭터) */}
        {availableVoices.length > 0 && (
          <div className="p-4 border-b border-ark-border">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-medium text-ark-gray">음성 매핑</h4>
              <span className="text-xs text-ark-gray">
                현재 에피소드 {voicelessCharacters.length}명
              </span>
            </div>
            {isLoadingEpisodeCharacters ? (
              <div className="text-center text-ark-gray py-4 ark-pulse">로딩 중...</div>
            ) : voicelessCharacters.length === 0 ? (
              <p className="text-xs text-ark-gray/70">
                * 음성 매핑이 필요한 캐릭터가 없습니다
              </p>
            ) : (
              <>
                <p className="text-xs text-ark-gray/70 mb-3">
                  * 자동: 이름 기반 분배 / 여성·남성: 성별 고정
                </p>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {voicelessCharacters.map((char, idx) => {
                    // char_id가 없으면 name을 키로 사용 (name: 접두사 추가)
                    const mappingKey = char.char_id || `name:${char.name}`
                    const manualMapping = speakerVoiceMap[mappingKey]
                    const autoVoice = getSpeakerVoice(mappingKey, char.name)
                    const autoVoiceName = autoVoice ? voiceCharacters.find(v => v.char_id === autoVoice)?.name : null

                    // 자동 여성/남성 선택 시 실제 선택될 캐릭터 계산
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
                      <div
                        key={`${mappingKey}-${idx}`}
                        className="flex items-center gap-2 p-2 rounded bg-ark-black/30"
                      >
                        <span className="text-sm flex-shrink-0 w-28 truncate text-ark-white" title={char.name}>
                          {char.name}
                          {!char.char_id && <span className="text-ark-gray/50 text-xs ml-1">(이름)</span>}
                        </span>
                        <span className="text-xs text-ark-gray flex-shrink-0">→</span>
                        <select
                          value={manualMapping ?? ''}
                          onChange={(e) => {
                            setSpeakerVoice(mappingKey, e.target.value || null)
                          }}
                          className="ark-input text-xs flex-1 min-w-0"
                        >
                          <option value="">
                            자동 {autoVoiceName ? `(${autoVoiceName})` : ''}
                          </option>
                          {defaultFemaleVoices.length > 0 && (
                            <option value={AUTO_VOICE_FEMALE}>
                              자동 (여성{autoFemaleName ? `-${autoFemaleName}` : ''})
                            </option>
                          )}
                          {defaultMaleVoices.length > 0 && (
                            <option value={AUTO_VOICE_MALE}>
                              자동 (남성{autoMaleName ? `-${autoMaleName}` : ''})
                            </option>
                          )}
                          <option disabled>──────────</option>
                          {availableVoices.map(v => (
                            <option key={v.char_id} value={v.char_id}>
                              {v.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    )
                  })}
                </div>
              </>
            )}
            {defaultFemaleVoices.length === 0 && defaultMaleVoices.length === 0 && (
              <p className="mt-2 text-xs text-ark-yellow">
                * 기본 음성이 설정되지 않았습니다. 캐릭터 관리에서 설정하세요.
              </p>
            )}
          </div>
        )}

        {/* 재생 설정 */}
        <div className="p-4 border-b border-ark-border">
          <h4 className="text-sm font-medium text-ark-gray mb-3">재생 설정</h4>
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

        {/* 사전 더빙 */}
        <div className="p-4 border-b border-ark-border">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-ark-gray">사전 더빙</h4>
            {episodeCacheStatus === 'completed' && (
              <span className="text-xs text-green-400">완료됨</span>
            )}
            {episodeCacheStatus === 'partial' && (
              <span className="text-xs text-ark-yellow">부분 완료</span>
            )}
          </div>

          {!selectedEpisodeId ? (
            <p className="text-xs text-ark-gray/70">
              에피소드를 먼저 선택하세요
            </p>
          ) : isRendering && renderProgress ? (
            // 렌더링 진행 중
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="text-ark-white">
                  {renderProgress.completed}/{renderProgress.total}
                </span>
                <span className="text-ark-orange">
                  {renderProgress.progress_percent.toFixed(0)}%
                </span>
              </div>
              <div className="w-full bg-ark-black rounded-full h-2 overflow-hidden">
                <div
                  className="bg-ark-orange h-2 rounded-full transition-all duration-300"
                  style={{ width: `${renderProgress.progress_percent}%` }}
                />
              </div>
              {renderProgress.current_text && (
                <p className="text-xs text-ark-gray truncate">
                  {renderProgress.current_text.substring(0, 40)}...
                </p>
              )}
              <button
                onClick={cancelRender}
                className="w-full ark-btn text-sm text-red-400 hover:text-red-300 border-red-400/30"
              >
                렌더링 취소
              </button>
            </div>
          ) : episodeCacheStatus === 'completed' ? (
            // 캐시 완료
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-green-400">
                <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                </svg>
                <span className="text-sm">사전 더빙 완료</span>
              </div>
              <p className="text-xs text-ark-gray/70">
                더빙 모드에서 캐시된 음성을 사용합니다
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => handleStartRender(true)}
                  disabled={!gptSovitsStatus?.api_running}
                  className={`flex-1 ark-btn ark-btn-secondary text-sm ${
                    !gptSovitsStatus?.api_running ? 'opacity-50 cursor-not-allowed' : ''
                  }`}
                >
                  다시 렌더링
                </button>
                <button
                  onClick={() => {
                    if (selectedEpisodeId && confirm('렌더 캐시를 삭제하시겠습니까?')) {
                      deleteRenderCache(selectedEpisodeId)
                    }
                  }}
                  className="ark-btn text-sm bg-red-900/50 hover:bg-red-800/50 text-red-300"
                  title="캐시 삭제"
                >
                  <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                    <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
                  </svg>
                </button>
              </div>
            </div>
          ) : episodeCacheStatus === 'partial' && renderProgress ? (
            // 부분 완료 (일부 대사만 렌더링됨)
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-ark-yellow">
                  <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                    <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
                  </svg>
                  <span className="text-sm">부분 완료</span>
                </div>
                <span className="text-xs text-ark-gray">
                  {renderProgress.completed}/{renderProgress.total}
                </span>
              </div>
              <div className="w-full bg-ark-black rounded-full h-2 overflow-hidden">
                <div
                  className="bg-ark-yellow h-2 rounded-full"
                  style={{ width: `${(renderProgress.completed / renderProgress.total) * 100}%` }}
                />
              </div>
              <p className="text-xs text-ark-gray/70">
                일부 대사만 캐시됨. 나머지는 실시간 합성됩니다.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => handleStartRender(false)}
                  disabled={!gptSovitsStatus?.api_running}
                  className={`flex-1 ark-btn ark-btn-secondary text-sm ${
                    !gptSovitsStatus?.api_running ? 'opacity-50 cursor-not-allowed' : ''
                  }`}
                >
                  이어서 렌더링
                </button>
                <button
                  onClick={() => {
                    if (selectedEpisodeId && confirm('렌더 캐시를 삭제하시겠습니까?')) {
                      deleteRenderCache(selectedEpisodeId)
                    }
                  }}
                  className="ark-btn text-sm bg-red-900/50 hover:bg-red-800/50 text-red-300"
                  title="캐시 삭제"
                >
                  <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                    <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
                  </svg>
                </button>
              </div>
            </div>
          ) : (
            // 사전 더빙 시작 가능
            <div className="space-y-2">
              <p className="text-xs text-ark-gray/70">
                에피소드 전체 음성을 미리 생성합니다
              </p>
              <button
                onClick={() => handleStartRender(false)}
                disabled={!gptSovitsStatus?.api_running}
                className={`w-full ark-btn ark-btn-secondary text-sm ${
                  !gptSovitsStatus?.api_running ? 'opacity-50 cursor-not-allowed' : ''
                }`}
              >
                사전 더빙 시작
              </button>
              {!gptSovitsStatus?.api_running && (
                <p className="text-xs text-ark-yellow">
                  * GPT-SoVITS를 먼저 시작하세요
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
