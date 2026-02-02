import { create } from 'zustand'
import {
  episodesApi,
  storiesApi,
  ttsApi,
  ocrApi,
  healthCheck,
  type EpisodeDetail,
  type DialogueInfo,
  type EpisodeSummary,
  type CategoryInfo,
  type StoryGroupInfo,
  type GroupEpisodeInfo,
  type MonitorInfo,
  type WindowInfo,
  type DetectDialogueResponse,
  type BoundingBox,
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

  // TTS 관련
  selectedVoice: string
  availableVoices: string[]
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
  setSelectedVoice: (voice: string) => void
  loadVoices: () => Promise<void>

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
}

// 오디오 재생 관리
let currentAudio: HTMLAudioElement | null = null

// OCR 모니터링 인터벌
let monitoringInterval: ReturnType<typeof setInterval> | null = null

export const useAppStore = create<AppState>((set, get) => ({
  // 초기 상태
  backendStatus: 'checking',
  categories: [],
  selectedCategoryId: null,
  storyGroups: [],
  selectedGroupId: null,
  groupEpisodes: [],
  isLoadingCategories: false,
  isLoadingGroups: false,
  isLoadingGroupEpisodes: false,
  episodes: [],
  chapters: {},
  selectedEpisodeId: null,
  selectedEpisode: null,
  isLoadingEpisodes: false,
  isLoadingEpisode: false,
  selectedVoice: 'ko',
  availableVoices: [],
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
    set({ isLoadingCategories: true })
    try {
      const data = await storiesApi.listCategories()
      set({ categories: data.categories })
      // 첫 번째 카테고리 자동 선택
      if (data.categories.length > 0 && !get().selectedCategoryId) {
        get().selectCategory(data.categories[0].id)
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
    set({ selectedGroupId: groupId, isLoadingGroupEpisodes: true })
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
    set({ isLoadingEpisode: true, selectedEpisodeId: episodeId })
    try {
      const data = await episodesApi.getEpisode(episodeId)
      set({ selectedEpisode: data })
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

  // 대사 재생
  playDialogue: async (dialogue: DialogueInfo) => {
    const { selectedVoice } = get()

    // 기존 재생 중지
    if (currentAudio) {
      currentAudio.pause()
      currentAudio = null
    }

    set({ isPlaying: true, currentDialogue: dialogue })

    try {
      const audioBlob = await ttsApi.synthesize(dialogue.text, selectedVoice)
      const audioUrl = URL.createObjectURL(audioBlob)

      currentAudio = new Audio(audioUrl)
      currentAudio.onended = () => {
        set({ isPlaying: false, currentDialogue: null })
        URL.revokeObjectURL(audioUrl)
      }
      currentAudio.onerror = () => {
        set({ isPlaying: false, currentDialogue: null })
        URL.revokeObjectURL(audioUrl)
      }

      await currentAudio.play()
    } catch (error) {
      console.error('Failed to play dialogue:', error)
      set({ isPlaying: false, currentDialogue: null })
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

  // 음성 선택
  setSelectedVoice: (voice: string) => {
    set({ selectedVoice: voice })
  },

  // 음성 목록 로드
  loadVoices: async () => {
    try {
      const data = await ttsApi.listVoices()
      set({ availableVoices: data.voices, selectedVoice: data.default || 'ko' })
    } catch (error) {
      console.error('Failed to load voices:', error)
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
    const { selectedMonitorId, selectedWindowHwnd, captureMode, ocrLanguage } = get()
    try {
      set({ ocrError: null })

      let result: DetectDialogueResponse
      if (captureMode === 'window' && selectedWindowHwnd) {
        result = await ocrApi.detectWindow(selectedWindowHwnd, ocrLanguage)
      } else {
        result = await ocrApi.detectDialogue(selectedMonitorId, ocrLanguage)
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
    if (monitoringInterval) return // 이미 실행 중

    set({ isMonitoring: true, ocrError: null })

    // 즉시 한 번 실행
    get().detectOnce()

    // 주기적 실행 (500ms 간격)
    monitoringInterval = setInterval(() => {
      get().detectOnce()
    }, 500)
  },

  // OCR: 모니터링 중지
  stopMonitoring: () => {
    if (monitoringInterval) {
      clearInterval(monitoringInterval)
      monitoringInterval = null
    }
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
}))
