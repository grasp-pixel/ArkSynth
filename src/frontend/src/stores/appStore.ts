import { create } from 'zustand'
import {
  episodesApi,
  storiesApi,
  ttsApi,
  healthCheck,
  type EpisodeDetail,
  type DialogueInfo,
  type EpisodeSummary,
  type CategoryInfo,
  type StoryGroupInfo,
  type GroupEpisodeInfo,
} from '../services/api'

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
}

// 오디오 재생 관리
let currentAudio: HTMLAudioElement | null = null

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
}))
