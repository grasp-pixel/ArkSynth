import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAppStore, isMysteryName } from '../stores/appStore'
import VoiceMappingModal from './VoiceMappingModal'

export default function VoiceSetupPanel() {
  const { t } = useTranslation()
  const [isVoiceMappingModalOpen, setIsVoiceMappingModalOpen] = useState(false)

  const {
    episodeCharacters,
    episodeNarrationCount,
    isLoadingEpisodeCharacters,
    loadVoiceCharacters,
    autoPlayOnMatch,
    toggleAutoPlay,
    cancelPrepare,
    clearEpisode,
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
    partialEpisodes,
    startRender,
    cancelRender,
    deleteRenderCache,
    loadRenderStatus,
    // 음성 매핑
    speakerVoiceMap,
    defaultFemaleVoices,
    defaultMaleVoices,
    getSpeakerVoice,
    // 모델 타입 조회
    trainedModels,
    canFinetune,
    getModelType,
    // 나레이션
    narratorCharId,
    // 알 수 없는 화자
    unknownSpeakerCharId,
    // 캐릭터 이름 조회용
    voiceCharacters,
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

  // 알 수 없는 화자("???") 대사 수
  const unknownSpeakerCount = useMemo(() => {
    return episodeCharacters
      .filter(c => !c.char_id && c.name && isMysteryName(c.name))
      .reduce((sum, c) => sum + c.dialogue_count, 0)
  }, [episodeCharacters])

  // 음성 없는 캐릭터 (수동 매핑 대상) - 에피소드 캐릭터 목록 기준
  // char_id가 null이어도 name이 있으면 매핑 가능
  const voicelessCharacters = useMemo(() => {
    return episodeCharacters.filter(c => !c.has_voice && c.name)
  }, [episodeCharacters])

  // 음성 없는 캐릭터에 실제로 매핑된 음성 ID들
  const mappedVoiceIds = useMemo(() => {
    return voicelessCharacters
      .map(c => {
        const key = c.char_id || `name:${c.name}`
        return getSpeakerVoice(key, c.name)
      })
      .filter((id): id is string => id !== null)
  }, [voicelessCharacters, getSpeakerVoice, speakerVoiceMap, defaultFemaleVoices, defaultMaleVoices])

  // 전체 준비 대상 수 (에피소드 캐릭터 + 매핑된 음성 + 나레이션)
  const totalTrainableCount = useMemo(() => {
    const episodeIds = trainableCharacters.map(c => c.voice_char_id || c.char_id).filter((id): id is string => id !== null)
    // 매핑된 음성 중 미준비 캐릭터만
    const mappedIds = mappedVoiceIds.filter(id => !trainedCharIds.has(id))
    // 나레이션이 있고, 나레이터 캐릭터가 설정되어 있고, 미준비인 경우 포함
    const narratorIds: string[] = []
    if (episodeNarrationCount > 0 && narratorCharId && !trainedCharIds.has(narratorCharId)) {
      narratorIds.push(narratorCharId)
    }
    // 중복 제거 후 카운트
    return new Set([...episodeIds, ...mappedIds, ...narratorIds]).size
  }, [trainableCharacters, trainedCharIds, mappedVoiceIds, episodeNarrationCount, narratorCharId])

  // Fine-tune 가능한 캐릭터 수 (준비됨 + 전처리 완료 + finetuned 아님)
  // episodeCharacters + 매핑된 음성 + 나레이션에서 계산
  const totalFinetuneableCount = useMemo(() => {
    const episodeIds = episodeCharacters
      .filter(c => c.has_voice)
      .map(c => c.voice_char_id || c.char_id)
      .filter((id): id is string => id !== null)
    // 나레이션 캐릭터도 포함
    const narratorIds: string[] = []
    if (episodeNarrationCount > 0 && narratorCharId) {
      narratorIds.push(narratorCharId)
    }
    // 에피소드 캐릭터 + 매핑된 음성 + 나레이션 합쳐서 canFinetune 체크
    const allIds = [...new Set([...episodeIds, ...mappedVoiceIds, ...narratorIds])]
    return allIds.filter(id => canFinetune(id)).length
  }, [episodeCharacters, canFinetune, trainedModels, mappedVoiceIds, episodeNarrationCount, narratorCharId])

  // 매핑 완료된 캐릭터 수
  const mappedCount = useMemo(() => {
    return voicelessCharacters.filter(c => {
      const key = c.char_id || `name:${c.name}`
      return speakerVoiceMap[key] !== undefined
    }).length
  }, [voicelessCharacters, speakerVoiceMap])

  // 현재 에피소드 캐시 상태
  const episodeCacheStatus = useMemo(() => {
    if (!selectedEpisodeId) return 'none'
    const safeId = selectedEpisodeId.replace(/\//g, '_').replace(/\\/g, '_')

    // renderProgress가 있으면 이를 기준으로 판정 (더 정확함)
    // episode_id도 safe id로 변환하여 비교
    const progressSafeId = renderProgress?.episode_id?.replace(/\//g, '_').replace(/\\/g, '_')
    if (renderProgress && progressSafeId === safeId) {
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

    // 부분 완료 에피소드 목록 확인
    if (partialEpisodes.includes(safeId)) {
      return 'partial'
    }

    // 완료된 에피소드 목록 확인
    if (cachedEpisodes.includes(safeId)) {
      return 'completed'
    }

    return 'none'
  }, [selectedEpisodeId, cachedEpisodes, partialEpisodes, renderProgress])

  // 나레이터/??? 미설정 경고 확인
  const [showNarratorWarning, setShowNarratorWarning] = useState(false)
  const [pendingRenderForce, setPendingRenderForce] = useState(false)

  // 사전 더빙 시작
  const handleStartRender = async (force: boolean = false) => {
    if (!selectedEpisodeId) return

    // 나레이터/??? 미설정 시 경고
    const hasNarration = episodeNarrationCount > 0
    const hasUnknownSpeaker = unknownSpeakerCount > 0
    const missingNarrator = hasNarration && !narratorCharId
    const missingUnknown = hasUnknownSpeaker && !unknownSpeakerCharId

    if (missingNarrator || missingUnknown) {
      setPendingRenderForce(force)
      setShowNarratorWarning(true)
      return
    }

    await startRender(selectedEpisodeId, force)
  }

  const confirmRenderWithWarning = async () => {
    setShowNarratorWarning(false)
    if (selectedEpisodeId) {
      await startRender(selectedEpisodeId, pendingRenderForce)
    }
  }

  // 일괄 준비 시작 (에피소드 캐릭터 + 매핑된 음성 + 나레이션)
  const handleStartBatchTraining = async () => {
    // 1. 에피소드 캐릭터 중 음성이 있고 미준비인 것
    const charIdsFromEpisode = trainableCharacters
      .map(c => c.voice_char_id || c.char_id)
      .filter((id): id is string => id !== null)

    // 2. 음성 없는 캐릭터에 매핑된 음성 중 미준비인 것
    const mappedIds = mappedVoiceIds.filter(id => !trainedCharIds.has(id))

    // 3. 나레이션이 있고, 나레이터 캐릭터가 설정되어 있고, 미준비인 경우 포함
    const narratorIds: string[] = []
    if (episodeNarrationCount > 0 && narratorCharId && !trainedCharIds.has(narratorCharId)) {
      narratorIds.push(narratorCharId)
    }

    // 중복 제거 후 합치기
    const uniqueCharIds = [...new Set([...charIdsFromEpisode, ...mappedIds, ...narratorIds])]

    if (uniqueCharIds.length > 0) {
      await startBatchTraining(uniqueCharIds, 'prepare')
    }
  }

  // 일괄 학습 시작 (Fine-tuning, 준비됨 + 전처리 완료된 캐릭터)
  const handleStartBatchFinetuning = async () => {
    // 1. 에피소드 캐릭터 중 음성이 있는 것
    const charIdsFromEpisode = episodeCharacters
      .filter(c => c.has_voice)
      .map(c => c.voice_char_id || c.char_id)
      .filter((id): id is string => id !== null)

    // 2. 나레이션 캐릭터도 포함
    const narratorIds: string[] = []
    if (episodeNarrationCount > 0 && narratorCharId) {
      narratorIds.push(narratorCharId)
    }

    // 3. 에피소드 캐릭터 + 매핑된 음성 + 나레이션 합쳐서 canFinetune 체크
    const allIds = [...new Set([...charIdsFromEpisode, ...mappedVoiceIds, ...narratorIds])]
    const finetuneableIds = allIds.filter(id => canFinetune(id))

    if (finetuneableIds.length > 0) {
      await startBatchTraining(finetuneableIds, 'finetune')
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
          {t('dubbing.setup.title')}
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={clearEpisode}
            className="text-ark-cyan hover:text-ark-white text-sm"
          >
            {t('dubbing.button.backToGroup')}
          </button>
          <button
            onClick={cancelPrepare}
            className="text-ark-gray hover:text-ark-white text-sm"
          >
            {t('common.cancel')}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* 캐릭터 목록 (현재 에피소드 기준) */}
        <div className="p-4 border-b border-ark-border">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-ark-gray">{t('dubbing.section.characters')}</h4>
            <div className="flex items-center gap-3">
              <span className="text-xs text-ark-gray">
                {t('dubbing.characters.hasVoice', { withVoice: characterStats.withVoice, total: characterStats.total })}
              </span>
              <span className={`text-xs ${characterStats.trained === characterStats.withVoice ? 'text-green-400' : 'text-ark-yellow'}`}>
                {t('dubbing.characters.prepared', { trained: characterStats.trained, withVoice: characterStats.withVoice })}
              </span>
            </div>
          </div>
          {isLoadingEpisodeCharacters ? (
            <div className="text-center text-ark-gray py-4 ark-pulse">{t('common.loading')}</div>
          ) : episodeCharacters.length === 0 ? (
            <div className="text-center text-ark-gray py-4">{t('common.noCharacters')}</div>
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
                    }`} title={char.has_voice ? t('dialogue.status.hasVoice') : t('dialogue.status.noVoice')} />
                    <span className="text-ark-white truncate">{char.name}</span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-xs text-ark-gray">
                      {t('character.dialogueCount', { count: char.dialogue_count })}
                    </span>
                    {(() => {
                      const voiceId = char.voice_char_id || char.char_id
                      if (voiceId && trainedCharIds.has(voiceId)) {
                        const modelType = getModelType(voiceId)
                        if (modelType === 'finetuned') {
                          return <span className="text-xs text-purple-400 font-medium">{t('character.status.trained')}</span>
                        }
                        return <span className="text-xs text-green-400 font-medium">{t('character.status.prepared')}</span>
                      } else if (char.has_voice) {
                        return <span className="text-xs text-ark-yellow">{t('character.status.needsPreparation')}</span>
                      }
                      return null
                    })()}
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="mt-2 text-xs text-ark-gray/70">
            {t('dubbing.note.greenMeansVoice')}
          </p>

          {/* 나레이션 대사 수 */}
          {episodeNarrationCount > 0 && (
            <div className="mt-3 p-2 bg-purple-500/10 rounded border border-purple-500/20">
              <div className="flex items-center justify-between">
                <span className="text-xs text-purple-400">{t('character.narration.labelShort')}</span>
                <span className="text-xs text-purple-300">{t('character.dialogueCount', { count: episodeNarrationCount })}</span>
              </div>
              <p className="text-[10px] text-purple-400/70 mt-1">
                {narratorCharId
                  ? t('dubbing.narrator.voice', { name: voiceCharacters.find(c => c.char_id === narratorCharId)?.name ?? narratorCharId })
                  : t('dubbing.narrator.setupGuide')}
              </p>
            </div>
          )}

          {/* 알 수 없는 화자(???) 대사 수 */}
          {unknownSpeakerCount > 0 && (
            <div className="mt-3 p-2 bg-amber-500/10 rounded border border-amber-500/20">
              <div className="flex items-center justify-between">
                <span className="text-xs text-amber-400">{t('character.unknownSpeaker.labelFull')}</span>
                <span className="text-xs text-amber-300">{t('character.dialogueCount', { count: unknownSpeakerCount })}</span>
              </div>
              <p className="text-[10px] text-amber-400/70 mt-1">
                {unknownSpeakerCharId
                  ? t('dubbing.unknownSpeaker.voice', { name: voiceCharacters.find(c => c.char_id === unknownSpeakerCharId)?.name ?? unknownSpeakerCharId })
                  : t('dubbing.unknownSpeaker.setupGuide')}
              </p>
            </div>
          )}
        </div>

        {/* GPT-SoVITS 연결 상태 */}
        <div className="p-4 border-b border-ark-border">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium text-ark-gray">{t('dubbing.section.gptSovits')}</h4>
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
                  ? t('app.gpt.synthesizing')
                  : gptSovitsStatus?.api_running
                    ? t('common.connected')
                    : t('common.waiting')}
              </span>
            </div>
          </div>
          {!gptSovitsStatus?.api_running && (
            <p className="mt-2 text-xs text-ark-gray/70">
              {t('dubbing.note.startGptSovits')}
            </p>
          )}
        </div>

        {/* 음성 준비 섹션 */}
        <div className="p-4 border-b border-ark-border">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-ark-gray">{t('dubbing.section.voicePreparation')}</h4>
            <span className="text-xs text-ark-gray">
              {t('dubbing.status.prepared', { trained: characterStats.trained, withVoice: characterStats.withVoice })}
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
                  {currentTrainingJob.status === 'preprocessing' && t('dubbing.status.preprocessing')}
                  {currentTrainingJob.status === 'training' && t('dubbing.status.preparing')}
                  {currentTrainingJob.status === 'pending' && t('common.pending')}
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
                    {currentTrainingJob.message || t('dubbing.status.preparing')}
                  </span>
                </div>
              </div>

              {/* 대기열 */}
              {trainingQueue.length > 0 && (
                <div className="text-xs text-ark-gray">
                  <span>{t('dubbing.queue.label')}</span>
                  <span className="text-ark-white">{t('dubbing.queue.count', { count: trainingQueue.length })}</span>
                  <span className="ml-2 text-ark-gray/70">
                    ({trainingQueue.slice(0, 3).map(j => j.char_name).join(', ')}
                    {trainingQueue.length > 3 && ` ${t('dubbing.queue.more', { count: trainingQueue.length - 3 })}`})
                  </span>
                </div>
              )}

              <button
                onClick={handleCancelTraining}
                className="w-full ark-btn text-sm text-red-400 hover:text-red-300 border-red-400/30"
              >
                {t('dubbing.button.cancelPrepare')}
              </button>
            </div>
          ) : totalTrainableCount > 0 ? (
            // 학습 대기 상태
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="text-ark-gray">
                  {t('dubbing.status.trainableCount', { count: totalTrainableCount })}
                </span>
              </div>
              <button
                onClick={handleStartBatchTraining}
                className="w-full ark-btn ark-btn-secondary text-sm ark-pulse-subtle"
              >
                {t('dubbing.button.batchPrepare')}
              </button>
              <button
                onClick={handleStartBatchFinetuning}
                className="w-full ark-btn text-sm text-purple-400 hover:text-purple-300 border-purple-400/30 mt-2"
                disabled={!gptSovitsStatus?.api_running}
                title={!gptSovitsStatus?.api_running ? t('character.zeroShotMode.needsConnection') : t('dubbing.button.batchTrain')}
              >
                {t('dubbing.button.batchTrain')}
              </button>
              <p className="text-xs text-ark-gray/50 text-center">
                {t('dubbing.note.prepareVsTrain')}
              </p>
              <p className="text-xs text-green-400/70 text-center mt-1">
                {t('dubbing.note.prepareSufficient')}
              </p>
            </div>
          ) : characterStats.withVoice > 0 ? (
            // 모든 캐릭터 준비 완료
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-green-400">
                <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                </svg>
                <span className="text-sm">{t('dubbing.status.allPrepared')}</span>
              </div>
              {/* Fine-tune 가능한 캐릭터가 있으면 학습 버튼 표시 */}
              {totalFinetuneableCount > 0 && (
                <>
                  <div className="text-xs text-ark-gray">
                    {t('dubbing.status.finetuneableCount', { count: totalFinetuneableCount })}
                  </div>
                  <button
                    onClick={handleStartBatchFinetuning}
                    className="w-full ark-btn text-sm text-purple-400 hover:text-purple-300 border-purple-400/30"
                    disabled={!gptSovitsStatus?.api_running}
                    title={!gptSovitsStatus?.api_running ? t('character.zeroShotMode.needsConnection') : t('dubbing.button.batchTrain')}
                  >
                    {t('dubbing.button.batchTrain')}
                  </button>
                </>
              )}
              <p className="text-xs text-ark-gray/70">
                {t('dubbing.note.resetInCharacterManagement')}
              </p>
            </div>
          ) : (
            // 학습 가능한 캐릭터 없음
            <p className="text-xs text-ark-gray/70">
              {t('dubbing.status.noCharactersWithVoice')}
            </p>
          )}
        </div>

        {/* 음성 매핑 (간소화) */}
        <div className="p-4 border-b border-ark-border">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-ark-gray">{t('dubbing.section.voiceMapping')}</h4>
            <span className="text-xs text-ark-gray">
              {voicelessCharacters.length > 0
                ? t('dubbing.mapping.count', { mapped: mappedCount, total: voicelessCharacters.length })
                : t('dubbing.status.allHaveVoice')}
            </span>
          </div>
          {isLoadingEpisodeCharacters ? (
            <div className="text-center text-ark-gray py-4 ark-pulse">{t('common.loading')}</div>
          ) : voicelessCharacters.length === 0 ? (
            <div className="flex items-center gap-2 text-green-400">
              <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
              </svg>
              <span className="text-sm">{t('dubbing.status.allHaveVoiceFull')}</span>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-xs text-ark-gray/70">
                {t('dubbing.mapping.description')}
              </p>
              <button
                onClick={() => setIsVoiceMappingModalOpen(true)}
                className="w-full ark-btn ark-btn-secondary text-sm flex items-center justify-center gap-2"
              >
                <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                  <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
                </svg>
                {t('dubbing.button.voiceMappingSetup')}
              </button>
              {defaultFemaleVoices.length === 0 && defaultMaleVoices.length === 0 && (
                <p className="text-xs text-ark-yellow">
                  {t('dubbing.warning.noDefaultVoices')}
                </p>
              )}
            </div>
          )}
        </div>

        {/* 음성 매핑 모달 */}
        <VoiceMappingModal
          isOpen={isVoiceMappingModalOpen}
          onClose={() => setIsVoiceMappingModalOpen(false)}
        />

        {/* 재생 설정 */}
        <div className="p-4 border-b border-ark-border">
          <h4 className="text-sm font-medium text-ark-gray mb-3">{t('dubbing.section.playbackSettings')}</h4>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={autoPlayOnMatch}
              onChange={toggleAutoPlay}
              className="w-4 h-4 rounded border-ark-border bg-ark-black text-ark-orange focus:ring-ark-orange"
            />
            <span className="text-ark-white text-sm">{t('dubbing.autoplay.onMatch')}</span>
          </label>
        </div>

        {/* 사전 더빙 */}
        <div className="p-4 border-b border-ark-border">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-ark-gray">{t('dubbing.section.preRendering')}</h4>
            {episodeCacheStatus === 'completed' && (
              <span className="text-xs text-green-400">{t('common.completed')}</span>
            )}
            {episodeCacheStatus === 'partial' && (
              <span className="text-xs text-ark-yellow">{t('common.partiallyCompleted')}</span>
            )}
          </div>

          {!selectedEpisodeId ? (
            <p className="text-xs text-ark-gray/70">
              {t('dubbing.message.selectEpisodeFirst')}
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
              <p className="text-xs text-ark-cyan/70 mt-1">
                {t('dubbing.note.realtimeDuringPreRendering')}
              </p>
              <button
                onClick={cancelRender}
                className="w-full ark-btn text-sm text-red-400 hover:text-red-300 border-red-400/30 mt-2"
              >
                {t('dubbing.button.cancelRendering')}
              </button>
            </div>
          ) : episodeCacheStatus === 'completed' ? (
            // 캐시 완료
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-green-400">
                <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                </svg>
                <span className="text-sm">{t('dubbing.status.preRenderingComplete')}</span>
              </div>
              <p className="text-xs text-ark-gray/70">
                {t('dubbing.info.usesCachedVoice')}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => handleStartRender(true)}
                  disabled={!gptSovitsStatus?.api_running}
                  className={`flex-1 ark-btn ark-btn-secondary text-sm ${
                    !gptSovitsStatus?.api_running ? 'opacity-50 cursor-not-allowed' : ''
                  }`}
                >
                  {t('dubbing.button.reRender')}
                </button>
                <button
                  onClick={() => {
                    if (selectedEpisodeId && confirm(t('dubbing.confirm.deleteRenderCache'))) {
                      deleteRenderCache(selectedEpisodeId)
                    }
                  }}
                  className="ark-btn text-sm bg-red-900/50 hover:bg-red-800/50 text-red-300"
                  title={t('dubbing.button.deleteCache')}
                >
                  <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                    <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
                  </svg>
                </button>
              </div>
            </div>
          ) : episodeCacheStatus === 'partial' ? (
            // 부분 완료 (일부 대사만 렌더링됨)
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-ark-yellow">
                  <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                    <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
                  </svg>
                  <span className="text-sm">{t('common.partiallyCompleted')}</span>
                </div>
                {renderProgress && (
                  <span className="text-xs text-ark-gray">
                    {renderProgress.completed}/{renderProgress.total}
                  </span>
                )}
              </div>
              {renderProgress && renderProgress.total > 0 && (
                <div className="w-full bg-ark-black rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-ark-yellow h-2 rounded-full"
                    style={{ width: `${(renderProgress.completed / renderProgress.total) * 100}%` }}
                  />
                </div>
              )}
              <p className="text-xs text-ark-gray/70">
                {t('dubbing.info.partialCache')}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => handleStartRender(false)}
                  disabled={!gptSovitsStatus?.api_running}
                  className={`flex-1 ark-btn ark-btn-secondary text-sm ${
                    !gptSovitsStatus?.api_running ? 'opacity-50 cursor-not-allowed' : ''
                  }`}
                >
                  {t('dubbing.button.continueRendering')}
                </button>
                <button
                  onClick={() => {
                    if (selectedEpisodeId && confirm(t('dubbing.confirm.deleteRenderCache'))) {
                      deleteRenderCache(selectedEpisodeId)
                    }
                  }}
                  className="ark-btn text-sm bg-red-900/50 hover:bg-red-800/50 text-red-300"
                  title={t('dubbing.button.deleteCache')}
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
                {t('dubbing.preRendering.description')}
              </p>
              <button
                onClick={() => handleStartRender(false)}
                disabled={!gptSovitsStatus?.api_running}
                className={`w-full ark-btn ark-btn-secondary text-sm ${
                  !gptSovitsStatus?.api_running ? 'opacity-50 cursor-not-allowed' : ''
                }`}
              >
                {t('dubbing.button.startPreRendering')}
              </button>
              {!gptSovitsStatus?.api_running && (
                <p className="text-xs text-ark-yellow">
                  {t('dubbing.note.startGptSovitsFirst')}
                </p>
              )}
            </div>
          )}
        </div>

      </div>

      {/* 나레이터/??? 미설정 경고 다이얼로그 */}
      {showNarratorWarning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
          <div className="bg-ark-dark border border-ark-border rounded-lg p-6 max-w-md mx-4 shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center flex-shrink-0">
                <svg viewBox="0 0 24 24" className="w-5 h-5 text-amber-400" fill="currentColor">
                  <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
                </svg>
              </div>
              <h3 className="text-base font-bold text-ark-white">{t('dubbing.dialog.confirmSpeaker')}</h3>
            </div>
            <div className="space-y-2 mb-6">
              {episodeNarrationCount > 0 && !narratorCharId && (
                <p className="text-sm text-amber-400">
                  {t('dubbing.warning.narratorNotSet', { count: episodeNarrationCount })}
                </p>
              )}
              {unknownSpeakerCount > 0 && !unknownSpeakerCharId && (
                <p className="text-sm text-amber-400">
                  {t('dubbing.warning.unknownSpeakerNotSet', { count: unknownSpeakerCount })}
                </p>
              )}
              <p className="text-xs text-ark-gray">
                {t('dubbing.info.skipDialoguesInfo')}
              </p>
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowNarratorWarning(false)}
                className="ark-btn text-sm px-4 py-2"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={confirmRenderWithWarning}
                className="ark-btn ark-btn-primary text-sm px-4 py-2"
              >
                {t('dubbing.button.proceed')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
