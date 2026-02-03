import { create } from 'zustand'
import {
  episodesApi,
  storiesApi,
  ttsApi,
  ocrApi,
  voiceApi,
  trainingApi,
  renderApi,
  healthCheck,
  createDialogueStream,
  createTrainingStream,
  createRenderStream,
  type EpisodeDetail,
  type DialogueInfo,
  type EpisodeSummary,
  type CategoryInfo,
  type StoryGroupInfo,
  type GroupEpisodeInfo,
  type GroupCharacterInfo,
  type MonitorInfo,
  type WindowInfo,
  type DetectDialogueResponse,
  type BoundingBox,
  type MatchDialogueResponse,
  type TrainingJob,
  type TrainedModel,
  type RenderProgress,
  type VoiceCharacter,
} from '../services/api'

type CaptureMode = 'monitor' | 'window'

interface AppState {
  // 연결 상태
  backendStatus: 'connected' | 'disconnected' | 'checking'

  // 카테고리/그룹 관련
  categories: CategoryInfo[]
  selectedCategoryId: string | null
  storyGroups: StoryGroupInfo[]
  selectedGroupId: string | null
  groupEpisodes: GroupEpisodeInfo[]
  isLoadingCategories: boolean
  isLoadingGroups: boolean
  isLoadingGroupEpisodes: boolean

  // 에피소드 관련 (기존)
  episodes: EpisodeSummary[]
  chapters: Record<string, EpisodeSummary[]>
  selectedEpisodeId: string | null
  selectedEpisode: EpisodeDetail | null
  isLoadingEpisodes: boolean
  isLoadingEpisode: boolean

  // 음성 관련
  defaultCharId: string | null  // 기본 캐릭터 ID (하위 호환)
  defaultVoices: string[]  // 다중 기본 음성 목록 (하위 호환 - 여성으로 취급)
  defaultFemaleVoices: string[]  // 기본 여성 음성
  defaultMaleVoices: string[]  // 기본 남성 음성
  isPlaying: boolean
  currentDialogue: DialogueInfo | null

  // OCR 관련
  monitors: MonitorInfo[]
  selectedMonitorId: number
  windows: WindowInfo[]
  selectedWindowHwnd: number | null
  captureMode: CaptureMode
  ocrLanguage: string
  isMonitoring: boolean
  detectedText: string | null
  detectedConfidence: number
  capturedImage: string | null  // base64 (legacy)
  capturedImageUrl: string | null  // 직접 이미지 URL
  ocrError: string | null
  customRegion: BoundingBox | null  // 사용자 지정 영역
  useCustomRegion: boolean  // 사용자 지정 영역 사용 여부

  // 대사 매칭 관련
  isDubbingMode: boolean  // 실시간 더빙 모드 활성화
  matchedDialogue: DialogueInfo | null  // 매칭된 대사
  matchedIndex: number  // 매칭된 대사 인덱스
  matchSimilarity: number  // 매칭 유사도
  isMatching: boolean  // 매칭 진행 중
  showCapturePreview: boolean  // 캡처 미리보기 표시

  // 더빙 준비 관련
  isPrepared: boolean  // 더빙 준비 완료 여부
  groupCharacters: GroupCharacterInfo[]  // 현재 그룹 캐릭터 목록 (전체 통계용)
  episodeCharacters: GroupCharacterInfo[]  // 현재 에피소드 캐릭터 목록 (음성 매핑용)
  isLoadingCharacters: boolean  // 캐릭터 로딩 중
  isLoadingEpisodeCharacters: boolean  // 에피소드 캐릭터 로딩 중
  speakerVoiceMap: Record<string, string>  // speaker_id → voice_id 매핑
  narratorCharId: string | null  // 나레이터 캐릭터 ID
  autoPlayOnMatch: boolean  // 매칭 시 자동 재생

  // 음성 캐릭터 목록 (나레이터 선택용)
  voiceCharacters: VoiceCharacter[]  // 음성 있는 모든 캐릭터
  isLoadingVoiceCharacters: boolean

  // 음성 모델 학습 관련
  isTrainingActive: boolean  // 학습 진행 중
  currentTrainingJob: TrainingJob | null  // 현재 학습 작업
  trainingQueue: TrainingJob[]  // 대기 중인 학습 작업
  trainedModels: TrainedModel[]  // 학습 완료된 모델
  trainedCharIds: Set<string>  // 학습 완료된 캐릭터 ID (빠른 조회용)
  trainingError: string | null  // 학습 오류

  // 렌더링 관련
  isRendering: boolean  // 렌더링 진행 중
  renderProgress: RenderProgress | null  // 현재 렌더링 진행률
  cachedEpisodes: string[]  // 캐시된 에피소드 목록
  renderError: string | null  // 렌더링 오류

  // GPT-SoVITS 관련
  gptSovitsStatus: { installed: boolean; api_running: boolean; synthesizing?: boolean } | null
  isStartingGptSovits: boolean
  gptSovitsError: string | null

  // 액션
  checkBackendStatus: () => Promise<void>
  loadCategories: () => Promise<void>
  selectCategory: (categoryId: string) => Promise<void>
  selectStoryGroup: (groupId: string) => Promise<void>
  loadEpisodes: () => Promise<void>
  selectEpisode: (episodeId: string) => Promise<void>
  clearEpisode: () => void
  playDialogue: (dialogue: DialogueInfo) => Promise<void>
  stopPlayback: () => void
  setDefaultCharId: (charId: string | null) => void

  // 다중 기본 음성 액션
  addDefaultVoice: (charId: string) => void
  removeDefaultVoice: (index: number) => void
  updateDefaultVoice: (index: number, charId: string) => void
  // 성별 기반 기본 음성 액션
  addDefaultFemaleVoice: (charId: string) => void
  removeDefaultFemaleVoice: (index: number) => void
  updateDefaultFemaleVoice: (index: number, charId: string) => void
  addDefaultMaleVoice: (charId: string) => void
  removeDefaultMaleVoice: (index: number) => void
  updateDefaultMaleVoice: (index: number, charId: string) => void
  getSpeakerVoice: (speakerId: string, speakerName?: string) => string | null

  // OCR 액션
  loadMonitors: () => Promise<void>
  setMonitor: (monitorId: number) => void
  loadWindows: () => Promise<void>
  setWindow: (hwnd: number) => void
  setCaptureMode: (mode: CaptureMode) => void
  setOcrLanguage: (lang: string) => void
  detectOnce: () => Promise<DetectDialogueResponse | null>
  captureScreen: () => Promise<void>
  captureDialogue: () => Promise<void>
  captureWindow: () => void
  startMonitoring: () => void
  stopMonitoring: () => void
  clearOcrResult: () => void
  // 사용자 지정 영역
  setCustomRegion: (region: BoundingBox) => Promise<void>
  setUseCustomRegion: (use: boolean) => void
  detectCustomRegion: () => Promise<DetectDialogueResponse | null>
  captureCustomRegion: () => void

  // 실시간 더빙 모드
  toggleDubbingMode: () => void
  setDubbingMode: (enabled: boolean) => void
  matchOcrResult: () => Promise<MatchDialogueResponse | null>
  clearMatch: () => void
  toggleCapturePreview: () => void

