import { useEffect, useMemo, useState } from 'react'
import { useAppStore } from '../stores/appStore'
import VoiceMappingModal from './VoiceMappingModal'

interface BatchTasks {
  prepare: boolean
  finetune: boolean
  render: boolean
}

interface FinetuneTarget {
  appearance: boolean  // 등장 캐릭터 (음성 보유)
  mapped: boolean      // 매핑된 캐릭터
}

export default function GroupSetupPanel() {
  const [isVoiceMappingModalOpen, setIsVoiceMappingModalOpen] = useState(false)
  const [batchTasks, setBatchTasks] = useState<BatchTasks>({
    prepare: true,
    finetune: false,
    render: true,
  })
  const [finetuneTarget, setFinetuneTarget] = useState<FinetuneTarget>({
    appearance: true,
    mapped: false,
  })
  const [isExecuting, setIsExecuting] = useState(false)

  const {
    // 그룹 정보
    selectedGroupId,
    storyGroups,
    groupEpisodes,
    groupCharacters,
    isLoadingCharacters,
    loadGroupCharacters,
    cancelPrepare,
    // 학습 관련
    trainedCharIds,
    isTrainingActive,
    currentTrainingJob,
    trainingQueue,
    loadTrainingStatus,
    loadTrainedModels,
    startBatchTraining,
    cancelTraining,
    unsubscribeFromTrainingProgress,
    // GPT-SoVITS
    gptSovitsStatus,
    // 그룹 렌더링
    isGroupRendering,
    groupRenderProgress,
    groupRenderError,
    startGroupRender,
    cancelGroupRender,
    // 캐시 상태
    cachedEpisodes,
    partialEpisodes,
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
  } = useAppStore()

  // 초기 로드
  useEffect(() => {
    loadTrainingStatus()
    loadTrainedModels()
    loadRenderStatus()

    return () => {
      unsubscribeFromTrainingProgress()
    }
  }, [])

  // 그룹 변경 시 캐릭터 로드
  useEffect(() => {
    if (selectedGroupId) {
      loadGroupCharacters(selectedGroupId)
    }
  }, [selectedGroupId, loadGroupCharacters])

  // 그룹 정보 찾기
  const groupInfo = useMemo(() => {
    return storyGroups.find(g => g.id === selectedGroupId)
  }, [storyGroups, selectedGroupId])

  // 캐릭터 통계 (그룹 기준)
  const characterStats = useMemo(() => {
    const withVoice = groupCharacters.filter(c => c.has_voice).length
    const trained = groupCharacters.filter(c => {
      const voiceId = c.voice_char_id || c.char_id
      return voiceId && trainedCharIds.has(voiceId)
    }).length
    const total = groupCharacters.length
    return { withVoice, trained, total }
  }, [groupCharacters, trainedCharIds])

  // 음성 없는 캐릭터 (매핑 대상)
  const voicelessCharacters = useMemo(() => {
    return groupCharacters.filter(c => !c.has_voice && c.name)
  }, [groupCharacters])

  // 매핑된 음성 ID들
  const mappedVoiceIds = useMemo(() => {
    return voicelessCharacters
      .map(c => {
        const key = c.char_id || `name:${c.name}`
        return getSpeakerVoice(key, c.name)
      })
      .filter((id): id is string => id !== null)
  }, [voicelessCharacters, getSpeakerVoice, speakerVoiceMap, defaultFemaleVoices, defaultMaleVoices])

  // 준비 가능한 캐릭터 수 (음성 있고 미준비)
  const preparableCount = useMemo(() => {
    const charIds = groupCharacters
      .filter(c => c.has_voice)
      .map(c => c.voice_char_id || c.char_id)
      .filter((id): id is string => id !== null && !trainedCharIds.has(id))
    return charIds.length
  }, [groupCharacters, trainedCharIds])

  // 준비 완료된 캐릭터 수
  const preparedCount = useMemo(() => {
    return groupCharacters.filter(c => {
      const voiceId = c.voice_char_id || c.char_id
      return voiceId && trainedCharIds.has(voiceId)
    }).length
  }, [groupCharacters, trainedCharIds])

  // Fine-tuned 완료된 캐릭터 수
  const finetunedCount = useMemo(() => {
    return groupCharacters.filter(c => {
      const voiceId = c.voice_char_id || c.char_id
      return voiceId && getModelType(voiceId) === 'finetuned'
    }).length
  }, [groupCharacters, getModelType, trainedModels])

  // 에피소드 캐시 상태
  const episodeCacheStats = useMemo(() => {
    const total = groupEpisodes.length
    const completed = groupEpisodes.filter(ep => {
      const safeId = ep.id.replace(/\//g, '_').replace(/\\/g, '_')
      return cachedEpisodes.includes(safeId)
    }).length
    const partial = groupEpisodes.filter(ep => {
      const safeId = ep.id.replace(/\//g, '_').replace(/\\/g, '_')
      return partialEpisodes.includes(safeId)
    }).length
    return { total, completed, partial }
  }, [groupEpisodes, cachedEpisodes, partialEpisodes])

  // 매핑 완료된 캐릭터 수
  const mappedCount = useMemo(() => {
    return voicelessCharacters.filter(c => {
      const key = c.char_id || `name:${c.name}`
      return speakerVoiceMap[key] !== undefined
    }).length
  }, [voicelessCharacters, speakerVoiceMap])

  // 일괄 실행
  const handleBatchExecute = async () => {
    if (!selectedGroupId) return
    setIsExecuting(true)

    try {
      // 1. 음성 준비 (prepare)
      if (batchTasks.prepare && preparableCount > 0) {
        const charIds = groupCharacters
          .filter(c => c.has_voice)
          .map(c => c.voice_char_id || c.char_id)
          .filter((id): id is string => id !== null && !trainedCharIds.has(id))

        if (charIds.length > 0) {
          await startBatchTraining(charIds, 'prepare')
          // 준비 완료 대기 (학습이 완료될 때까지)
          // 실제로는 SSE로 진행 상황을 추적하고, 완료 후 다음 단계 진행
          // 여기서는 일단 시작만 하고 다음 단계는 수동으로
        }
      }

      // 2. 모델 학습 (finetune) - 선택 사항
      if (batchTasks.finetune) {
        const targetCharIds: string[] = []

        // 등장 캐릭터 (음성 보유)
        if (finetuneTarget.appearance) {
          const ids = groupCharacters
            .filter(c => c.has_voice)
            .map(c => c.voice_char_id || c.char_id)
            .filter((id): id is string => id !== null && canFinetune(id))
          targetCharIds.push(...ids)
        }

        // 매핑된 캐릭터
        if (finetuneTarget.mapped) {
          const ids = mappedVoiceIds.filter(id => canFinetune(id))
          targetCharIds.push(...ids)
        }

        const uniqueIds = [...new Set(targetCharIds)]
        if (uniqueIds.length > 0) {
          await startBatchTraining(uniqueIds, 'finetune')
        }
      }

      // 3. 사전 더빙 (render)
      // 학습이 진행 중이면 완료 후 시작해야 함
      if (batchTasks.render && !isTrainingActive) {
        await startGroupRender(selectedGroupId)
      }
    } catch (error) {
      console.error('일괄 실행 오류:', error)
    } finally {
      setIsExecuting(false)
    }
  }

  // 학습 취소
  const handleCancelTraining = async () => {
    if (currentTrainingJob) {
      await cancelTraining(currentTrainingJob.job_id)
    }
  }

  // 실행 가능 여부
  const canExecute = useMemo(() => {
    if (!gptSovitsStatus?.api_running) return false
    if (isTrainingActive || isGroupRendering) return false
    // 선택된 작업이 하나라도 있어야 함
    return batchTasks.prepare || batchTasks.finetune || batchTasks.render
  }, [gptSovitsStatus, isTrainingActive, isGroupRendering, batchTasks])

  return (
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div className="p-4 border-b border-ark-border bg-ark-panel/50 flex items-center justify-between">
        <h3 className="font-bold text-ark-white flex items-center gap-2">
          <svg viewBox="0 0 24 24" className="w-5 h-5 text-ark-cyan" fill="currentColor">
            <path d="M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-1 9h-4v4h-2v-4H9V9h4V5h2v4h4v2z"/>
          </svg>
          그룹 설정
        </h3>
        <button
          onClick={cancelPrepare}
          className="text-ark-gray hover:text-ark-white text-sm"
        >
          닫기
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* 그룹 정보 */}
        <div className="p-4 border-b border-ark-border bg-ark-panel/30">
          <div className="flex items-center justify-between">
            <span className="text-ark-white font-medium">{groupInfo?.name || '그룹'}</span>
            <span className="text-xs text-ark-gray">{groupEpisodes.length}개 에피소드</span>
          </div>
        </div>

        {/* 그룹 캐릭터 목록 */}
        <div className="p-4 border-b border-ark-border">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-ark-gray">그룹 캐릭터</h4>
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
              {groupCharacters.slice(0, 20).map((char, idx) => (
                <div
                  key={`${char.char_id ?? 'unknown'}-${char.name}-${idx}`}
                  className="flex items-center justify-between p-2 bg-ark-black/30 rounded text-sm"
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      char.has_voice ? 'bg-green-500' : 'bg-ark-gray/50'
                    }`} />
                    <span className="text-ark-white truncate">{char.name}</span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-xs text-ark-gray">
                      {char.dialogue_count}대사
                    </span>
                    {(() => {
                      const voiceId = char.voice_char_id || char.char_id
                      if (voiceId && trainedCharIds.has(voiceId)) {
                        const modelType = getModelType(voiceId)
                        if (modelType === 'finetuned') {
                          return <span className="text-xs text-purple-400 font-medium">학습됨</span>
                        }
                        return <span className="text-xs text-green-400 font-medium">준비됨</span>
                      }
                      return null
                    })()}
                  </div>
                </div>
              ))}
              {groupCharacters.length > 20 && (
                <p className="text-xs text-ark-gray/70 text-center pt-2">
                  외 {groupCharacters.length - 20}명
                </p>
              )}
            </div>
          )}
        </div>

        {/* 음성 매핑 */}
        <div className="p-4 border-b border-ark-border">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-ark-gray">음성 매핑</h4>
            <span className="text-xs text-ark-gray">
              {voicelessCharacters.length > 0
                ? `${mappedCount}/${voicelessCharacters.length}명 매핑`
                : '모두 보유'}
            </span>
          </div>
          {voicelessCharacters.length === 0 ? (
            <div className="flex items-center gap-2 text-green-400">
              <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
              </svg>
              <span className="text-sm">모든 캐릭터가 음성을 보유</span>
            </div>
          ) : (
            <div className="space-y-2">
              <button
                onClick={() => setIsVoiceMappingModalOpen(true)}
                className="w-full ark-btn ark-btn-secondary text-sm flex items-center justify-center gap-2"
              >
                <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                  <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
                </svg>
                음성 매핑 설정
              </button>
            </div>
          )}
        </div>

        {/* 일괄 작업 */}
        <div className="p-4 border-b border-ark-border">
          <h4 className="text-sm font-medium text-ark-gray mb-4">일괄 작업</h4>

          {/* 진행 중 상태 표시 */}
          {(isTrainingActive || isGroupRendering) ? (
            <div className="space-y-4">
              {/* 학습 진행 중 */}
              {isTrainingActive && currentTrainingJob && (
                <div className="space-y-3 p-3 bg-ark-black/50 rounded border border-ark-border">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-ark-orange ark-pulse" />
                      <span className="text-sm text-ark-white font-medium">
                        {currentTrainingJob.char_name}
                      </span>
                    </div>
                    <span className="text-xs px-2 py-0.5 rounded bg-ark-orange/20 text-ark-orange">
                      {currentTrainingJob.mode === 'prepare' ? '준비 중' : '학습 중'}
                    </span>
                  </div>
                  <div className="w-full bg-ark-black rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-ark-orange h-2 rounded-full transition-all duration-300"
                      style={{ width: `${(currentTrainingJob.progress * 100)}%` }}
                    />
                  </div>
                  {trainingQueue.length > 0 && (
                    <p className="text-xs text-ark-gray">
                      대기열: {trainingQueue.length}개
                    </p>
                  )}
                  <button
                    onClick={handleCancelTraining}
                    className="w-full ark-btn text-sm text-red-400 hover:text-red-300 border-red-400/30"
                  >
                    취소
                  </button>
                </div>
              )}

              {/* 그룹 렌더링 진행 중 */}
              {isGroupRendering && groupRenderProgress && (
                <div className="space-y-3 p-3 bg-ark-black/50 rounded border border-ark-border">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-ark-white">
                      에피소드 {groupRenderProgress.completed_episodes}/{groupRenderProgress.total_episodes}
                    </span>
                    <span className="text-ark-orange">
                      {groupRenderProgress.overall_progress.toFixed(0)}%
                    </span>
                  </div>
                  <div className="w-full bg-ark-black rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-ark-orange h-2 rounded-full transition-all duration-300"
                      style={{ width: `${groupRenderProgress.overall_progress}%` }}
                    />
                  </div>
                  {groupRenderProgress.current_episode_id && (
                    <p className="text-xs text-ark-gray truncate">
                      현재: {groupRenderProgress.current_episode_id.split('/').pop()}
                    </p>
                  )}
                  <button
                    onClick={cancelGroupRender}
                    className="w-full ark-btn text-sm text-red-400 hover:text-red-300 border-red-400/30"
                  >
                    취소
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {/* 필수 섹션 */}
              <div className="space-y-2">
                <p className="text-xs text-ark-gray font-medium">필수</p>

                {/* 음성 준비 */}
                <label className="flex items-center justify-between p-2 bg-ark-black/30 rounded cursor-pointer hover:bg-ark-black/50">
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={batchTasks.prepare}
                      onChange={e => setBatchTasks(prev => ({ ...prev, prepare: e.target.checked }))}
                      className="w-4 h-4 rounded border-ark-border bg-ark-black text-ark-orange focus:ring-ark-orange"
                    />
                    <span className="text-sm text-ark-white">음성 준비 (prepare)</span>
                  </div>
                  <span className="text-xs text-ark-gray">
                    {preparedCount}/{characterStats.withVoice} 완료
                  </span>
                </label>

                {/* 사전 더빙 */}
                <label className="flex items-center justify-between p-2 bg-ark-black/30 rounded cursor-pointer hover:bg-ark-black/50">
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={batchTasks.render}
                      onChange={e => setBatchTasks(prev => ({ ...prev, render: e.target.checked }))}
                      className="w-4 h-4 rounded border-ark-border bg-ark-black text-ark-orange focus:ring-ark-orange"
                    />
                    <span className="text-sm text-ark-white">사전 더빙 (render)</span>
                  </div>
                  <span className="text-xs text-ark-gray">
                    {episodeCacheStats.completed}/{episodeCacheStats.total} 에피소드
                  </span>
                </label>
              </div>

              {/* 고퀄리티 섹션 (선택) */}
              <div className="space-y-2">
                <p className="text-xs text-ark-gray font-medium">고퀄리티 (선택)</p>

                {/* 모델 학습 */}
                <div className="p-2 bg-ark-black/30 rounded">
                  <label className="flex items-center justify-between cursor-pointer hover:bg-ark-black/50">
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={batchTasks.finetune}
                        onChange={e => setBatchTasks(prev => ({ ...prev, finetune: e.target.checked }))}
                        className="w-4 h-4 rounded border-ark-border bg-ark-black text-purple-500 focus:ring-purple-500"
                      />
                      <span className="text-sm text-ark-white">모델 학습 (fine-tune)</span>
                    </div>
                    <span className="text-xs text-ark-gray">
                      {finetunedCount}/{characterStats.withVoice} 완료
                    </span>
                  </label>

                  {/* 학습 대상 (모델 학습 선택 시만 표시) */}
                  {batchTasks.finetune && (
                    <div className="mt-3 ml-7 space-y-2 border-l-2 border-purple-500/30 pl-3">
                      <p className="text-xs text-ark-gray">학습 대상:</p>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={finetuneTarget.appearance}
                          onChange={e => setFinetuneTarget(prev => ({ ...prev, appearance: e.target.checked }))}
                          className="w-3 h-3 rounded border-ark-border bg-ark-black text-purple-500 focus:ring-purple-500"
                        />
                        <span className="text-xs text-ark-white">등장 캐릭터 (음성 보유)</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={finetuneTarget.mapped}
                          onChange={e => setFinetuneTarget(prev => ({ ...prev, mapped: e.target.checked }))}
                          className="w-3 h-3 rounded border-ark-border bg-ark-black text-purple-500 focus:ring-purple-500"
                        />
                        <span className="text-xs text-ark-white">매핑된 캐릭터</span>
                      </label>
                    </div>
                  )}
                </div>
              </div>

              {/* 실행 버튼 */}
              <button
                onClick={handleBatchExecute}
                disabled={!canExecute || isExecuting}
                className={`w-full ark-btn ark-btn-primary text-sm py-3 ${
                  (!canExecute || isExecuting) ? 'opacity-50 cursor-not-allowed' : ''
                }`}
              >
                {isExecuting ? '실행 중...' : '일괄 실행'}
              </button>

              {/* 상태 메시지 */}
              {!gptSovitsStatus?.api_running && (
                <p className="text-xs text-ark-yellow text-center">
                  * GPT-SoVITS를 먼저 시작하세요
                </p>
              )}
              {groupRenderError && (
                <p className="text-xs text-red-400 text-center">
                  {groupRenderError}
                </p>
              )}
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
        </div>
      </div>

      {/* 음성 매핑 모달 */}
      <VoiceMappingModal
        isOpen={isVoiceMappingModalOpen}
        onClose={() => setIsVoiceMappingModalOpen(false)}
      />
    </div>
  )
}
