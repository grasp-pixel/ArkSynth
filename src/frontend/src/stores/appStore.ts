import { create } from 'zustand'
import {
  episodesApi,
  storiesApi,
  ttsApi,
  ocrApi,
  voiceApi,
  trainingApi,
  renderApi,
  settingsApi,
  healthCheck,
  createDialogueStream,
  createTrainingStream,
  createRenderStream,
  createGroupRenderStream,
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
  type GroupRenderProgress,
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
  dubbingWarning: string | null  // 더빙 모드 경고 (캐시 없음 등)
  showNoCacheWarning: boolean  // 사전 더빙 미완료 경고 표시
  showCapturePreview: boolean  // 캡처 미리보기 표시

  // 더빙 준비 관련
  isPrepared: boolean  // 더빙 준비 완료 여부
  groupCharacters: GroupCharacterInfo[]  // 현재 그룹 캐릭터 목록 (전체 통계용)
  episodeCharacters: GroupCharacterInfo[]  // 현재 에피소드 캐릭터 목록 (음성 매핑용)
  episodeNarrationCount: number  // 현재 에피소드의 나레이션 대사 수
  isLoadingCharacters: boolean  // 캐릭터 로딩 중
  isLoadingEpisodeCharacters: boolean  // 에피소드 캐릭터 로딩 중
  speakerVoiceMap: Record<string, string>  // speaker_id → voice_id 매핑
  narratorCharId: string | null  // 나레이터 캐릭터 ID
  unknownSpeakerCharId: string | null  // 알 수 없는 화자(name-only "???" 등) 캐릭터 ID
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
  continueWithFinetune: boolean  // 준비 완료 후 자동으로 학습 시작

  // 렌더링 관련
  isRendering: boolean  // 렌더링 진행 중
  renderProgress: RenderProgress | null  // 현재 렌더링 진행률
  cachedEpisodes: string[]  // 완료된 에피소드 목록
  partialEpisodes: string[]  // 부분 완료된 에피소드 목록
  renderError: string | null  // 렌더링 오류

  // 그룹 렌더링 관련
  isGroupRendering: boolean  // 그룹 렌더링 진행 중
  groupRenderProgress: GroupRenderProgress | null  // 그룹 렌더링 진행률
  groupRenderError: string | null  // 그룹 렌더링 오류

  // GPT-SoVITS 관련
  gptSovitsStatus: { installed: boolean; api_running: boolean; synthesizing?: boolean; force_zero_shot?: boolean } | null
  isStartingGptSovits: boolean
  gptSovitsError: string | null

  // TTS 엔진 설정
  defaultTtsEngine: 'gpt_sovits'

  // GPU 세마포어 (OCR/TTS 동시 실행 제한)
  gpuSemaphoreEnabled: boolean

  // TTS 추론 파라미터
  ttsParams: { speed_factor: number; top_k: number; top_p: number; temperature: number }

  // 볼륨 설정
  volume: number  // 재생 볼륨 (0.0~1.0)
  isMuted: boolean

  // 패널 접기 상태
  isLeftPanelCollapsed: boolean
  isRightPanelCollapsed: boolean

  // 전체 새로고침
  isRefreshingAll: boolean
  refreshAll: () => Promise<void>

  // 액션
  checkBackendStatus: () => Promise<void>
  loadCategories: () => Promise<void>
  selectCategory: (categoryId: string) => Promise<void>
  selectStoryGroup: (groupId: string) => Promise<void>
  loadEpisodes: () => Promise<void>
  selectEpisode: (episodeId: string) => Promise<void>
  clearEpisode: () => void
  goHome: () => void
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
  resolveDialogueVoice: (dialogue: { speaker_id?: string | null, speaker_name?: string | null }) => string | null

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
  setSpeakerVoice: (speakerId: string, voiceId: string | null) => Promise<void>
  clearSpeakerVoice: (speakerId: string) => Promise<void>
  setNarratorCharId: (charId: string | null) => void
  setUnknownSpeakerCharId: (charId: string | null) => void
  loadVoiceCharacters: () => Promise<void>
  loadVoiceMappings: () => Promise<void>  // 백엔드에서 음성 매핑 로드
  toggleAutoPlay: () => void
  startDubbing: () => void
  confirmStartDubbing: () => void  // showNoCacheWarning 확인 후 더빙 시작
  dismissNoCacheWarning: () => void
  stopDubbing: () => void

  // 음성 모델 학습
  loadTrainingStatus: () => Promise<void>
  loadTrainedModels: () => Promise<void>
  startBatchTraining: (charIds?: string[], mode?: 'prepare' | 'finetune') => Promise<void>
  startFullBatchTraining: (charIds?: string[]) => Promise<void>  // 준비 → 학습 연속 진행
  cancelTraining: (jobId: string) => Promise<void>
  clearAllTrainedModels: () => Promise<void>
  deleteModel: (charId: string) => Promise<void>
  subscribeToTrainingProgress: () => void
  unsubscribeFromTrainingProgress: () => void
  isCharacterTrained: (charId: string) => boolean
  getModelType: (charId: string) => 'none' | 'prepared' | 'finetuned'
  canFinetune: (charId: string) => boolean
  getSegmentCount: (charId: string) => number

  // 렌더링
  loadRenderStatus: () => Promise<void>
  startRender: (episodeId: string, force?: boolean) => Promise<void>
  cancelRender: () => Promise<void>
  deleteRenderCache: (episodeId: string) => Promise<void>
  subscribeToRenderProgress: (episodeId: string) => void
  unsubscribeFromRenderProgress: () => void
  getRenderedAudioUrl: (index: number) => string | null
  isDialogueRendered: (index: number) => boolean

  // 그룹 렌더링
  startGroupRender: (groupId: string, force?: boolean) => Promise<void>
  cancelGroupRender: () => Promise<void>
  subscribeToGroupRenderProgress: (groupId: string) => void
  unsubscribeFromGroupRenderProgress: () => void

  // GPT-SoVITS
  checkGptSovitsStatus: () => Promise<void>
  startGptSovits: () => Promise<void>

  // TTS 엔진 설정
  loadTtsEngineSetting: () => Promise<void>

  // TTS 추론 파라미터
  loadTtsParams: () => Promise<void>
  updateTtsParams: (params: Partial<{ speed_factor: number; top_k: number; top_p: number; temperature: number }>) => Promise<void>

  // GPU 세마포어
  loadGpuSemaphoreStatus: () => Promise<void>
  toggleGpuSemaphore: () => Promise<void>

  // 볼륨 설정
  setVolume: (volume: number) => void
  toggleMute: () => void

  // 패널 접기
  toggleLeftPanel: () => void
  toggleRightPanel: () => void
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
  unknownSpeakerCharId: string | null
  autoPlayOnMatch: boolean
  npcVoiceMap: Record<string, string>  // NPC 음성 매핑 (char_id → voice_id)
  // 볼륨 설정
  volume?: number
  isMuted?: boolean
  // 패널 접기 상태
  isLeftPanelCollapsed?: boolean
  isRightPanelCollapsed?: boolean
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
    unknownSpeakerCharId: state.unknownSpeakerCharId,
    autoPlayOnMatch: state.autoPlayOnMatch,
    npcVoiceMap: state.speakerVoiceMap,  // NPC 음성 매핑 저장
    volume: state.volume,
    isMuted: state.isMuted,
    isLeftPanelCollapsed: state.isLeftPanelCollapsed,
    isRightPanelCollapsed: state.isRightPanelCollapsed,
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

// 이름이 '???' 같은 미스터리 이름인지 확인 (이름 기반 매핑 상속에서 제외)
// "바운티 헌터?", "킨베에?" 등 식별 가능한 이름은 미스터리가 아님
export const isMysteryName = (name: string): boolean => {
  if (!name) return true
  const trimmed = name.trim()
  return [...trimmed].every(c => c === '?')
}

// AUTO_VOICE 특수 값을 실제 char_id로 해석하는 공통 함수
// getSpeakerVoice와 resolveSpeakerMappings에서 동일 로직 사용
const resolveAutoVoice = (
  voiceId: string,
  speakerId: string,
  defaultFemaleVoices: string[],
  defaultMaleVoices: string[],
): string | null => {
  if (voiceId === AUTO_VOICE_FEMALE) {
    return defaultFemaleVoices.length > 0
      ? defaultFemaleVoices[simpleHash(speakerId) % defaultFemaleVoices.length]
      : null
  } else if (voiceId === AUTO_VOICE_MALE) {
    return defaultMaleVoices.length > 0
      ? defaultMaleVoices[simpleHash(speakerId) % defaultMaleVoices.length]
      : null
  }
  return voiceId
}

// speakerVoiceMap 항목을 해석하여 resolvedVoiceMap을 구성하는 공통 함수
// startRender, startGroupRender에서 동일한 로직을 사용하여 불일치 방지
export const resolveSpeakerMappings = (
  speakerVoiceMap: Record<string, string>,
  defaultFemaleVoices: string[],
  defaultMaleVoices: string[],
  unknownSpeakerCharId: string | null,
): Record<string, string> => {
  const resolved: Record<string, string> = {}

  for (const [speakerId, voiceId] of Object.entries(speakerVoiceMap)) {
    // unknownSpeakerCharId가 설정된 경우, 미스터리 키는 건너뜀 (unknownSpeakerCharId로 처리)
    if (unknownSpeakerCharId) {
      const isMysteryKey = speakerId.startsWith('name:')
        ? isMysteryName(speakerId.slice(5))
        : isMysteryName(speakerId)
      if (isMysteryKey) continue
    }

    const resolvedId = resolveAutoVoice(voiceId, speakerId, defaultFemaleVoices, defaultMaleVoices)
    if (resolvedId) {
      resolved[speakerId] = resolvedId
    }
  }

  // 알 수 없는 화자 매핑 (미스터리 키 강제 적용)
  if (unknownSpeakerCharId) {
    const mysteryKeys = ['?', '??', '???', '????', '?????', 'name:???', 'name:????', 'name:?????']
    for (const key of mysteryKeys) {
      resolved[key] = unknownSpeakerCharId
    }
  }

  return resolved
}

// 오디오 재생 관리
let currentAudio: HTMLAudioElement | null = null
let lastPlayStartTime = 0  // 마지막 재생 시작 시간 (중복 방지)
let lastPlayedDialogueId: string | null = null  // 마지막 재생한 대사 ID
let isPlayStarting = false  // 재생 시작 중 플래그 (중복 요청 방지)

// 실시간 TTS 합성 및 재생 헬퍼 함수
async function synthesizeAndPlayDialogue(
  text: string,
  charId: string,
  set: (state: Partial<AppState>) => void,
  get: () => AppState
) {
  try {
    const { volume, isMuted } = get()

    console.log('[playDialogue] GPT-SoVITS 합성:', charId, text.substring(0, 30))
    const audioBlob = await ttsApi.synthesize(text, charId)
    const audioUrl = URL.createObjectURL(audioBlob)

    currentAudio = new Audio(audioUrl)
    currentAudio.volume = isMuted ? 0 : volume  // 볼륨 설정
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
  dubbingWarning: null,
  showNoCacheWarning: false,
  showCapturePreview: false,

  // 더빙 준비 초기 상태
  isPrepared: false,
  groupCharacters: [],
  episodeCharacters: [],
  episodeNarrationCount: 0,
  isLoadingCharacters: false,
  isLoadingEpisodeCharacters: false,
  speakerVoiceMap: persistedState.npcVoiceMap ?? {},  // 저장된 NPC 매핑 복원
  narratorCharId: persistedState.narratorCharId ?? null,
  unknownSpeakerCharId: persistedState.unknownSpeakerCharId ?? null,
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
  continueWithFinetune: false,

  // 렌더링 초기 상태
  isRendering: false,
  renderProgress: null,
  cachedEpisodes: [],
  partialEpisodes: [],
  renderError: null,

  // 그룹 렌더링 초기 상태
  isGroupRendering: false,
  groupRenderProgress: null,
  groupRenderError: null,

  // GPT-SoVITS 초기 상태
  gptSovitsStatus: null,
  isStartingGptSovits: false,
  gptSovitsError: null,

  // TTS 엔진 설정 초기 상태
  defaultTtsEngine: 'gpt_sovits',

  // TTS 추론 파라미터 초기 상태
  ttsParams: { speed_factor: 1.0, top_k: 12, top_p: 1.0, temperature: 0.9 },

  // GPU 세마포어 초기 상태 (기본 활성화)
  gpuSemaphoreEnabled: true,

  // 볼륨 설정 초기 상태 (localStorage에서 복원)
  volume: persistedState.volume ?? 1.0,
  isMuted: persistedState.isMuted ?? false,

  // 패널 접기 초기 상태 (localStorage에서 복원)
  isLeftPanelCollapsed: persistedState.isLeftPanelCollapsed ?? false,
  isRightPanelCollapsed: persistedState.isRightPanelCollapsed ?? false,

  // 전체 새로고침
  isRefreshingAll: false,
  refreshAll: async () => {
    set({ isRefreshingAll: true })
    try {
      await Promise.all([
        settingsApi.refreshAll(),
        ttsApi.reinitGptSovits().catch(() => {}),
      ])
      // 캐릭터/매핑 데이터도 새로고침
      const { selectedGroupId, loadVoiceCharacters, loadTrainedModels, loadGroupCharacters } = get()
      await Promise.all([
        loadVoiceCharacters(),
        loadTrainedModels(),
        selectedGroupId ? loadGroupCharacters(selectedGroupId) : Promise.resolve(),
      ])
    } catch (err) {
      console.error('전체 새로고침 실패:', err)
    } finally {
      set({ isRefreshingAll: false })
    }
  },

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

    // 다른 그룹 선택 시 더빙/준비 상태 취소 + 에피소드 선택 초기화
    if (prevGroupId !== groupId) {
      if (isDubbingMode) stopDubbing()
      if (isPrepared) cancelPrepare()
      // 에피소드 선택 초기화 → GroupSetupPanel 표시되도록
      set({ selectedEpisodeId: null, selectedEpisode: null })
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

  goHome: () => {
    const { isPrepared, isDubbingMode, stopDubbing, cancelPrepare } = get()
    if (isDubbingMode) stopDubbing()
    if (isPrepared) cancelPrepare()
    set({
      selectedGroupId: null,
      groupEpisodes: [],
      selectedEpisodeId: null,
      selectedEpisode: null,
    })
    persistCurrentState(get)
  },

  // 대사 재생 (캐시 우선, 렌더링 중이면 캐시만 사용)
  playDialogue: async (dialogue: DialogueInfo) => {
    const {
      selectedEpisodeId, cachedEpisodes, renderProgress,
      currentDialogue, isPlaying,
      isRendering,
    } = get()

    // === 중복 재생 방지 ===
    // 1. 재생 시작 중이면 스킵 (비동기 처리 중 중복 호출 방지)
    if (isPlayStarting) {
      console.log('[playDialogue] 중복 스킵 - 재생 시작 중')
      return
    }

    // 2. 이미 같은 대사를 재생 중이면 스킵
    if (isPlaying && currentDialogue?.id === dialogue.id) {
      console.log('[playDialogue] 중복 스킵 - 이미 재생 중:', dialogue.id)
      return
    }

    // 3. 마지막 재생 시작으로부터 0.5초 이내면 스킵 (빠른 연속 호출 방지)
    const now = Date.now()
    if (now - lastPlayStartTime < 500) {
      console.log('[playDialogue] 중복 스킵 - 0.5초 이내 연속 호출')
      return
    }

    // 즉시 플래그 설정 (비동기 처리 전)
    isPlayStarting = true
    lastPlayStartTime = now
    lastPlayedDialogueId = dialogue.id

    // 캐릭터 ID 결정 (resolveDialogueVoice 통합 함수 사용)
    const { resolveDialogueVoice } = get()
    const charIdToUse = resolveDialogueVoice(dialogue)

    console.log('[playDialogue] 대사 정보:', {
      speaker_id: dialogue.speaker_id,
      speaker_name: dialogue.speaker_name,
      text: dialogue.text.substring(0, 30) + '...',
      resolvedVoice: charIdToUse,
    })

    // 기존 재생 중지
    if (currentAudio) {
      currentAudio.pause()
      currentAudio = null
    }

    // char_id 없으면 재생 불가
    if (!charIdToUse) {
      console.warn('[playDialogue] 캐릭터 ID 없음 - 재생 불가')
      isPlayStarting = false
      return
    }

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
    console.log('[playDialogue] 캐시 확인:', { dialogueIndex, isCached, isRendered, completed: renderProgress?.completed, isRendering })

    // === 렌더링 중이면 캐시만 사용 (실시간 합성 차단) ===
    if (isRendering) {
      if (!isRendered) {
        // 아직 렌더링되지 않은 대사 - 재생 불가
        console.log('[playDialogue] 렌더링 중 - 아직 완료되지 않은 대사, 스킵:', dialogueIndex)
        isPlayStarting = false
        return
      }
    }

    set({ isPlaying: true, currentDialogue: dialogue, dubbingWarning: null })

    if ((isCached || isRendered) && selectedEpisodeId && dialogueIndex >= 0) {
      const cachedAudioUrl = renderApi.getAudioUrl(selectedEpisodeId, dialogueIndex)
      console.log('[playDialogue] 캐시 재생:', dialogueIndex, cachedAudioUrl)

      try {
        const { volume, isMuted } = get()
        currentAudio = new Audio(cachedAudioUrl)
        currentAudio.volume = isMuted ? 0 : volume  // 볼륨 설정

        // 성공 시 핸들러
        currentAudio.onended = () => {
          set({ isPlaying: false, currentDialogue: null })
        }

        // 캐시 재생 실패 시 로깅 (실제 폴백은 catch 블록에서 처리)
        currentAudio.onerror = () => {
          console.warn('[playDialogue] 캐시 재생 실패 (onerror)')
        }

        await currentAudio.play()
        console.log('[playDialogue] 캐시 재생 성공')
        isPlayStarting = false
        return
      } catch (error) {
        console.warn('[playDialogue] 캐시 로드 실패:', error)
        currentAudio = null
        // 더빙 모드 또는 렌더링 중이면 실시간 합성 차단
        const { isDubbingMode: inDubbingMode } = get()
        if (inDubbingMode || isRendering) {
          set({
            isPlaying: false,
            currentDialogue: null,
            dubbingWarning: '사전 더빙이 필요합니다. 먼저 에피소드 더빙을 진행하세요.',
          })
          isPlayStarting = false
          return
        }
        // 테스트 모드: 캐시 실패 시 실시간 합성으로 폴백
        console.log('[playDialogue] 캐시 실패 → 실시간 합성 폴백')
        try {
          await synthesizeAndPlayDialogue(dialogue.text, charIdToUse!, set, get)
        } finally {
          isPlayStarting = false
        }
        return
      }
    }

    // 캐시 URL이 없는 경우 (더빙 모드 또는 렌더링 중이면 차단)
    const { isDubbingMode } = get()
    if (isDubbingMode || isRendering) {
      set({
        isPlaying: false,
        currentDialogue: null,
        dubbingWarning: '사전 더빙이 필요합니다. 먼저 에피소드 더빙을 진행하세요.',
      })
      isPlayStarting = false
      return
    }

    // 실시간 GPT-SoVITS 합성 (테스트 용도 - 더빙 모드가 아닐 때만)
    console.log('[playDialogue] 캐시 없음 → 실시간 합성')
    try {
      await synthesizeAndPlayDialogue(dialogue.text, charIdToUse, set, get)
    } finally {
      isPlayStarting = false
    }
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

  // 화자별 음성 결정 (수동 매핑 우선 → voice_char_id → 성별 기반 기본 음성 자동 분배)
  // 사용자가 명시적으로 설정한 수동 매핑이 최우선, 자동 감지는 폴백
  getSpeakerVoice: (speakerId: string, speakerName?: string): string | null => {
    const { trainedCharIds, speakerVoiceMap, defaultFemaleVoices, defaultMaleVoices, defaultVoices, voiceCharacters, episodeCharacters } = get()

    const { unknownSpeakerCharId } = get()

    // 1. 알 수 없는 화자 체크 (미스터리 이름은 수동 매핑보다 unknownSpeakerCharId 우선)
    if (unknownSpeakerCharId) {
      const isMysteryKey = speakerId.startsWith('name:')
        ? isMysteryName(speakerId.slice(5))
        : isMysteryName(speakerId)
      if (isMysteryKey) return unknownSpeakerCharId
    }

    // 2. 수동 매핑 (사용자가 명시적으로 설정한 매핑)
    let mapping = speakerVoiceMap[speakerId]

    // 2.5. name: 키 이름 기반 상속
    if (!mapping && speakerId.startsWith('name:')) {
      const charName = speakerId.slice(5)
      // 일반 이름 → 같은 이름의 char_id 매핑 상속
      // (예: avg_npc_003="클로어" 매핑 → name:클로어도 동일 음성 사용)
      const matchingChar = episodeCharacters.find(c => c.char_id && c.name === charName)
      if (matchingChar?.char_id) {
        mapping = speakerVoiceMap[matchingChar.char_id]
      }
    }

    if (mapping) {
      const resolved = resolveAutoVoice(mapping, speakerId, defaultFemaleVoices, defaultMaleVoices)
      if (resolved) return resolved
    }

    // 2. episodeCharacters에서 voice_char_id 확인 (별칭 기반 자동 감지)
    // name: 접두사 키인 경우 이름으로 찾기
    let episodeChar
    if (speakerId.startsWith('name:')) {
      const charName = speakerId.slice(5)  // 'name:' 제거
      episodeChar = episodeCharacters.find(c => c.name === charName)
    } else {
      episodeChar = episodeCharacters.find(c => c.char_id === speakerId)
    }
    const voiceCharId = episodeChar?.voice_char_id || speakerId

    // 3. voice_char_id가 음성 파일을 가지고 있으면 사용 (별칭 기반 "올바른" 음성)
    const hasOwnVoice = voiceCharacters.some(v => v.char_id === voiceCharId)
    if (hasOwnVoice) {
      return voiceCharId
    }

    // 4. 학습된 음성 있으면 사용
    if (trainedCharIds.has(voiceCharId)) {
      return voiceCharId
    }

    // 5. 성별 기반 기본 음성 분배
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

  // 대사 하나의 음성을 결정하는 통합 함수 (표시/재생 공통)
  resolveDialogueVoice: (dialogue: { speaker_id?: string | null, speaker_name?: string | null }): string | null => {
    const { getSpeakerVoice, narratorCharId, defaultFemaleVoices, defaultVoices } = get()

    if (dialogue.speaker_id) {
      return getSpeakerVoice(dialogue.speaker_id, dialogue.speaker_name || undefined)
    } else if (dialogue.speaker_name) {
      return getSpeakerVoice(`name:${dialogue.speaker_name}`, dialogue.speaker_name)
    } else {
      // 나레이션
      return narratorCharId || (defaultFemaleVoices.length > 0 ? defaultFemaleVoices[0] : (defaultVoices.length > 0 ? defaultVoices[0] : null))
    }
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
        return null
      }

      set({ isMatching: true })

      try {
        const result = await ocrApi.matchDialogue(state.selectedEpisodeId, state.detectedText)

        if (result.matched && result.dialogue) {
          lastMatchedText = state.detectedText  // 매칭 성공한 텍스트 저장

          // 이전 매칭 대사와 다른 경우 재생 중단 후 새 대사 재생
          const { autoPlayOnMatch, playDialogue, stopPlayback, matchedDialogue: prevMatched, isPlaying } = get()
          // 새 대사인지 확인: 이전 매칭 대사와 다르고, 마지막 재생 대사와도 다름
          const isNewDialogue = (!prevMatched || prevMatched.id !== result.dialogue.id) &&
                                result.dialogue.id !== lastPlayedDialogueId

          set({
            matchedDialogue: result.dialogue,
            matchedIndex: result.index,
            matchSimilarity: result.similarity,
            isMatching: false,
          })

          // 자동 재생 (새 대사이면 현재 재생 중단 후 재생)
          if (autoPlayOnMatch && isNewDialogue) {
            console.log('[Match] 새 대사:', result.dialogue.id)
            if (isPlaying) {
              stopPlayback()
            }
            playDialogue(result.dialogue)
          }
        } else {
          // 매칭 실패 시 기존 결과 유지 (OCR 불안정성 대응)
          // 새 대사로 전환 시에만 결과 교체됨
          set({ isMatching: false })
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
    const { selectedGroupId, loadGroupCharacters, loadWindows, loadVoiceCharacters, loadTrainedModels, loadRenderStatus } = get()

    if (!selectedGroupId) {
      set({ ocrError: '스토리 그룹을 먼저 선택하세요' })
      return
    }

    set({ isLoadingCharacters: true, ocrError: null })

    try {
      // 모든 필수 데이터를 병렬 로드
      await Promise.all([
        loadGroupCharacters(selectedGroupId),
        loadVoiceCharacters(),
        loadTrainedModels(),
        loadRenderStatus(),
      ])
      // 윈도우 목록은 실패해도 무방 (별도)
      loadWindows()
      // 모든 로드가 성공한 후에만 플래그 설정
      set({ isPrepared: true })
    } catch (error) {
      console.error('더빙 준비 실패:', error)
      set({ isPrepared: false, ocrError: '더빙 준비 중 오류가 발생했습니다' })
    }
  },

  // 준비 취소
  cancelPrepare: () => {
    set({
      isPrepared: false,
      groupCharacters: [],
      episodeCharacters: [],
      // speakerVoiceMap은 백엔드에 저장되므로 초기화하지 않음
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
        episodeNarrationCount: data.narration_count ?? 0,
        isLoadingEpisodeCharacters: false,
      })
    } catch (error) {
      console.error('Failed to load episode characters:', error)
      set({
        episodeCharacters: [],
        episodeNarrationCount: 0,
        isLoadingEpisodeCharacters: false,
      })
    }
  },

  // 화자별 음성 설정 (백엔드 자동 저장)
  setSpeakerVoice: async (speakerId: string, voiceId: string | null) => {
    // 1. 로컬 상태 즉시 업데이트
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

    // 2. 백엔드에 저장 (null이 아닌 경우)
    if (voiceId !== null) {
      try {
        await voiceApi.addVoiceMapping(speakerId, voiceId)
        console.log('[setSpeakerVoice] 백엔드 저장 완료:', speakerId, '->', voiceId)
      } catch (error) {
        console.error('[setSpeakerVoice] 백엔드 저장 실패:', error)
        // 실패해도 로컬 상태는 유지 (다음 기회에 재시도 가능)
      }
    } else {
      // null이면 백엔드에서 삭제
      try {
        await voiceApi.removeVoiceMapping(speakerId)
        console.log('[setSpeakerVoice] 백엔드 매핑 삭제:', speakerId)
      } catch (error) {
        // 404는 무시 (이미 없는 매핑)
        if (!(error instanceof Error && error.message.includes('404'))) {
          console.error('[setSpeakerVoice] 백엔드 삭제 실패:', error)
        }
      }
    }

    // localStorage에도 저장 (백업용)
    persistCurrentState(get)
  },

  // 화자별 음성 매핑 제거 (백엔드 동기화)
  clearSpeakerVoice: async (speakerId: string) => {
    set((state) => {
      const { [speakerId]: _, ...rest } = state.speakerVoiceMap
      return { speakerVoiceMap: rest }
    })

    // 백엔드에서도 삭제
    try {
      await voiceApi.removeVoiceMapping(speakerId)
      console.log('[clearSpeakerVoice] 백엔드 매핑 삭제:', speakerId)
    } catch (error) {
      // 404는 무시
      if (!(error instanceof Error && error.message.includes('404'))) {
        console.error('[clearSpeakerVoice] 백엔드 삭제 실패:', error)
      }
    }
  },

  // 나레이터 캐릭터 설정
  setNarratorCharId: (charId: string | null) => {
    set({ narratorCharId: charId })
    persistCurrentState(get)
  },

  // 알 수 없는 화자 캐릭터 설정 (name-only "???" 등)
  setUnknownSpeakerCharId: (charId: string | null) => {
    set({ unknownSpeakerCharId: charId })
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

  // 백엔드에서 음성 매핑 로드 (앱 시작 시 호출)
  loadVoiceMappings: async () => {
    try {
      const data = await voiceApi.listVoiceMappings()
      const backendMappings = data.mappings || {}

      // 백엔드 매핑을 speakerVoiceMap에 병합 (백엔드 우선)
      set((state) => ({
        speakerVoiceMap: {
          ...state.speakerVoiceMap,
          ...backendMappings,
        },
      }))

      console.log('[loadVoiceMappings] 백엔드 매핑 로드 완료:', Object.keys(backendMappings).length, '개')
    } catch (error) {
      console.error('[loadVoiceMappings] 백엔드 매핑 로드 실패:', error)
      // 실패해도 localStorage 매핑은 유지
    }
  },

  // 자동 재생 토글
  toggleAutoPlay: () => {
    set((state) => ({ autoPlayOnMatch: !state.autoPlayOnMatch }))
    setTimeout(() => persistCurrentState(get), 0)  // state 업데이트 후 저장
  },

  // 더빙 시작
  startDubbing: () => {
    const { selectedWindowHwnd, selectedEpisodeId, cachedEpisodes, partialEpisodes } = get()

    if (!selectedWindowHwnd) {
      set({ ocrError: '캡처할 윈도우를 선택하세요' })
      return
    }

    // 사전 더빙 상태 확인
    if (selectedEpisodeId) {
      const safeId = selectedEpisodeId.replace(/\//g, '_').replace(/\\/g, '_')
      const hasCachedAudio = cachedEpisodes.includes(safeId) || partialEpisodes.includes(safeId)
      if (!hasCachedAudio) {
        set({ showNoCacheWarning: true })
        return
      }
    }

    // 윈도우 캡처 모드로 설정 후 더빙 시작
    set({ isDubbingMode: true, captureMode: 'window' })
    get().startMonitoring()
  },

  confirmStartDubbing: () => {
    set({ showNoCacheWarning: false, isDubbingMode: true, captureMode: 'window' })
    get().startMonitoring()
  },

  dismissNoCacheWarning: () => {
    set({ showNoCacheWarning: false })
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
  startBatchTraining: async (charIds?: string[], mode: 'prepare' | 'finetune' = 'prepare') => {
    const modeLabel = mode === 'finetune' ? '학습' : '준비'
    console.log(`[Training] startBatchTraining 호출, charIds: ${charIds}, mode: ${mode}`)
    try {
      set({ trainingError: null })

      // SSE 먼저 연결 (이벤트를 놓치지 않도록)
      console.log('[Training] SSE 먼저 연결')
      get().subscribeToTrainingProgress()

      // 약간의 딜레이 후 API 호출 (SSE 연결 완료 대기)
      await new Promise(resolve => setTimeout(resolve, 100))

      console.log('[Training] API 호출 시작')
      const data = await trainingApi.startBatchTraining(charIds, mode)
      console.log('[Training] API 응답:', data)

      if (data.jobs.length > 0) {
        console.log(`[Training] ${modeLabel} jobs 수:`, data.jobs.length)
        set({
          trainingQueue: data.jobs,
          isTrainingActive: true,
        })
      } else {
        console.log(`[Training] ${modeLabel}할 캐릭터가 없음`)
        // jobs가 없으면 SSE 연결 해제
        get().unsubscribeFromTrainingProgress()
      }
    } catch (error) {
      console.error(`[Training] ${modeLabel} 시작 실패:`, error)
      set({ trainingError: '준비 시작 실패' })
      // 오류 시 SSE 연결 해제
      get().unsubscribeFromTrainingProgress()
    }
  },

  // 준비 → 학습 연속 진행
  startFullBatchTraining: async (charIds?: string[]) => {
    console.log('[Training] 준비+학습 연속 진행 시작')
    // 준비 완료 후 자동으로 학습 시작하도록 플래그 설정
    set({ continueWithFinetune: true })
    // 준비 먼저 시작
    await get().startBatchTraining(charIds, 'prepare')
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

  // 개별 모델 삭제
  deleteModel: async (charId: string) => {
    try {
      await trainingApi.deleteModel(charId)
      console.log('[Training] 모델 삭제:', charId)
      // 상태에서 해당 모델 제거
      set((state) => {
        const newModels = state.trainedModels.filter(m => m.char_id !== charId)
        const newCharIds = new Set(newModels.map(m => m.char_id))
        return {
          trainedModels: newModels,
          trainedCharIds: newCharIds,
          trainingError: null,
        }
      })
    } catch (error) {
      console.error('Failed to delete model:', charId, error)
      set({ trainingError: '모델 삭제 실패' })
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
        console.log('[Training] 완료:', job.char_name, job.status, job.mode)
        // 학습 완료 시 모델 목록 새로고침
        get().loadTrainedModels()

        const { trainingQueue, continueWithFinetune } = get()
        const remainingJobs = trainingQueue.filter(j => j.job_id !== job.job_id)

        // 큐에서 완료된 작업 제거
        set({
          trainingQueue: remainingJobs,
          currentTrainingJob: null,
          isTrainingActive: remainingJobs.length > 0,
        })

        // 준비가 모두 완료되고 연속 학습 플래그가 설정되어 있으면 학습 시작
        if (remainingJobs.length === 0 && continueWithFinetune && job.mode === 'prepare') {
          console.log('[Training] 준비 완료, 자동으로 학습 시작')
          set({ continueWithFinetune: false })
          // 약간의 딜레이 후 학습 시작 (상태 안정화)
          setTimeout(() => {
            get().startBatchTraining(undefined, 'finetune')
          }, 500)
        }
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

  // 모델 타입 조회 (none, prepared, finetuned)
  getModelType: (charId: string) => {
    const model = get().trainedModels.find(m => m.char_id === charId)
    if (!model) return 'none'
    return model.model_type || (model.epochs_sovits > 0 ? 'finetuned' : 'prepared')
  },

  // finetune 가능 여부 (prepared 상태이고 전처리 완료됨)
  canFinetune: (charId: string) => {
    const model = get().trainedModels.find(m => m.char_id === charId)
    if (!model) return false
    // can_finetune 필드가 있으면 사용, 없으면 기존 로직 (하위 호환성)
    if (typeof model.can_finetune === 'boolean') {
      return model.can_finetune
    }
    // 하위 호환: prepared 상태이면 finetune 가능으로 간주 (기존 동작)
    return model.model_type === 'prepared'
  },

  // 전처리된 세그먼트 수 조회
  getSegmentCount: (charId: string) => {
    const model = get().trainedModels.find(m => m.char_id === charId)
    return model?.segment_count ?? 0
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
        partialEpisodes: status.partial_episodes || [],
        renderError: null,
      })
    } catch (error) {
      console.error('Failed to load render status:', error)
      set({ renderError: '렌더링 상태 로드 실패' })
    }
  },

  // 렌더링 시작
  startRender: async (episodeId: string, force: boolean = false) => {
    const { defaultCharId, narratorCharId, unknownSpeakerCharId, speakerVoiceMap, defaultFemaleVoices, defaultMaleVoices, getSpeakerVoice, loadEpisodeCharacters, loadVoiceCharacters } = get()

    // voiceCharacters가 비어있으면 먼저 로드 (getSpeakerVoice에서 사용)
    let { voiceCharacters } = get()
    if (voiceCharacters.length === 0) {
      console.log('[startRender] voiceCharacters 비어있음, 로드 중...')
      await loadVoiceCharacters()
      voiceCharacters = get().voiceCharacters
      console.log('[startRender] voiceCharacters 로드 완료:', voiceCharacters.length)
    }

    // episodeCharacters가 비어있으면 먼저 로드
    let { episodeCharacters } = get()
    if (episodeCharacters.length === 0) {
      console.log('[startRender] episodeCharacters 비어있음, 로드 중...')
      await loadEpisodeCharacters(episodeId)
      // 로드 후 다시 가져오기
      episodeCharacters = get().episodeCharacters
      console.log('[startRender] episodeCharacters 로드 완료:', episodeCharacters.length)
    }

    // 1. episodeCharacters에서 voice_char_id가 있는 캐릭터들의 매핑 추가
    // (실시간 재생과 동일한 로직 적용)
    const resolvedVoiceMap: Record<string, string> = {}

    console.log('[startRender] episodeCharacters 수:', episodeCharacters.length)

    // voice_char_id가 있는 캐릭터들 자동 매핑
    for (const char of episodeCharacters) {
      // char_id가 있는 경우: char_id와 name: 키 모두 매핑
      if (char.char_id) {
        const voiceId = getSpeakerVoice(char.char_id, char.name)
        if (voiceId) {
          resolvedVoiceMap[char.char_id] = voiceId
          console.log(`[startRender] 캐릭터 매핑: ${char.char_id} (${char.name}) → ${voiceId}`)

          // name: 키도 추가 (speaker_id가 없는 대사용)
          // 단, 미스터리 이름(???)은 전파하지 않음 (unknownSpeakerCharId로 처리)
          if (!isMysteryName(char.name)) {
            const nameKey = `name:${char.name}`
            if (!resolvedVoiceMap[nameKey]) {
              resolvedVoiceMap[nameKey] = voiceId
            }
          }
        } else {
          console.log(`[startRender] 캐릭터 음성 없음: ${char.char_id} (${char.name})`)
        }
      }
      // char_id가 없지만 voice_char_id가 있는 경우: 별칭 캐릭터 (예: '오니' → 하루카)
      else if (char.voice_char_id && char.name) {
        const nameKey = `name:${char.name}`
        resolvedVoiceMap[nameKey] = char.voice_char_id
        console.log(`[startRender] 별칭 매핑: ${char.name} → ${char.voice_char_id}`)
      }
    }

    // 2. speakerVoiceMap 해석 + 알 수 없는 화자 매핑 (공통 함수 사용)
    const speakerResolved = resolveSpeakerMappings(speakerVoiceMap, defaultFemaleVoices, defaultMaleVoices, unknownSpeakerCharId)
    Object.assign(resolvedVoiceMap, speakerResolved)

    try {
      set({ renderError: null })

      console.log('[startRender] 렌더링 시작 요청:', {
        episodeId,
        defaultCharId,
        narratorCharId,
        speakerVoiceMap: Object.keys(speakerVoiceMap).length,
        resolvedVoiceMap,
        defaultFemaleVoices,
        defaultMaleVoices,
        force,
      })

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

  // 렌더 캐시 삭제
  deleteRenderCache: async (episodeId: string) => {
    try {
      await renderApi.deleteCache(episodeId)
      // 상태 초기화
      set({
        renderProgress: null,
        cachedEpisodes: get().cachedEpisodes.filter(id => id !== episodeId),
      })
      // 캐시 목록 갱신
      await get().loadRenderStatus()
    } catch (error) {
      console.error('Failed to delete render cache:', error)
      set({ renderError: '캐시 삭제 실패' })
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

  // === 그룹 렌더링 ===

  // 그룹 렌더링 시작
  startGroupRender: async (groupId: string, force: boolean = false) => {
    const { defaultCharId, narratorCharId, unknownSpeakerCharId, speakerVoiceMap, defaultFemaleVoices, defaultMaleVoices } = get()

    // speakerVoiceMap 해석 + 알 수 없는 화자 매핑 (공통 함수 사용)
    const resolvedVoiceMap = resolveSpeakerMappings(speakerVoiceMap, defaultFemaleVoices, defaultMaleVoices, unknownSpeakerCharId)

    try {
      set({ groupRenderError: null })

      console.log('[startGroupRender] 그룹 렌더링 시작 요청:', {
        groupId,
        defaultCharId,
        narratorCharId,
        speakerVoiceMap: Object.keys(resolvedVoiceMap).length,
        force,
      })

      const progress = await renderApi.startGroupRender(
        groupId,
        'ko',
        defaultCharId || undefined,
        narratorCharId || undefined,
        Object.keys(resolvedVoiceMap).length > 0 ? resolvedVoiceMap : undefined,
        force
      )

      set({
        isGroupRendering: progress.status === 'rendering',
        groupRenderProgress: progress,
      })

      // 렌더링 진행 중이면 구독 시작
      if (progress.status === 'rendering') {
        get().subscribeToGroupRenderProgress(groupId)
      }
    } catch (error: any) {
      console.error('Failed to start group render:', error)
      const errorMsg = error?.response?.data?.detail || '그룹 렌더링 시작 실패'
      set({ groupRenderError: errorMsg })
    }
  },

  // 그룹 렌더링 취소
  cancelGroupRender: async () => {
    try {
      await renderApi.cancelGroupRender()
      set({
        isGroupRendering: false,
        groupRenderProgress: null,
      })
      get().unsubscribeFromGroupRenderProgress()
    } catch (error) {
      console.error('Failed to cancel group render:', error)
      set({ groupRenderError: '그룹 렌더링 취소 실패' })
    }
  },

  // 그룹 렌더링 진행 상황 구독
  subscribeToGroupRenderProgress: (groupId: string) => {
    if (groupRenderStream) {
      groupRenderStream.close()
    }

    groupRenderStream = createGroupRenderStream(groupId, {
      onProgress: (progress) => {
        set({
          groupRenderProgress: progress,
          isGroupRendering: progress.status === 'rendering',
        })
      },
      onComplete: (progress) => {
        set({
          groupRenderProgress: progress,
          isGroupRendering: false,
        })
        // 캐시 목록 갱신
        get().loadRenderStatus()
      },
      onError: (error) => {
        console.error('Group render stream error:', error)
        set({ groupRenderError: error })
      },
    })
  },

  // 그룹 렌더링 진행 상황 구독 해제
  unsubscribeFromGroupRenderProgress: () => {
    if (groupRenderStream) {
      groupRenderStream.close()
      groupRenderStream = null
    }
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

  // TTS 엔진 설정 로드
  loadTtsEngineSetting: async () => {
    try {
      const setting = await settingsApi.getTTSEngineSetting()
      set({ defaultTtsEngine: setting.engine })
    } catch (error) {
      console.error('Failed to load TTS engine setting:', error)
    }
  },

  // GPU 세마포어 상태 로드
  // TTS 추론 파라미터 로드
  loadTtsParams: async () => {
    try {
      const params = await ttsApi.getTtsParams()
      set({ ttsParams: params })
    } catch (error) {
      console.error('Failed to load TTS params:', error)
    }
  },

  // TTS 추론 파라미터 업데이트
  updateTtsParams: async (params) => {
    try {
      const updated = await ttsApi.updateTtsParams(params)
      set({ ttsParams: updated })
    } catch (error) {
      console.error('Failed to update TTS params:', error)
    }
  },

  loadGpuSemaphoreStatus: async () => {
    try {
      const result = await settingsApi.getGpuSemaphore()
      set({ gpuSemaphoreEnabled: result.enabled })
    } catch (error) {
      console.error('Failed to load GPU semaphore status:', error)
    }
  },

  // GPU 세마포어 토글
  toggleGpuSemaphore: async () => {
    const { gpuSemaphoreEnabled } = get()
    try {
      const result = await settingsApi.setGpuSemaphore(!gpuSemaphoreEnabled)
      set({ gpuSemaphoreEnabled: result.enabled })
    } catch (error) {
      console.error('Failed to toggle GPU semaphore:', error)
    }
  },

  // 볼륨 설정
  setVolume: (volume: number) => {
    set({ volume: Math.max(0, Math.min(1, volume)) })
    // 현재 재생 중인 오디오가 있으면 볼륨 즉시 적용
    if (currentAudio) {
      const { isMuted } = get()
      currentAudio.volume = isMuted ? 0 : volume
    }
    persistCurrentState(get)
  },

  // 음소거 토글
  toggleMute: () => {
    set((state) => {
      const newMuted = !state.isMuted
      // 현재 재생 중인 오디오가 있으면 즉시 적용
      if (currentAudio) {
        currentAudio.volume = newMuted ? 0 : state.volume
      }
      return { isMuted: newMuted }
    })
    persistCurrentState(get)
  },

  // 왼쪽 패널 접기/펼치기
  toggleLeftPanel: () => {
    set((state) => ({ isLeftPanelCollapsed: !state.isLeftPanelCollapsed }))
    persistCurrentState(get)
  },

  // 오른쪽 패널 접기/펼치기
  toggleRightPanel: () => {
    set((state) => ({ isRightPanelCollapsed: !state.isRightPanelCollapsed }))
    persistCurrentState(get)
  },
}))

// 학습 스트림 참조
let trainingStream: { close: () => void } | null = null

// 렌더링 스트림 참조
let renderStream: { close: () => void } | null = null

// 그룹 렌더링 스트림 참조
let groupRenderStream: { close: () => void } | null = null