  // 더빙 준비
  prepareForDubbing: () => Promise<void>
  cancelPrepare: () => void
  loadGroupCharacters: (groupId: string) => Promise<void>
  loadEpisodeCharacters: (episodeId: string) => Promise<void>
  setSpeakerVoice: (speakerId: string, voiceId: string | null) => void
  clearSpeakerVoice: (speakerId: string) => void
  setNarratorCharId: (charId: string | null) => void
  loadVoiceCharacters: () => Promise<void>
  toggleAutoPlay: () => void
  startDubbing: () => void
  stopDubbing: () => void

  // 음성 모델 학습
  loadTrainingStatus: () => Promise<void>
  loadTrainedModels: () => Promise<void>
  startBatchTraining: (charIds?: string[]) => Promise<void>
  cancelTraining: (jobId: string) => Promise<void>
  clearAllTrainedModels: () => Promise<void>
  subscribeToTrainingProgress: () => void
  unsubscribeFromTrainingProgress: () => void
  isCharacterTrained: (charId: string) => boolean

  // 렌더링
  loadRenderStatus: () => Promise<void>
  startRender: (episodeId: string, force?: boolean) => Promise<void>
  cancelRender: () => Promise<void>
  subscribeToRenderProgress: (episodeId: string) => void
  unsubscribeFromRenderProgress: () => void
  getRenderedAudioUrl: (index: number) => string | null
  isDialogueRendered: (index: number) => boolean

  // GPT-SoVITS
  checkGptSovitsStatus: () => Promise<void>
  startGptSovits: () => Promise<void>
}

// localStorage 키
const STORAGE_KEY = 'avt_app_state'

// 저장할 상태 타입
interface PersistedState {
  selectedCategoryId: string | null
  selectedGroupId: string | null
  selectedEpisodeId: string | null
  defaultCharId: string | null  // 하위 호환
  defaultVoices: string[]  // 다중 기본 음성 (하위 호환)
  defaultFemaleVoices: string[]  // 기본 여성 음성
  defaultMaleVoices: string[]  // 기본 남성 음성
  narratorCharId: string | null
  autoPlayOnMatch: boolean
  npcVoiceMap: Record<string, string>  // NPC 음성 매핑 (char_id → voice_id)
}

// 자동 음성 선택 특수 값
export const AUTO_VOICE_FEMALE = '__auto_female__'
export const AUTO_VOICE_MALE = '__auto_male__'

// localStorage에서 상태 로드
const loadPersistedState = (): Partial<PersistedState> => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      return JSON.parse(saved)
    }
  } catch (error) {
    console.error('Failed to load persisted state:', error)
  }
  return {}
}

// localStorage에 상태 저장
const savePersistedState = (state: PersistedState) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch (error) {
    console.error('Failed to save persisted state:', error)
  }
}

// 초기 상태 로드
const persistedState = loadPersistedState()

// 현재 상태를 localStorage에 저장하는 헬퍼 (스토어 내부에서 호출)
const persistCurrentState = (get: () => AppState) => {
  const state = get()
  savePersistedState({
    selectedCategoryId: state.selectedCategoryId,
    selectedGroupId: state.selectedGroupId,
    selectedEpisodeId: state.selectedEpisodeId,
    defaultCharId: state.defaultCharId,
    defaultVoices: state.defaultVoices,
    defaultFemaleVoices: state.defaultFemaleVoices,
    defaultMaleVoices: state.defaultMaleVoices,
    narratorCharId: state.narratorCharId,
    autoPlayOnMatch: state.autoPlayOnMatch,
    npcVoiceMap: state.speakerVoiceMap,  // NPC 음성 매핑 저장
  })
}

// 문자열 해시 함수 (화자별 음성 분배용)
export const simpleHash = (str: string): number => {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash  // 32bit integer 변환
  }
  return Math.abs(hash)
}

// 오디오 재생 관리
let currentAudio: HTMLAudioElement | null = null

// 실시간 TTS 합성 및 재생 헬퍼 함수
async function synthesizeAndPlayDialogue(
  text: string,
  charId: string,
  set: (state: Partial<AppState>) => void
) {
  try {
    console.log('[playDialogue] GPT-SoVITS 합성:', charId, text.substring(0, 30))
    const audioBlob = await ttsApi.synthesize(text, charId)
    const audioUrl = URL.createObjectURL(audioBlob)

    currentAudio = new Audio(audioUrl)
    currentAudio.onended = () => {
      set({ isPlaying: false, currentDialogue: null })
      URL.revokeObjectURL(audioUrl)
    }
    currentAudio.onerror = (e) => {
      console.error('[playDialogue] 오디오 재생 오류:', e)
      set({ isPlaying: false, currentDialogue: null })
      URL.revokeObjectURL(audioUrl)
    }

    await currentAudio.play()
  } catch (error) {
    console.error('[playDialogue] GPT-SoVITS 합성 실패:', error)
    set({ isPlaying: false, currentDialogue: null })
  }
}

// OCR 모니터링 관련
let monitoringInterval: ReturnType<typeof setInterval> | null = null
let sseStream: { close: () => void } | null = null  // SSE 스트림
let isOcrInProgress = false  // OCR 진행 중 플래그
let lastOcrSuccessTime = 0   // 마지막 OCR 성공 시간
let lastMatchedText = ''     // 마지막 매칭된 텍스트 (중복 방지)
let matchDebounceTimer: ReturnType<typeof setTimeout> | null = null

// OCR 설정
const OCR_COOLDOWN_MS = 1500      // OCR 성공 후 쿨다운 (1.5초)
const OCR_POLL_INTERVAL_MS = 800  // 폴링 간격 (0.8초)
const MATCH_DEBOUNCE_MS = 500     // 매칭 디바운스 (0.5초)
const USE_SSE_STREAMING = true    // SSE 스트리밍 사용 여부

