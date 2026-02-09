import { useEffect, useMemo, useState, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useAppStore, isMysteryName, type GroupRenderState, type EpisodeRenderResult } from '../stores/appStore'
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

// 대기 중인 다음 단계
type PendingStep = 'finetune' | 'render' | null

// 에피소드 상태 아이콘
function EpisodeStatusIcon({ status }: { status: EpisodeRenderResult['status'] }) {
  switch (status) {
    case 'completed':
      return <span className="text-green-400 flex-shrink-0">&#10003;</span>
    case 'skipped':
      return <span className="text-ark-gray flex-shrink-0">&ndash;</span>
    case 'rendering':
      return <span className="text-ark-orange flex-shrink-0 ark-pulse">&#9654;</span>
    case 'loading':
      return <span className="text-ark-orange flex-shrink-0 ark-pulse">&#9678;</span>
    case 'failed':
      return <span className="text-red-400 flex-shrink-0">&#10007;</span>
    default:
      return <span className="text-ark-gray/50 flex-shrink-0">&#9675;</span>
  }
}

// 그룹 렌더링 대시보드
function GroupRenderDashboard({ state, onCancel }: { state: GroupRenderState; onCancel: () => void }) {
  const { t } = useTranslation()
  const currentRef = useRef<HTMLDivElement>(null)

  // 현재 진행 중인 에피소드로 자동 스크롤
  useEffect(() => {
    currentRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [state.currentEpisodeIndex])

  // 전체 진행률 계산
  const completedCount = state.episodes.filter(e => e.status === 'completed' || e.status === 'skipped').length
  const totalCount = state.episodes.length
  const overallPercent = totalCount > 0 ? (completedCount / totalCount) * 100 : 0

  return (
    <div className="space-y-3 p-3 bg-ark-black/50 rounded border border-ark-border">
      {/* 헤더 + 전체 진행률 */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-ark-white font-medium">{t('group.section.preRendering')}</span>
        <span className="text-ark-orange">
          {completedCount}/{totalCount} ({overallPercent.toFixed(0)}%)
        </span>
      </div>
      <div className="w-full bg-ark-black rounded-full h-2 overflow-hidden">
        <div
          className="bg-ark-orange h-2 rounded-full transition-all duration-300"
          style={{ width: `${overallPercent}%` }}
        />
      </div>

      {/* 에피소드 리스트 */}
      <div className="max-h-64 overflow-y-auto space-y-1">
        {state.episodes.map((ep, idx) => (
          <div
            key={ep.episodeId}
            ref={idx === state.currentEpisodeIndex ? currentRef : undefined}
            className={`px-2 py-1.5 rounded text-xs ${
              ep.status === 'rendering' || ep.status === 'loading'
                ? 'bg-ark-orange/10 border border-ark-orange/30'
                : 'bg-ark-black/30'
            }`}
          >
            <div className="flex items-center gap-2">
              <EpisodeStatusIcon status={ep.status} />
              <span className={`truncate flex-1 ${
                ep.status === 'completed' ? 'text-green-400' :
                ep.status === 'failed' ? 'text-red-400' :
                ep.status === 'skipped' ? 'text-ark-gray' :
                ep.status === 'rendering' || ep.status === 'loading' ? 'text-ark-white' :
                'text-ark-gray/70'
              }`}>
                {ep.title}
              </span>
              {ep.status === 'skipped' && (
                <span className="text-[10px] text-ark-gray">{t('common.cached')}</span>
              )}
              {ep.status === 'rendering' && ep.totalDialogues > 0 && (
                <span className="text-[10px] text-ark-orange">
                  {ep.completedDialogues}/{ep.totalDialogues}
                </span>
              )}
              {ep.status === 'loading' && (
                <span className="text-[10px] text-ark-orange">{t('dubbing.status.configuringVoice')}</span>
              )}
            </div>
            {/* 현재 렌더링 중인 에피소드: 대사 진행률 바 + 텍스트 */}
            {ep.status === 'rendering' && ep.totalDialogues > 0 && (
              <div className="mt-1 ml-5">
                <div className="w-full bg-ark-black rounded-full h-1 overflow-hidden">
                  <div
                    className="bg-ark-orange/70 h-1 rounded-full transition-all duration-300"
                    style={{ width: `${ep.totalDialogues > 0 ? (ep.completedDialogues / ep.totalDialogues) * 100 : 0}%` }}
                  />
                </div>
                {state.currentDialogueText && (
                  <p className="text-[10px] text-ark-gray/70 mt-0.5 truncate">
                    &ldquo;{state.currentDialogueText}&rdquo;
                  </p>
                )}
              </div>
            )}
            {/* 실패한 에피소드: 에러 메시지 */}
            {ep.status === 'failed' && ep.error && (
              <p className="text-[10px] text-red-400/70 mt-0.5 ml-5 truncate">
                {ep.error}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* 취소 버튼 */}
      <button
        onClick={onCancel}
        className="w-full ark-btn text-sm text-red-400 hover:text-red-300 border-red-400/30"
      >
        {t('common.cancel')}
      </button>
    </div>
  )
}

export default function GroupSetupPanel() {
  const { t } = useTranslation()
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
  const [pendingStep, setPendingStep] = useState<PendingStep>(null)
  const prevTrainingActiveRef = useRef(false)

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
    groupRenderState,
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
    // 알 수 없는 화자
    unknownSpeakerCharId,
    // 나레이션
    narratorCharId,
    // 캐릭터 이름 조회용
    voiceCharacters,
    loadVoiceCharacters,
  } = useAppStore()

  // 초기 로드
  useEffect(() => {
    loadTrainingStatus()
    loadTrainedModels()
    loadVoiceCharacters()
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

  // 나레이션 분리 (char_id가 null이고 이름이 "나레이터"인 항목)
  const narrationInfo = useMemo(() => {
    const narrator = groupCharacters.find(c => c.char_id === null && c.name === '나레이터')
    return narrator ? narrator.dialogue_count : 0
  }, [groupCharacters])

  // 알 수 없는 화자("???") 대사 수
  const unknownSpeakerCount = useMemo(() => {
    return groupCharacters
      .filter(c => !c.char_id && c.name && isMysteryName(c.name))
      .reduce((sum, c) => sum + c.dialogue_count, 0)
  }, [groupCharacters])

  // 실제 캐릭터만 (나레이터, 미스터리 이름 전용 제외)
  const actualCharacters = useMemo(() => {
    return groupCharacters.filter(c => {
      // 나레이터 제외
      if (c.char_id === null && c.name === '나레이터') return false
      // 미스터리 이름만 있는 NPC 제외
      if (!c.char_id && c.name && isMysteryName(c.name)) return false
      return true
    })
  }, [groupCharacters])

  // 캐릭터 통계 (나레이터 제외)
  const characterStats = useMemo(() => {
    const withVoice = actualCharacters.filter(c => c.has_voice).length
    const trained = actualCharacters.filter(c => {
      const voiceId = c.voice_char_id || c.char_id
      return voiceId && trainedCharIds.has(voiceId)
    }).length
    const total = actualCharacters.length
    return { withVoice, trained, total }
  }, [actualCharacters, trainedCharIds])

  // 음성 없는 캐릭터 (매핑 대상, 나레이터 제외)
  const voicelessCharacters = useMemo(() => {
    return actualCharacters.filter(c => !c.has_voice && c.name)
  }, [actualCharacters])

  // 매핑된 음성 ID들
  const mappedVoiceIds = useMemo(() => {
    return voicelessCharacters
      .map(c => {
        const key = c.char_id || `name:${c.name}`
        return getSpeakerVoice(key, c.name)
      })
      .filter((id): id is string => id !== null)
  }, [voicelessCharacters, getSpeakerVoice, speakerVoiceMap, defaultFemaleVoices, defaultMaleVoices])

  // 준비 가능한 캐릭터 수 (음성 있고 미준비, 나레이터 제외)
  const preparableCount = useMemo(() => {
    const charIds = actualCharacters
      .filter(c => c.has_voice)
      .map(c => c.voice_char_id || c.char_id)
      .filter((id): id is string => id !== null && !trainedCharIds.has(id))
    return charIds.length
  }, [actualCharacters, trainedCharIds])

  // 준비 완료된 캐릭터 수 (나레이터 제외)
  const preparedCount = useMemo(() => {
    return actualCharacters.filter(c => {
      const voiceId = c.voice_char_id || c.char_id
      return voiceId && trainedCharIds.has(voiceId)
    }).length
  }, [actualCharacters, trainedCharIds])

  // Fine-tuned 완료된 캐릭터 수 (나레이터 제외)
  const finetunedCount = useMemo(() => {
    return actualCharacters.filter(c => {
      const voiceId = c.voice_char_id || c.char_id
      return voiceId && getModelType(voiceId) === 'finetuned'
    }).length
  }, [actualCharacters, getModelType, trainedModels])

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

  // 학습 완료 감지 및 다음 단계 자동 실행
  useEffect(() => {
    // 학습이 활성 → 비활성으로 변경되었을 때
    if (prevTrainingActiveRef.current && !isTrainingActive && pendingStep) {
      const executeNextStep = async () => {
        if (pendingStep === 'finetune' && batchTasks.finetune) {
          // finetune 실행
          const targetCharIds: string[] = []
          if (finetuneTarget.appearance) {
            const ids = actualCharacters
              .filter(c => c.has_voice)
              .map(c => c.voice_char_id || c.char_id)
              .filter((id): id is string => id !== null && canFinetune(id))
            targetCharIds.push(...ids)
          }
          if (finetuneTarget.mapped) {
            const ids = mappedVoiceIds.filter(id => canFinetune(id))
            targetCharIds.push(...ids)
          }
          const uniqueIds = [...new Set(targetCharIds)]
          if (uniqueIds.length > 0) {
            await startBatchTraining(uniqueIds, 'finetune')
            setPendingStep(batchTasks.render ? 'render' : null)
          } else {
            // finetune 대상 없으면 render로
            if (batchTasks.render) {
              setPendingStep('render')
            } else {
              setPendingStep(null)
              setIsExecuting(false)
            }
          }
        } else if (pendingStep === 'render' && batchTasks.render && selectedGroupId) {
          // render 실행
          await startGroupRender(selectedGroupId)
          setPendingStep(null)
          setIsExecuting(false)
        } else {
          setPendingStep(null)
          setIsExecuting(false)
        }
      }
      executeNextStep()
    }
    prevTrainingActiveRef.current = isTrainingActive
  }, [isTrainingActive, pendingStep, batchTasks, finetuneTarget, actualCharacters, mappedVoiceIds, canFinetune, startBatchTraining, startGroupRender, selectedGroupId])

  // 일괄 실행
  const handleBatchExecute = async () => {
    if (!selectedGroupId) return

    setIsExecuting(true)
    setPendingStep(null)

    try {
      // 1. 음성 준비 (prepare)
      if (batchTasks.prepare && preparableCount > 0) {
        const charIds = actualCharacters
          .filter(c => c.has_voice)
          .map(c => c.voice_char_id || c.char_id)
          .filter((id): id is string => id !== null && !trainedCharIds.has(id))

        if (charIds.length > 0) {
          await startBatchTraining(charIds, 'prepare')
          // 다음 단계 설정: finetune → render 순서
          if (batchTasks.finetune) {
            setPendingStep('finetune')
          } else if (batchTasks.render) {
            setPendingStep('render')
          }
          return // 학습 완료 후 자동으로 다음 단계 진행
        }
      }

      // 2. 모델 학습 (finetune) - prepare가 없거나 이미 완료된 경우
      if (batchTasks.finetune) {
        const targetCharIds: string[] = []

        if (finetuneTarget.appearance) {
          const ids = actualCharacters
            .filter(c => c.has_voice)
            .map(c => c.voice_char_id || c.char_id)
            .filter((id): id is string => id !== null && canFinetune(id))
          targetCharIds.push(...ids)
        }

        if (finetuneTarget.mapped) {
          const ids = mappedVoiceIds.filter(id => canFinetune(id))
          targetCharIds.push(...ids)
        }

        const uniqueIds = [...new Set(targetCharIds)]
        if (uniqueIds.length > 0) {
          await startBatchTraining(uniqueIds, 'finetune')
          if (batchTasks.render) {
            setPendingStep('render')
          }
          return // 학습 완료 후 자동으로 다음 단계 진행
        }
      }

      // 3. 사전 더빙 (render) - 학습이 없거나 이미 완료된 경우
      if (batchTasks.render && !isTrainingActive) {
        await startGroupRender(selectedGroupId)
      }
      setIsExecuting(false)
    } catch (error) {
      console.error('일괄 실행 오류:', error)
      setIsExecuting(false)
      setPendingStep(null)
    }
  }

  // 학습 취소
  const handleCancelTraining = async () => {
    setPendingStep(null)
    setIsExecuting(false)
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
          {t('group.section.setup')}
        </h3>
        <button
          onClick={cancelPrepare}
          className="text-ark-gray hover:text-ark-white text-sm"
        >
          {t('common.close')}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* 그룹 정보 */}
        <div className="p-4 border-b border-ark-border bg-ark-panel/30">
          <div className="flex items-center justify-between">
            <span className="text-ark-white font-medium">{groupInfo?.name || '그룹'}</span>
            <span className="text-xs text-ark-gray">{t('group.info.episodeCount', { count: groupEpisodes.length })}</span>
          </div>
        </div>

        {/* 그룹 캐릭터 목록 */}
        <div className="p-4 border-b border-ark-border">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-ark-gray">{t('group.section.characters')}</h4>
            <span className="text-xs text-ark-gray">
              {t('group.characters.hasVoice', { withVoice: characterStats.withVoice, total: characterStats.total })}
            </span>
          </div>
          {isLoadingCharacters ? (
            <div className="text-center text-ark-gray py-4 ark-pulse">{t('common.loading')}</div>
          ) : actualCharacters.length === 0 ? (
            <div className="text-center text-ark-gray py-4">{t('common.noCharacters')}</div>
          ) : (
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {actualCharacters.map((char, idx) => (
                <div
                  key={`${char.char_id}-${char.name}-${idx}`}
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
                      }
                      return null
                    })()}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* 나레이션 대사 수 */}
          {narrationInfo > 0 && (
            <div className="mt-3 p-2 bg-purple-500/10 rounded border border-purple-500/20">
              <div className="flex items-center justify-between">
                <span className="text-xs text-purple-400">{t('character.narration.labelShort')}</span>
                <span className="text-xs text-purple-300">{t('character.dialogueCount', { count: narrationInfo })}</span>
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

        {/* 음성 매핑 */}
        <div className="p-4 border-b border-ark-border">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-ark-gray">{t('group.section.voiceMapping')}</h4>
            <span className="text-xs text-ark-gray">
              {voicelessCharacters.length > 0
                ? t('group.mapping.count', { mapped: mappedCount, total: voicelessCharacters.length })
                : t('group.status.allHaveVoice')}
            </span>
          </div>
          {voicelessCharacters.length === 0 ? (
            <div className="flex items-center gap-2 text-green-400">
              <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
              </svg>
              <span className="text-sm">{t('group.status.allHaveVoice')}</span>
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
                {t('group.button.voiceMappingSetup')}
              </button>
            </div>
          )}
        </div>

        {/* 일괄 작업 */}
        <div className="p-4 border-b border-ark-border">
          <h4 className="text-sm font-medium text-ark-gray mb-4">{t('group.section.batchTasks')}</h4>

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
                      {currentTrainingJob.mode === 'prepare' ? t('character.status.preparing') : t('character.status.training')}
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
                      {t('group.queue.label', { count: trainingQueue.length })}
                    </p>
                  )}
                  <button
                    onClick={handleCancelTraining}
                    className="w-full ark-btn text-sm text-red-400 hover:text-red-300 border-red-400/30"
                  >
                    {t('common.cancel')}
                  </button>
                </div>
              )}

              {/* 그룹 렌더링 진행 중 */}
              {isGroupRendering && groupRenderState && (
                <GroupRenderDashboard
                  state={groupRenderState}
                  onCancel={cancelGroupRender}
                />
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {/* 필수 섹션 */}
              <div className="space-y-2">
                <p className="text-xs text-ark-gray font-medium">{t('group.section.required')}</p>

                {/* 음성 준비 */}
                <label className="flex items-center justify-between p-2 bg-ark-black/30 rounded cursor-pointer hover:bg-ark-black/50">
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={batchTasks.prepare}
                      onChange={e => setBatchTasks(prev => ({ ...prev, prepare: e.target.checked }))}
                      className="w-4 h-4 rounded border-ark-border bg-ark-black text-ark-orange focus:ring-ark-orange"
                    />
                    <span className="text-sm text-ark-white">{t('group.task.prepare')}</span>
                  </div>
                  <span className="text-xs text-ark-gray">
                    {t('group.status.preparedCount', { prepared: preparedCount, total: characterStats.withVoice })}
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
                    <span className="text-sm text-ark-white">{t('group.task.render')}</span>
                  </div>
                  <span className="text-xs text-ark-gray">
                    {t('group.episodes.count', { completed: episodeCacheStats.completed, total: episodeCacheStats.total })}
                  </span>
                </label>
              </div>

              {/* 고퀄리티 섹션 (선택) */}
              <div className="space-y-2">
                <p className="text-xs text-ark-gray font-medium">{t('group.section.quality')}</p>

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
                      <span className="text-sm text-ark-white">{t('group.task.finetune')}</span>
                    </div>
                    <span className="text-xs text-ark-gray">
                      {t('group.status.finetunedCount', { finetuned: finetunedCount, total: characterStats.withVoice })}
                    </span>
                  </label>
                  <p className="text-[10px] text-ark-yellow/70 mt-1 ml-7">
                    {t('group.warning.timeConsuming')}
                  </p>

                  {/* 학습 대상 (모델 학습 선택 시만 표시) */}
                  {batchTasks.finetune && (
                    <div className="mt-3 ml-7 space-y-2 border-l-2 border-purple-500/30 pl-3">
                      <p className="text-xs text-ark-gray">{t('group.label.trainTargets')}</p>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={finetuneTarget.appearance}
                          onChange={e => setFinetuneTarget(prev => ({ ...prev, appearance: e.target.checked }))}
                          className="w-3 h-3 rounded border-ark-border bg-ark-black text-purple-500 focus:ring-purple-500"
                        />
                        <span className="text-xs text-ark-white">{t('group.target.appearanceCharacters')}</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={finetuneTarget.mapped}
                          onChange={e => setFinetuneTarget(prev => ({ ...prev, mapped: e.target.checked }))}
                          className="w-3 h-3 rounded border-ark-border bg-ark-black text-purple-500 focus:ring-purple-500"
                        />
                        <span className="text-xs text-ark-white">{t('group.target.mappedCharacters')}</span>
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
                {isExecuting ? t('group.status.executing') : t('group.button.batchExecute')}
              </button>

              {/* 상태 메시지 */}
              {!gptSovitsStatus?.api_running && (
                <p className="text-xs text-ark-yellow text-center">
                  {t('group.note.startGptSovitsFirst')}
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
                  ? t('group.status.synthesizing')
                  : gptSovitsStatus?.api_running
                    ? t('common.connected')
                    : t('common.waiting')}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 음성 매핑 모달 */}
      <VoiceMappingModal
        isOpen={isVoiceMappingModalOpen}
        onClose={() => setIsVoiceMappingModalOpen(false)}
        characters={actualCharacters}
      />
    </div>
  )
}