export const useAppStore = create<AppState>((set, get) => ({
  // 초기 상태 (localStorage에서 복원)
  backendStatus: 'checking',
  categories: [],
  selectedCategoryId: persistedState.selectedCategoryId ?? null,
  storyGroups: [],
  selectedGroupId: persistedState.selectedGroupId ?? null,
  groupEpisodes: [],
  isLoadingCategories: false,
  isLoadingGroups: false,
  isLoadingGroupEpisodes: false,
  episodes: [],
  chapters: {},
  selectedEpisodeId: persistedState.selectedEpisodeId ?? null,
  selectedEpisode: null,
  isLoadingEpisodes: false,
  isLoadingEpisode: false,
  defaultCharId: persistedState.defaultCharId ?? null,
  // 하위 호환: defaultVoices가 있으면 defaultFemaleVoices로 마이그레이션
  defaultVoices: persistedState.defaultVoices ?? (persistedState.defaultCharId ? [persistedState.defaultCharId] : []),
  defaultFemaleVoices: persistedState.defaultFemaleVoices ?? persistedState.defaultVoices ?? (persistedState.defaultCharId ? [persistedState.defaultCharId] : []),
  defaultMaleVoices: persistedState.defaultMaleVoices ?? [],
  isPlaying: false,
  currentDialogue: null,

  // OCR 초기 상태
  monitors: [],
  selectedMonitorId: 1,
  windows: [],
  selectedWindowHwnd: null,
  captureMode: 'monitor',
  ocrLanguage: 'ko',
  isMonitoring: false,
  detectedText: null,
  detectedConfidence: 0,
  capturedImage: null,
  capturedImageUrl: null,
  ocrError: null,
  customRegion: null,
  useCustomRegion: false,

  // 대사 매칭 초기 상태
  isDubbingMode: false,
  matchedDialogue: null,
  matchedIndex: -1,
  matchSimilarity: 0,
  isMatching: false,
  showCapturePreview: false,

  // 더빙 준비 초기 상태
  isPrepared: false,
  groupCharacters: [],
  episodeCharacters: [],
  isLoadingCharacters: false,
  isLoadingEpisodeCharacters: false,
  speakerVoiceMap: persistedState.npcVoiceMap ?? {},  // 저장된 NPC 매핑 복원
  narratorCharId: persistedState.narratorCharId ?? null,
  autoPlayOnMatch: persistedState.autoPlayOnMatch ?? true,

  // 음성 캐릭터 목록 초기 상태
  voiceCharacters: [],
  isLoadingVoiceCharacters: false,

  // 음성 모델 학습 초기 상태
  isTrainingActive: false,
  currentTrainingJob: null,
  trainingQueue: [],
  trainedModels: [],
  trainedCharIds: new Set<string>(),
  trainingError: null,

  // 렌더링 초기 상태
  isRendering: false,
  renderProgress: null,
  cachedEpisodes: [],
  renderError: null,

  // GPT-SoVITS 초기 상태
  gptSovitsStatus: null,
  isStartingGptSovits: false,
  gptSovitsError: null,

  // 백엔드 상태 확인
  checkBackendStatus: async () => {
    const { backendStatus } = get()
    // 최초 확인 시에만 'checking' 상태 표시 (깜빡임 방지)
    if (backendStatus === 'checking') {
      const isConnected = await healthCheck()
      set({ backendStatus: isConnected ? 'connected' : 'disconnected' })
    } else {
      // 주기적 확인 시에는 상태 변경 없이 확인만
      const isConnected = await healthCheck()
      const newStatus = isConnected ? 'connected' : 'disconnected'
      // 상태가 실제로 변경된 경우에만 업데이트
      if (backendStatus !== newStatus) {
        set({ backendStatus: newStatus })
      }
    }
  },

  // 카테고리 목록 로드
  loadCategories: async () => {
    // 복원할 저장된 상태 (selectCategory가 초기화하기 전에 저장)
    const savedCategoryId = get().selectedCategoryId
    const savedGroupId = get().selectedGroupId
    const savedEpisodeId = get().selectedEpisodeId

    set({ isLoadingCategories: true })
    try {
      const data = await storiesApi.listCategories()
      set({ categories: data.categories })

      if (data.categories.length > 0) {
        // 저장된 카테고리가 유효하면 사용, 아니면 첫 번째 선택
        const targetCategoryId = savedCategoryId && data.categories.some(c => c.id === savedCategoryId)
          ? savedCategoryId
          : data.categories[0].id

        await get().selectCategory(targetCategoryId)

        // 저장된 그룹이 유효하면 선택
        const { storyGroups } = get()
        if (savedGroupId && storyGroups.some(g => g.id === savedGroupId)) {
          await get().selectStoryGroup(savedGroupId)

          // 저장된 에피소드가 유효하면 선택
          const { groupEpisodes } = get()
          if (savedEpisodeId && groupEpisodes.some(e => e.id === savedEpisodeId)) {
            await get().selectEpisode(savedEpisodeId)
          }
        }
      }
    } catch (error) {
      console.error('Failed to load categories:', error)
      set({ categories: [] })
    } finally {
      set({ isLoadingCategories: false })
    }
  },

  // 카테고리 선택
  selectCategory: async (categoryId: string) => {
    set({
      selectedCategoryId: categoryId,
      selectedGroupId: null,
      groupEpisodes: [],
      isLoadingGroups: true,
    })
    persistCurrentState(get)
    try {
      const data = await storiesApi.listCategoryGroups(categoryId)
      set({ storyGroups: data.groups })
    } catch (error) {
      console.error('Failed to load story groups:', error)
      set({ storyGroups: [] })
    } finally {
      set({ isLoadingGroups: false })
    }
  },

  // 스토리 그룹 선택
  selectStoryGroup: async (groupId: string) => {
    const { selectedGroupId: prevGroupId, isPrepared, isDubbingMode, stopDubbing, cancelPrepare } = get()

    // 다른 그룹 선택 시 더빙/준비 상태 취소
    if (prevGroupId !== groupId) {
      if (isDubbingMode) stopDubbing()
      if (isPrepared) cancelPrepare()
    }

    set({ selectedGroupId: groupId, isLoadingGroupEpisodes: true })
    persistCurrentState(get)
    try {
      const data = await storiesApi.listGroupEpisodes(groupId)
      set({ groupEpisodes: data.episodes })
    } catch (error) {
      console.error('Failed to load group episodes:', error)
      set({ groupEpisodes: [] })
    } finally {
      set({ isLoadingGroupEpisodes: false })
    }
  },

  // 에피소드 목록 로드 (기존 - 호환성 유지)
  loadEpisodes: async () => {
    set({ isLoadingEpisodes: true })
    try {
      const data = await episodesApi.listMainEpisodes()
      set({ episodes: data.episodes, chapters: data.chapters })
    } catch (error) {
      console.error('Failed to load episodes:', error)
      set({ episodes: [], chapters: {} })
    } finally {
      set({ isLoadingEpisodes: false })
    }
  },

  // 에피소드 선택
  selectEpisode: async (episodeId: string) => {
    const { loadEpisodeCharacters } = get()
    set({ isLoadingEpisode: true, selectedEpisodeId: episodeId })
    persistCurrentState(get)
    try {
      const data = await episodesApi.getEpisode(episodeId)
      set({ selectedEpisode: data })

      // 에피소드 캐릭터 목록 로드 (병렬 실행)
      loadEpisodeCharacters(episodeId)

      // 렌더링 캐시 상태 확인
      try {
        const progress = await renderApi.getProgress(episodeId)
        if (progress.status !== 'not_started') {
          set({ renderProgress: progress })
          // 캐시 완료된 에피소드면 cachedEpisodes에 추가
          const safeId = episodeId.replace(/\//g, '_').replace(/\\/g, '_')
          if (progress.status === 'completed' && !get().cachedEpisodes.includes(safeId)) {
            set({ cachedEpisodes: [...get().cachedEpisodes, safeId] })
          }
        } else {
          // 캐시 없으면 초기화
          set({ renderProgress: null })
        }
      } catch {
        // 렌더링 상태 조회 실패 (캐시 없음)
        set({ renderProgress: null })
      }
    } catch (error) {
      console.error('Failed to load episode:', error)
      set({ selectedEpisode: null })
    } finally {
      set({ isLoadingEpisode: false })
    }
  },

  // 에피소드 선택 해제
  clearEpisode: () => {
    set({ selectedEpisodeId: null, selectedEpisode: null })
  },

  // 대사 재생 (캐시 우선, 없으면 GPT-SoVITS 실시간 합성)
  playDialogue: async (dialogue: DialogueInfo) => {
    const {
      narratorCharId, defaultVoices,
      selectedEpisodeId, cachedEpisodes, renderProgress,
      getSpeakerVoice
    } = get()

    // 캐릭터 ID 결정 우선순위:
    // 1. dialogue.speaker_id (화자) → getSpeakerVoice로 음성 결정 (성별 기반)
    // 2. 나레이션이면 narratorCharId
    // 3. defaultFemaleVoices[0] (기본)
    let charIdToUse: string | null = null
    const { defaultFemaleVoices } = get()
    if (dialogue.speaker_id) {
      charIdToUse = getSpeakerVoice(dialogue.speaker_id, dialogue.speaker_name || undefined)
    } else {
      // 나레이션
      charIdToUse = narratorCharId || (defaultFemaleVoices.length > 0 ? defaultFemaleVoices[0] : (defaultVoices.length > 0 ? defaultVoices[0] : null))
    }

    // 기존 재생 중지
    if (currentAudio) {
      currentAudio.pause()
      currentAudio = null
    }

    // char_id 없으면 재생 불가
    if (!charIdToUse) {
      console.warn('[playDialogue] 캐릭터 ID 없음 - 재생 불가')
      return
    }

    set({ isPlaying: true, currentDialogue: dialogue })

    // 캐시 확인 - 배열 인덱스 찾기 (line_number가 아닌 실제 배열 인덱스 사용)
    const { selectedEpisode } = get()
    const dialogueIndex = selectedEpisode?.dialogues.findIndex(d => d.id === dialogue.id) ?? -1
    const safeEpisodeId = selectedEpisodeId?.replace(/\//g, '_').replace(/\\/g, '_')
    const safeProgressEpisodeId = renderProgress?.episode_id?.replace(/\//g, '_').replace(/\\/g, '_')
    const isCached = safeEpisodeId && cachedEpisodes.includes(safeEpisodeId)
    // 렌더링 진행 중인 에피소드에서 이미 완료된 대사 확인
    const isRendered = dialogueIndex >= 0 && renderProgress &&
      safeProgressEpisodeId === safeEpisodeId &&
      dialogueIndex < renderProgress.completed

    // 캐시된 오디오 사용 시도
    console.log('[playDialogue] 캐시 확인:', { dialogueIndex, isCached, isRendered, completed: renderProgress?.completed })
    if ((isCached || isRendered) && selectedEpisodeId && dialogueIndex >= 0) {
      const cachedAudioUrl = renderApi.getAudioUrl(selectedEpisodeId, dialogueIndex)
      console.log('[playDialogue] 캐시 재생:', dialogueIndex, cachedAudioUrl)

      try {
        currentAudio = new Audio(cachedAudioUrl)

        // 성공 시 핸들러
        currentAudio.onended = () => {
          set({ isPlaying: false, currentDialogue: null })
        }

        // 캐시 재생 실패 시 실시간 합성으로 폴백
        currentAudio.onerror = async () => {
          console.warn('[playDialogue] 캐시 재생 실패, 실시간 합성으로 폴백')
          currentAudio = null
          await synthesizeAndPlayDialogue(dialogue.text, charIdToUse!, set)
        }

        await currentAudio.play()
        console.log('[playDialogue] 캐시 재생 성공')
        return
      } catch (error) {
        console.warn('[playDialogue] 캐시 로드 실패:', error)
        // 폴백으로 진행
      }
    }

    // 실시간 GPT-SoVITS 합성
    await synthesizeAndPlayDialogue(dialogue.text, charIdToUse, set)
  },

  // 재생 중지
  stopPlayback: () => {
    if (currentAudio) {
      currentAudio.pause()
      currentAudio = null
    }
    set({ isPlaying: false, currentDialogue: null })
  },

  // 기본 캐릭터 선택 (하위 호환)
  setDefaultCharId: (charId: string | null) => {
    set({ defaultCharId: charId })
    persistCurrentState(get)
  },

  // 다중 기본 음성 추가
  addDefaultVoice: (charId: string) => {
    set((state) => {
      // 이미 있으면 추가하지 않음
      if (state.defaultVoices.includes(charId)) return state
      return { defaultVoices: [...state.defaultVoices, charId] }
    })
    persistCurrentState(get)
  },

  // 다중 기본 음성 제거
  removeDefaultVoice: (index: number) => {
    set((state) => ({
      defaultVoices: state.defaultVoices.filter((_, i) => i !== index)
    }))
    persistCurrentState(get)
  },

  // 다중 기본 음성 수정
  updateDefaultVoice: (index: number, charId: string) => {
    set((state) => {
      const newVoices = [...state.defaultVoices]
      newVoices[index] = charId
      return { defaultVoices: newVoices }
    })
    persistCurrentState(get)
  },

  // 기본 여성 음성 관리
  addDefaultFemaleVoice: (charId: string) => {
    set((state) => {
      if (state.defaultFemaleVoices.includes(charId)) return state
      return { defaultFemaleVoices: [...state.defaultFemaleVoices, charId] }
    })
    persistCurrentState(get)
  },
  removeDefaultFemaleVoice: (index: number) => {
    set((state) => ({
      defaultFemaleVoices: state.defaultFemaleVoices.filter((_, i) => i !== index)
    }))
    persistCurrentState(get)
  },
  updateDefaultFemaleVoice: (index: number, charId: string) => {
    set((state) => {
      const newVoices = [...state.defaultFemaleVoices]
      newVoices[index] = charId
      return { defaultFemaleVoices: newVoices }
    })
    persistCurrentState(get)
  },

  // 기본 남성 음성 관리
  addDefaultMaleVoice: (charId: string) => {
    set((state) => {
      if (state.defaultMaleVoices.includes(charId)) return state
      return { defaultMaleVoices: [...state.defaultMaleVoices, charId] }
    })
    persistCurrentState(get)
  },
  removeDefaultMaleVoice: (index: number) => {
    set((state) => ({
      defaultMaleVoices: state.defaultMaleVoices.filter((_, i) => i !== index)
    }))
    persistCurrentState(get)
  },
  updateDefaultMaleVoice: (index: number, charId: string) => {
    set((state) => {
      const newVoices = [...state.defaultMaleVoices]
      newVoices[index] = charId
      return { defaultMaleVoices: newVoices }
    })
    persistCurrentState(get)
  },

  // 화자별 음성 결정 (학습된 음성 → 매핑 → 성별 기반 기본 음성 자동 분배)
  getSpeakerVoice: (speakerId: string, speakerName?: string): string | null => {
    const { trainedCharIds, speakerVoiceMap, defaultFemaleVoices, defaultMaleVoices, defaultVoices } = get()

    // 1. 학습된 음성 있으면 사용
    if (trainedCharIds.has(speakerId)) return speakerId

    // 2. 수동 매핑 있으면 사용
    const mapping = speakerVoiceMap[speakerId]
    if (mapping) {
      // 특수 값 처리: 자동 여성/남성
      if (mapping === AUTO_VOICE_FEMALE) {
        if (defaultFemaleVoices.length > 0) {
          const hash = simpleHash(speakerId)
          return defaultFemaleVoices[hash % defaultFemaleVoices.length]
        }
      } else if (mapping === AUTO_VOICE_MALE) {
        if (defaultMaleVoices.length > 0) {
          const hash = simpleHash(speakerId)
          return defaultMaleVoices[hash % defaultMaleVoices.length]
        }
      } else {
        // 일반 캐릭터 매핑
        return mapping
      }
    }

    // 3. 성별 기반 기본 음성 분배
    // 남성 키워드: 명확한 남성 표현만 (남자, 남성, 소년, 청년, 노인/노년은 맥락에 따라 다르므로 제외)
    const maleKeywords = ['남자', '남성', '소년', '청년', '신사', '아저씨']
    const nameToCheck = speakerName || speakerId
    const isMale = maleKeywords.some(kw => nameToCheck.includes(kw))

    // 남성이고 남성 음성이 있으면 남성 음성 사용
    if (isMale && defaultMaleVoices.length > 0) {
      const hash = simpleHash(speakerId)
      return defaultMaleVoices[hash % defaultMaleVoices.length]
    }

    // 여성 음성이 있으면 여성 음성 사용 (기본)
    if (defaultFemaleVoices.length > 0) {
      const hash = simpleHash(speakerId)
      return defaultFemaleVoices[hash % defaultFemaleVoices.length]
    }

    // 하위 호환: 기존 defaultVoices 사용
    if (defaultVoices.length > 0) {
      const hash = simpleHash(speakerId)
      return defaultVoices[hash % defaultVoices.length]
    }

    return null
  },

  // OCR: 모니터 목록 로드
  loadMonitors: async () => {
    try {
      const data = await ocrApi.listMonitors()
      set({ monitors: data.monitors, ocrError: null })
    } catch (error) {
      console.error('Failed to load monitors:', error)
      set({ ocrError: 'Failed to load monitors' })
    }
  },

  // OCR: 모니터 선택
  setMonitor: (monitorId: number) => {
    set({ selectedMonitorId: monitorId })
  },

  // OCR: 윈도우 목록 로드
  loadWindows: async () => {
    try {
      const data = await ocrApi.listWindows()
      set({ windows: data.windows, ocrError: null })
    } catch (error) {
      console.error('Failed to load windows:', error)
      set({ ocrError: 'Failed to load windows' })
    }
  },

  // OCR: 윈도우 선택
  setWindow: (hwnd: number) => {
    set({ selectedWindowHwnd: hwnd })
  },

  // OCR: 캡처 모드 설정
  setCaptureMode: (mode: CaptureMode) => {
    set({ captureMode: mode })
    // 윈도우 모드로 전환 시 윈도우 목록 새로고침
    if (mode === 'window') {
      get().loadWindows()
    }
  },

  // OCR: 언어 선택
  setOcrLanguage: (lang: string) => {
    set({ ocrLanguage: lang })
  },

  // OCR: 한 번 감지 (모드에 따라 모니터 또는 윈도우)
  detectOnce: async () => {
    const { selectedMonitorId, selectedWindowHwnd, captureMode, ocrLanguage, isMonitoring } = get()

    // 모니터링 중일 때: 안정화 API 사용 + 쿨다운 및 중복 요청 방지
    if (isMonitoring) {
      // 이미 OCR 진행 중이면 스킵
      if (isOcrInProgress) {
        return null
      }

      // 쿨다운 중이면 스킵
      const now = Date.now()
      if (now - lastOcrSuccessTime < OCR_COOLDOWN_MS) {
        return null
      }

      // 윈도우 모드에서 안정화 API 사용
      if (captureMode === 'window' && selectedWindowHwnd) {
        try {
          isOcrInProgress = true
          const result = await ocrApi.detectWindowStable(selectedWindowHwnd, ocrLanguage)

          // 안정화되지 않은 경우 (타이핑 중) - UI 업데이트 없이 스킵
          if (!result.is_stable) {
            return null
          }

          // 새로운 대사가 아닌 경우 스킵
          if (!result.is_new || !result.text) {
            return null
          }

          // 새로운 대사 감지됨
          lastOcrSuccessTime = Date.now()
          set({
            detectedText: result.text,
            detectedConfidence: result.confidence,
          })
          // OCR 결과를 에피소드 대사와 매칭
          get().matchOcrResult()
          return { text: result.text, confidence: result.confidence, timestamp: result.timestamp }
        } catch (error) {
          console.error('Failed to detect dialogue (stable):', error)
          return null
        } finally {
          isOcrInProgress = false
        }
      }
    }

    // 수동 감지 또는 모니터 모드: 기존 방식
    try {
      isOcrInProgress = true
      set({ ocrError: null })

      let result: DetectDialogueResponse
      if (captureMode === 'window' && selectedWindowHwnd) {
        result = await ocrApi.detectWindow(selectedWindowHwnd, ocrLanguage)
      } else {
        result = await ocrApi.detectDialogue(selectedMonitorId, ocrLanguage)
      }

      // 성공 시 쿨다운 타이머 갱신
      if (result.text) {
        lastOcrSuccessTime = Date.now()
      }

      set({
        detectedText: result.text,
        detectedConfidence: result.confidence,
      })
      return result
    } catch (error) {
      console.error('Failed to detect dialogue:', error)
      set({ ocrError: 'Failed to detect dialogue' })
      return null
    } finally {
      isOcrInProgress = false
    }
  },

  // OCR: 화면 캡처 (직접 이미지 URL 사용)
  captureScreen: async () => {
    const { selectedMonitorId } = get()
    try {
      set({ ocrError: null })
      // 직접 이미지 URL 사용 (base64 대신)
      const imageUrl = ocrApi.getCaptureImageUrl(selectedMonitorId)
      set({ capturedImageUrl: imageUrl, capturedImage: null })
    } catch (error) {
      console.error('Failed to capture screen:', error)
      set({ ocrError: 'Failed to capture screen' })
    }
  },

  // OCR: 대사 영역 캡처 (직접 이미지 URL 사용)
  captureDialogue: async () => {
    const { selectedMonitorId } = get()
    try {
      set({ ocrError: null })
      // 직접 이미지 URL 사용 (base64 대신)
      const imageUrl = ocrApi.getDialogueImageUrl(selectedMonitorId)
      set({ capturedImageUrl: imageUrl, capturedImage: null })
    } catch (error) {
      console.error('Failed to capture dialogue region:', error)
      set({ ocrError: 'Failed to capture dialogue region' })
    }
  },

  // OCR: 윈도우 캡처
  captureWindow: () => {
    const { selectedWindowHwnd } = get()
    if (!selectedWindowHwnd) {
      set({ ocrError: 'No window selected' })
      return
    }
    const imageUrl = ocrApi.getWindowImageUrl(selectedWindowHwnd)
    set({ capturedImageUrl: imageUrl, capturedImage: null, ocrError: null })
  },

  // OCR: 모니터링 시작
  startMonitoring: () => {
    const { selectedWindowHwnd, captureMode, ocrLanguage } = get()

    if (monitoringInterval || sseStream) return // 이미 실행 중

    // 상태 초기화
    isOcrInProgress = false
    lastOcrSuccessTime = 0
    lastMatchedText = ''

    set({ isMonitoring: true, ocrError: null })

    // 윈도우 모드 + SSE 사용 시 스트리밍
    if (USE_SSE_STREAMING && captureMode === 'window' && selectedWindowHwnd) {
      console.log('[OCR] Starting SSE stream for window:', selectedWindowHwnd)

      sseStream = createDialogueStream(selectedWindowHwnd, ocrLanguage, {
        pollInterval: 0.3,
        stabilityThreshold: 3,
        onDialogue: (event) => {
          if (event.text && event.is_new) {
            console.log('[SSE] New dialogue:', event.text)
            set({
              detectedText: event.text,
              detectedConfidence: event.confidence ?? 0,
            })
            // OCR 결과를 에피소드 대사와 매칭
            get().matchOcrResult()
          }
        },
        onError: (event) => {
          console.error('[SSE] Error:', event.message)
          // 연결 오류 시 폴링으로 폴백
          if (event.type === 'error' && !monitoringInterval) {
            console.log('[SSE] Falling back to polling')
            sseStream?.close()
            sseStream = null
            monitoringInterval = setInterval(() => {
              get().detectOnce()
            }, OCR_POLL_INTERVAL_MS)
          }
        },
        onStatus: (event) => {
          console.log('[SSE] Status:', event.type)
        },
      })
      return
    }

    // 폴링 모드
    get().detectOnce()
    monitoringInterval = setInterval(() => {
      get().detectOnce()
    }, OCR_POLL_INTERVAL_MS)
  },

  // OCR: 모니터링 중지
  stopMonitoring: () => {
    // SSE 스트림 종료
    if (sseStream) {
      console.log('[OCR] Closing SSE stream')
      sseStream.close()
      sseStream = null
    }
    // 폴링 인터벌 종료
    if (monitoringInterval) {
      clearInterval(monitoringInterval)
      monitoringInterval = null
    }
    if (matchDebounceTimer) {
      clearTimeout(matchDebounceTimer)
      matchDebounceTimer = null
    }
    // 상태 초기화
    isOcrInProgress = false
    lastOcrSuccessTime = 0
    set({ isMonitoring: false })
  },

  // OCR: 결과 초기화
  clearOcrResult: () => {
    set({
      detectedText: null,
      detectedConfidence: 0,
      capturedImage: null,
      capturedImageUrl: null,
      ocrError: null,
    })
  },

  // 사용자 지정 영역 설정
  setCustomRegion: async (region: BoundingBox) => {
    try {
      await ocrApi.setCustomRegion(region)
      set({ customRegion: region, ocrError: null })
    } catch (error) {
      console.error('Failed to set custom region:', error)
      set({ ocrError: 'Failed to set custom region' })
    }
  },

  // 사용자 지정 영역 사용 토글
  setUseCustomRegion: (use: boolean) => {
    set({ useCustomRegion: use })
  },

  // 사용자 지정 영역에서 텍스트 감지
  detectCustomRegion: async () => {
    const { ocrLanguage, customRegion } = get()
    if (!customRegion) {
      set({ ocrError: 'Custom region not set' })
      return null
    }
    try {
      set({ ocrError: null })
      const result = await ocrApi.detectCustomRegion(ocrLanguage)
      set({
        detectedText: result.text,
        detectedConfidence: result.confidence,
      })
      return result
    } catch (error) {
      console.error('Failed to detect custom region:', error)
      set({ ocrError: 'Failed to detect custom region' })
      return null
    }
  },

  // 사용자 지정 영역 캡처
  captureCustomRegion: () => {
    const { customRegion } = get()
    if (!customRegion) {
      set({ ocrError: 'Custom region not set' })
      return
    }
    const imageUrl = ocrApi.getCustomRegionImageUrl(customRegion)
    set({ capturedImageUrl: imageUrl, capturedImage: null, ocrError: null })
  },

  // 실시간 더빙 모드 토글
  toggleDubbingMode: () => {
    const { isDubbingMode, isMonitoring, stopMonitoring } = get()
    if (isDubbingMode && isMonitoring) {
      stopMonitoring()
    }
    set({
      isDubbingMode: !isDubbingMode,
      matchedDialogue: null,
      matchedIndex: -1,
      matchSimilarity: 0,
    })
  },

  // 실시간 더빙 모드 설정
  setDubbingMode: (enabled: boolean) => {
    const { isMonitoring, stopMonitoring } = get()
    if (!enabled && isMonitoring) {
      stopMonitoring()
    }
    set({
      isDubbingMode: enabled,
      matchedDialogue: null,
      matchedIndex: -1,
      matchSimilarity: 0,
    })
  },

  // OCR 결과를 에피소드 대사와 매칭 (디바운스 + 중복 방지)
  matchOcrResult: async () => {
    const { selectedEpisodeId, detectedText, isMonitoring } = get()

    if (!selectedEpisodeId) {
      set({ ocrError: '에피소드를 먼저 선택하세요' })
      return null
    }

    if (!detectedText) {
      return null
    }

    // 중복 텍스트 스킵 (이미 매칭한 텍스트)
    if (detectedText === lastMatchedText) {
      console.log('[Match] Skipping - same text already matched')
      return null
    }

    // 모니터링 중이면 디바운스 적용
    if (isMonitoring) {
      return new Promise((resolve) => {
        if (matchDebounceTimer) {
          clearTimeout(matchDebounceTimer)
        }

        matchDebounceTimer = setTimeout(async () => {
          const result = await performMatch()
          resolve(result)
        }, MATCH_DEBOUNCE_MS)
      })
    }

    // 수동 실행은 즉시 매칭
    return performMatch()

    async function performMatch() {
      const state = get()
      if (!state.detectedText || !state.selectedEpisodeId) return null

      // 이미 매칭 중이면 스킵
      if (state.isMatching) {
        console.log('[Match] Skipping - already matching')
        return null
      }

      set({ isMatching: true })

      try {
        const result = await ocrApi.matchDialogue(state.selectedEpisodeId, state.detectedText)

        if (result.matched && result.dialogue) {
          lastMatchedText = state.detectedText  // 매칭 성공한 텍스트 저장

          // 이전 매칭 대사와 다른 경우 재생 중단 후 새 대사 재생
          const { autoPlayOnMatch, playDialogue, stopPlayback, matchedDialogue: prevMatched, isPlaying } = get()
          const isNewDialogue = !prevMatched || prevMatched.id !== result.dialogue.id

          set({
            matchedDialogue: result.dialogue,
            matchedIndex: result.index,
            matchSimilarity: result.similarity,
            isMatching: false,
          })

          // 자동 재생 (새 대사이면 현재 재생 중단 후 재생)
          if (autoPlayOnMatch && isNewDialogue) {
            if (isPlaying) {
              stopPlayback()
            }
            playDialogue(result.dialogue)
          }
        } else {
          set({
            matchedDialogue: null,
            matchedIndex: -1,
            matchSimilarity: 0,
            isMatching: false,
          })
        }

        return result
      } catch (error) {
        console.error('Failed to match dialogue:', error)
        set({
          ocrError: 'Failed to match dialogue',
          isMatching: false,
        })
        return null
      }
    }
  },

  // 매칭 결과 초기화
  clearMatch: () => {
    set({
      matchedDialogue: null,
      matchedIndex: -1,
      matchSimilarity: 0,
    })
  },

  // 캡처 미리보기 토글
  toggleCapturePreview: () => {
    set((state) => ({ showCapturePreview: !state.showCapturePreview }))
  },

  // 더빙 준비 시작
  prepareForDubbing: async () => {
    const { selectedGroupId, loadGroupCharacters, loadWindows } = get()

    if (!selectedGroupId) {
      set({ ocrError: '스토리 그룹을 먼저 선택하세요' })
      return
    }

    // 윈도우 목록 새로고침 (병렬 실행)
    loadWindows()
    await loadGroupCharacters(selectedGroupId)
    set({ isPrepared: true })
  },

  // 준비 취소
  cancelPrepare: () => {
    set({
      isPrepared: false,
      groupCharacters: [],
      episodeCharacters: [],
      speakerVoiceMap: {},
    })
  },

  // 그룹 캐릭터 로드
  loadGroupCharacters: async (groupId: string) => {
    set({ isLoadingCharacters: true })
    try {
      const data = await storiesApi.listGroupCharacters(groupId)
      set({
        groupCharacters: data.characters,
        isLoadingCharacters: false,
      })
    } catch (error) {
      console.error('Failed to load group characters:', error)
      set({
        groupCharacters: [],
        isLoadingCharacters: false,
        ocrError: 'Failed to load group characters',
      })
    }
  },

  // 에피소드 캐릭터 로드 (speaker_name 기준)
  loadEpisodeCharacters: async (episodeId: string) => {
    set({ isLoadingEpisodeCharacters: true })
    try {
      const data = await episodesApi.getEpisodeCharacters(episodeId)
      set({
        episodeCharacters: data.characters,
        isLoadingEpisodeCharacters: false,
      })
    } catch (error) {
      console.error('Failed to load episode characters:', error)
      set({
        episodeCharacters: [],
        isLoadingEpisodeCharacters: false,
      })
    }
  },

  // 화자별 음성 설정 (NPC 매핑 저장 포함)
  setSpeakerVoice: (speakerId: string, voiceId: string | null) => {
    set((state) => {
      if (voiceId === null) {
        // null이면 매핑 제거
        const { [speakerId]: _, ...rest } = state.speakerVoiceMap
        return { speakerVoiceMap: rest }
      }
      return {
        speakerVoiceMap: {
          ...state.speakerVoiceMap,
          [speakerId]: voiceId,
        },
      }
    })
    // NPC 매핑 저장
    persistCurrentState(get)
  },

  // 화자별 음성 매핑 제거
  clearSpeakerVoice: (speakerId: string) => {
    set((state) => {
      const { [speakerId]: _, ...rest } = state.speakerVoiceMap
      return { speakerVoiceMap: rest }
    })
  },

  // 나레이터 캐릭터 설정
  setNarratorCharId: (charId: string | null) => {
    set({ narratorCharId: charId })
    persistCurrentState(get)
  },

  // 음성 캐릭터 목록 로드
  loadVoiceCharacters: async () => {
    set({ isLoadingVoiceCharacters: true })
    try {
      const data = await voiceApi.listCharacters()
      // 음성 파일 개수로 정렬 (내림차순)
      const sorted = data.characters.sort((a, b) => b.file_count - a.file_count)
      set({
        voiceCharacters: sorted,
        isLoadingVoiceCharacters: false,
      })
    } catch (error) {
      console.error('Failed to load voice characters:', error)
      set({ isLoadingVoiceCharacters: false })
    }
  },

  // 자동 재생 토글
  toggleAutoPlay: () => {
    set((state) => ({ autoPlayOnMatch: !state.autoPlayOnMatch }))
    setTimeout(() => persistCurrentState(get), 0)  // state 업데이트 후 저장
  },

  // 더빙 시작
  startDubbing: () => {
    const { selectedWindowHwnd, startMonitoring } = get()

    if (!selectedWindowHwnd) {
      set({ ocrError: '캡처할 윈도우를 선택하세요' })
      return
    }

    // 윈도우 캡처 모드로 설정 후 더빙 시작
    set({ isDubbingMode: true, captureMode: 'window' })
    startMonitoring()
  },

  // 더빙 중지
  stopDubbing: () => {
    const { stopMonitoring, stopPlayback } = get()
    stopMonitoring()
    stopPlayback()
    set({
      isDubbingMode: false,
      matchedDialogue: null,
      matchedIndex: -1,
      matchSimilarity: 0,
    })
  },

  // === 음성 모델 학습 ===

  // 학습 상태 로드
  loadTrainingStatus: async () => {
    try {
      const status = await trainingApi.getStatus()
      set({
        isTrainingActive: status.is_training,
        currentTrainingJob: status.current_job,
        trainingError: null,
      })
    } catch (error) {
      console.error('Failed to load training status:', error)
      set({ trainingError: '준비 상태 로드 실패' })
    }
  },

  // 학습된 모델 목록 로드
  loadTrainedModels: async () => {
    try {
      const data = await trainingApi.listModels()
      const charIds = new Set(data.models.map(m => m.char_id))
      set({
        trainedModels: data.models,
        trainedCharIds: charIds,
        trainingError: null,
      })
    } catch (error) {
      console.error('Failed to load trained models:', error)
    }
  },

  // 일괄 학습 시작
  startBatchTraining: async (charIds?: string[]) => {
    console.log('[Training] startBatchTraining 호출, charIds:', charIds)
    try {
      set({ trainingError: null })

      // SSE 먼저 연결 (이벤트를 놓치지 않도록)
      console.log('[Training] SSE 먼저 연결')
      get().subscribeToTrainingProgress()

      // 약간의 딜레이 후 API 호출 (SSE 연결 완료 대기)
      await new Promise(resolve => setTimeout(resolve, 100))

      console.log('[Training] API 호출 시작')
      const data = await trainingApi.startBatchTraining(charIds)
      console.log('[Training] API 응답:', data)

      if (data.jobs.length > 0) {
        console.log('[Training] jobs 수:', data.jobs.length)
        set({
          trainingQueue: data.jobs,
          isTrainingActive: true,
        })
      } else {
        console.log('[Training] jobs가 비어있음')
        // jobs가 없으면 SSE 연결 해제
        get().unsubscribeFromTrainingProgress()
      }
    } catch (error) {
      console.error('[Training] 준비 시작 실패:', error)
      set({ trainingError: '준비 시작 실패' })
      // 오류 시 SSE 연결 해제
      get().unsubscribeFromTrainingProgress()
    }
  },

  // 학습 취소
  cancelTraining: async (jobId: string) => {
    try {
      await trainingApi.cancelTraining(jobId)
      // 현재 작업이 취소된 경우 상태 업데이트
      const { currentTrainingJob } = get()
      if (currentTrainingJob?.job_id === jobId) {
        set({ currentTrainingJob: null, isTrainingActive: false })
      }
    } catch (error) {
      console.error('Failed to cancel training:', error)
      set({ trainingError: '준비 취소 실패' })
    }
  },

  // 모든 학습 모델 삭제
  clearAllTrainedModels: async () => {
    try {
      const data = await trainingApi.deleteAllModels()
      console.log('[Training] 모델 초기화:', data.deleted_count, '개 삭제')
      // 상태 초기화
      set({
        trainedModels: [],
        trainedCharIds: new Set<string>(),
        trainingError: null,
      })
    } catch (error) {
      console.error('Failed to clear trained models:', error)
      set({ trainingError: '준비 데이터 삭제 실패' })
    }
  },

  // 학습 진행 상황 구독
  subscribeToTrainingProgress: () => {
    if (trainingStream) {
      console.log('[Training] 이미 SSE 연결됨, 건너뛰기')
      return  // 이미 구독 중
    }

    console.log('[Training] SSE 구독 시작')
    trainingStream = createTrainingStream({
      onProgress: (job) => {
        console.log('[Training] 진행:', job.char_name, job.status, `${(job.progress * 100).toFixed(1)}%`, job.message)
        set({
          currentTrainingJob: job,
          isTrainingActive: true,
        })
      },
      onComplete: (job) => {
        console.log('[Training] 완료:', job.char_name, job.status)
        // 학습 완료 시 모델 목록 새로고침
        get().loadTrainedModels()

        // 큐에서 완료된 작업 제거
        set((state) => ({
          trainingQueue: state.trainingQueue.filter(j => j.job_id !== job.job_id),
          currentTrainingJob: null,
          isTrainingActive: state.trainingQueue.length > 1,  // 다음 작업 있으면 활성 유지
        }))
      },
      onStatus: (status) => {
        console.log('[Training] 상태:', status)
        set({
          isTrainingActive: status.is_training,
          currentTrainingJob: status.current_job,
        })
      },
      onError: (error) => {
        console.error('[Training] SSE 오류:', error)
        set({ trainingError: error })
      },
    })
  },

  // 학습 진행 상황 구독 해제
  unsubscribeFromTrainingProgress: () => {
    console.log('[Training] SSE 구독 해제')
    if (trainingStream) {
      trainingStream.close()
      trainingStream = null
    }
  },

  // 캐릭터 학습 완료 여부 확인
  isCharacterTrained: (charId: string) => {
    return get().trainedCharIds.has(charId)
  },

  // === 렌더링 ===

  // 렌더링 상태 로드
  loadRenderStatus: async () => {
    try {
      const status = await renderApi.getStatus()
      set({
        isRendering: status.is_rendering,
        renderProgress: status.current_progress,
        cachedEpisodes: status.cached_episodes,
        renderError: null,
      })
    } catch (error) {
      console.error('Failed to load render status:', error)
      set({ renderError: '렌더링 상태 로드 실패' })
    }
  },

  // 렌더링 시작
  startRender: async (episodeId: string, force: boolean = false) => {
    const { defaultCharId, narratorCharId, speakerVoiceMap, defaultFemaleVoices, defaultMaleVoices } = get()

    // speakerVoiceMap의 특수 값들을 실제 char_id로 해석
    const resolvedVoiceMap: Record<string, string> = {}
    for (const [speakerId, voiceId] of Object.entries(speakerVoiceMap)) {
      if (voiceId === AUTO_VOICE_FEMALE) {
        // 여성 자동 → 기본 여성 음성 중 하나
        if (defaultFemaleVoices.length > 0) {
          const hash = simpleHash(speakerId)
          resolvedVoiceMap[speakerId] = defaultFemaleVoices[hash % defaultFemaleVoices.length]
        }
      } else if (voiceId === AUTO_VOICE_MALE) {
        // 남성 자동 → 기본 남성 음성 중 하나
        if (defaultMaleVoices.length > 0) {
          const hash = simpleHash(speakerId)
          resolvedVoiceMap[speakerId] = defaultMaleVoices[hash % defaultMaleVoices.length]
        }
      } else {
        // 일반 매핑
        resolvedVoiceMap[speakerId] = voiceId
      }
    }

    try {
      set({ renderError: null })
      const progress = await renderApi.startRender(
        episodeId,
        'ko',
        defaultCharId || undefined,
        narratorCharId || undefined,
        Object.keys(resolvedVoiceMap).length > 0 ? resolvedVoiceMap : undefined,
        force
      )

      set({
        isRendering: progress.status === 'rendering',
        renderProgress: progress,
      })

      // 렌더링 진행 중이면 구독 시작
      if (progress.status === 'rendering') {
        get().subscribeToRenderProgress(episodeId)
      }
    } catch (error) {
      console.error('Failed to start render:', error)
      set({ renderError: '렌더링 시작 실패' })
    }
  },

  // 렌더링 취소
  cancelRender: async () => {
    const { renderProgress } = get()
    if (!renderProgress) return

    try {
      await renderApi.cancelRender(renderProgress.episode_id)
      set({
        isRendering: false,
        renderProgress: null,
      })
      get().unsubscribeFromRenderProgress()
    } catch (error) {
      console.error('Failed to cancel render:', error)
      set({ renderError: '렌더링 취소 실패' })
    }
  },

  // 렌더링 진행 상황 구독
  subscribeToRenderProgress: (episodeId: string) => {
    if (renderStream) {
      renderStream.close()
    }

    renderStream = createRenderStream(episodeId, {
      onProgress: (progress) => {
        set({
          renderProgress: progress,
          isRendering: progress.status === 'rendering',
        })
      },
      onComplete: (progress) => {
        set({
          renderProgress: progress,
          isRendering: false,
        })
        // 캐시 목록 갱신
        get().loadRenderStatus()
      },
      onError: (error) => {
        console.error('Render stream error:', error)
        set({ renderError: error })
      },
    })
  },

  // 렌더링 진행 상황 구독 해제
  unsubscribeFromRenderProgress: () => {
    if (renderStream) {
      renderStream.close()
      renderStream = null
    }
  },

  // 렌더링된 오디오 URL 반환
  getRenderedAudioUrl: (index: number) => {
    const { selectedEpisodeId, cachedEpisodes } = get()
    if (!selectedEpisodeId) return null

    // 에피소드가 캐시되어 있는지 확인
    const safeId = selectedEpisodeId.replace(/\//g, '_').replace(/\\/g, '_')
    if (!cachedEpisodes.includes(safeId)) return null

    return renderApi.getAudioUrl(selectedEpisodeId, index)
  },

  // 대사가 렌더링되었는지 확인
  isDialogueRendered: (index: number) => {
    const { renderProgress } = get()
    if (!renderProgress) return false
    return index < renderProgress.completed
  },

  // === GPT-SoVITS ===

  // GPT-SoVITS 상태 확인
  checkGptSovitsStatus: async () => {
    try {
      const status = await ttsApi.getGptSovitsStatus()
      set({
        gptSovitsStatus: status,
        gptSovitsError: null,
      })
    } catch (error) {
      console.error('Failed to check GPT-SoVITS status:', error)
      set({
        gptSovitsStatus: null,
        gptSovitsError: 'GPT-SoVITS 상태 확인 실패',
      })
    }
  },

  // GPT-SoVITS 시작
  startGptSovits: async () => {
    set({ isStartingGptSovits: true, gptSovitsError: null })
    try {
      await ttsApi.startGptSovits()
      // 시작 후 상태 갱신
      await get().checkGptSovitsStatus()
    } catch (error: any) {
      console.error('Failed to start GPT-SoVITS:', error)
      const errorMsg = error?.response?.data?.detail || 'GPT-SoVITS 시작 실패'
      set({ gptSovitsError: errorMsg })
    } finally {
      set({ isStartingGptSovits: false })
    }
  },
}))

// 학습 스트림 참조
let trainingStream: { close: () => void } | null = null

// 렌더링 스트림 참조
let renderStream: { close: () => void } | null = null
