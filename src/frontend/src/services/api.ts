import axios from 'axios'

const API_BASE = 'http://127.0.0.1:8000'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
})

// OCR용 (모델 로드에 시간이 걸림)
const ocrApiClient = axios.create({
  baseURL: API_BASE,
  timeout: 120000,  // 2분 (첫 모델 로드 시)
})

// 에피소드 관련 API
export interface DialogueInfo {
  id: string
  speaker_id: string | null
  speaker_name: string
  text: string
  line_number: number
}

export interface EpisodeSummary {
  id: string
  code: string      // "0-1", "1-7"
  name: string      // "어둠 속에서"
  tag: string       // "작전 전", "작전 후"
  chapter: string   // "서장", "제1장"
  display_name: string  // "0-1 어둠 속에서"
}

export interface MainEpisodesResponse {
  total: number
  language: string
  chapters: Record<string, EpisodeSummary[]>
  episodes: EpisodeSummary[]
}

export interface EpisodeDetail {
  id: string
  title: string
  dialogues: DialogueInfo[]
  characters: string[]
}

export interface CharacterInfo {
  id: string
  name: string
}

// 스토리 카테고리/그룹 관련 타입
export interface CategoryInfo {
  id: string
  name: string
  group_count: number
  episode_count: number
}

export interface StoryGroupInfo {
  id: string
  name: string
  category: string
  entry_type: string
  episode_count: number
}

export interface GroupEpisodeInfo {
  id: string
  story_id: string
  code: string
  name: string
  tag: string
  display_name: string
}

export const episodesApi = {
  // 메인 스토리 에피소드 목록
  listMainEpisodes: async (lang?: string) => {
    const params = lang ? { lang } : {}
    const res = await api.get<MainEpisodesResponse>('/api/episodes/main', { params })
    return res.data
  },

  // 에피소드 상세
  getEpisode: async (episodeId: string) => {
    const res = await api.get<EpisodeDetail>(`/api/episodes/${episodeId}`)
    return res.data
  },

  // 에피소드 캐릭터 목록
  getEpisodeCharacters: async (episodeId: string) => {
    const res = await api.get<{ episode_id: string; characters: CharacterInfo[] }>(
      `/api/episodes/${episodeId}/characters`
    )
    return res.data
  },
}

// 스토리 카테고리/그룹 API
export const storiesApi = {
  // 카테고리 목록
  listCategories: async (lang?: string) => {
    const params = lang ? { lang } : {}
    const res = await api.get<{ categories: CategoryInfo[]; language: string }>(
      '/api/stories/categories',
      { params }
    )
    return res.data
  },

  // 카테고리별 그룹 목록
  listCategoryGroups: async (categoryId: string, lang?: string) => {
    const params = lang ? { lang } : {}
    const res = await api.get<{ category: string; total: number; groups: StoryGroupInfo[] }>(
      `/api/stories/categories/${categoryId}/groups`,
      { params }
    )
    return res.data
  },

  // 그룹별 에피소드 목록
  listGroupEpisodes: async (groupId: string, lang?: string) => {
    const params = lang ? { lang } : {}
    const res = await api.get<{
      group_id: string
      group_name: string
      category: string
      total: number
      episodes: GroupEpisodeInfo[]
    }>(`/api/stories/groups/${groupId}/episodes`, { params })
    return res.data
  },
}

// TTS 관련 API
export const ttsApi = {
  // 음성 합성
  synthesize: async (text: string, voiceId?: string): Promise<Blob> => {
    const res = await api.post('/api/tts/synthesize',
      { text, voice_id: voiceId },
      { responseType: 'blob' }
    )
    return res.data
  },

  // 사용 가능한 음성 목록
  listVoices: async () => {
    const res = await api.get<{ default: string; voices: string[] }>('/api/tts/voices')
    return res.data
  },

  // 언어별 음성 목록
  listVoicesByLanguage: async (language: string) => {
    const res = await api.get<{ language: string; voices: Array<{ name: string; gender: string; friendly_name: string }> }>(
      `/api/tts/voices/${language}`
    )
    return res.data
  },
}

// 음성 자산 관련 API
export interface VoiceCharacter {
  char_id: string
  name: string
  file_count: number
  has_voice: boolean
}

export const voiceApi = {
  // 음성이 있는 캐릭터 목록
  listCharacters: async () => {
    const res = await api.get<{ total: number; characters: VoiceCharacter[] }>('/api/voice/characters')
    return res.data
  },

  // 캐릭터 음성 정보
  getCharacterVoice: async (charId: string) => {
    const res = await api.get<{ char_id: string; name: string; file_count: number; files: string[] }>(
      `/api/voice/characters/${charId}`
    )
    return res.data
  },

  // 음성 존재 확인
  checkVoice: async (charId: string) => {
    const res = await api.get<{ char_id: string; has_voice: boolean }>(`/api/voice/check/${charId}`)
    return res.data
  },
}

// OCR 관련 타입
export interface BoundingBox {
  x: number
  y: number
  width: number
  height: number
}

export interface OCRResult {
  text: string
  confidence: number
  bounding_box: BoundingBox | null
}

export interface MonitorInfo {
  id: number
  name: string
  left: number
  top: number
  width: number
  height: number
}

export interface DetectDialogueResponse {
  text: string | null
  confidence: number
  timestamp: number
}

export interface WindowInfo {
  hwnd: number
  title: string
  left: number
  top: number
  width: number
  height: number
}

// OCR API
export const ocrApi = {
  // 모니터 목록
  listMonitors: async () => {
    const res = await api.get<{ monitors: MonitorInfo[] }>('/api/ocr/monitors')
    return res.data
  },

  // 대사 영역 좌표
  getDialogueRegion: async (width: number, height: number) => {
    const res = await api.get<{ region: BoundingBox; screen_width: number; screen_height: number }>(
      '/api/ocr/dialogue-region',
      { params: { width, height } }
    )
    return res.data
  },

  // 화면 캡처 (base64)
  captureScreen: async (monitor: number = 1) => {
    const res = await api.get<{ image_base64: string; width: number; height: number }>(
      '/api/ocr/capture',
      { params: { monitor } }
    )
    return res.data
  },

  // 대사 영역 캡처 (base64)
  captureDialogue: async (monitor: number = 1) => {
    const res = await api.get<{ image_base64: string; width: number; height: number }>(
      '/api/ocr/capture/dialogue',
      { params: { monitor } }
    )
    return res.data
  },

  // 직접 이미지 URL 생성 (base64 대신 직접 이미지 서빙)
  getCaptureImageUrl: (monitor: number = 1) => {
    return `${API_BASE}/api/ocr/capture/image?monitor=${monitor}&t=${Date.now()}`
  },

  getDialogueImageUrl: (monitor: number = 1) => {
    return `${API_BASE}/api/ocr/capture/dialogue/image?monitor=${monitor}&t=${Date.now()}`
  },

  getCustomRegionImageUrl: (region: BoundingBox) => {
    return `${API_BASE}/api/ocr/capture/region/image?x=${region.x}&y=${region.y}&width=${region.width}&height=${region.height}&t=${Date.now()}`
  },

  // 사용자 지정 영역 설정
  setCustomRegion: async (region: BoundingBox) => {
    const res = await api.post<{ saved: boolean; region: BoundingBox }>(
      '/api/ocr/region/custom',
      region
    )
    return res.data
  },

  // 사용자 지정 영역 조회
  getCustomRegion: async () => {
    const res = await api.get<{ region: BoundingBox | null }>('/api/ocr/region/custom')
    return res.data
  },

  // 사용자 지정 영역에서 텍스트 감지
  detectCustomRegion: async (lang: string = 'ko', minConfidence: number = 0.5) => {
    const res = await ocrApiClient.get<DetectDialogueResponse>(
      '/api/ocr/detect/custom',
      { params: { lang, min_confidence: minConfidence } }
    )
    return res.data
  },

  // 대사 감지 (캡처 + OCR)
  detectDialogue: async (monitor: number = 1, lang: string = 'ko', minConfidence: number = 0.5) => {
    const res = await ocrApiClient.get<DetectDialogueResponse>(
      '/api/ocr/detect',
      { params: { monitor, lang, min_confidence: minConfidence } }
    )
    return res.data
  },

  // 이미지 OCR
  recognizeImage: async (file: File, lang: string = 'ko') => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await ocrApiClient.post<{ results: OCRResult[]; language: string }>(
      '/api/ocr/recognize',
      formData,
      { params: { lang } }
    )
    return res.data
  },

  // 지원 언어 목록
  listLanguages: async () => {
    const res = await api.get<{ languages: Array<{ code: string; name: string }> }>('/api/ocr/languages')
    return res.data
  },

  // 윈도우 목록 (Windows 전용)
  listWindows: async () => {
    const res = await api.get<{ windows: WindowInfo[] }>('/api/ocr/windows')
    return res.data
  },

  // 윈도우 캡처 이미지 URL (상단 15% UI 영역 제외)
  getWindowImageUrl: (hwnd: number, ignoreTopRatio: number = 0.15) => {
    return `${API_BASE}/api/ocr/capture/window/image?hwnd=${hwnd}&ignore_top_ratio=${ignoreTopRatio}&t=${Date.now()}`
  },

  // 윈도우에서 대사 감지
  detectWindow: async (hwnd: number, lang: string = 'ko', minConfidence: number = 0.5) => {
    const res = await ocrApiClient.get<DetectDialogueResponse>(
      '/api/ocr/detect/window',
      { params: { hwnd, lang, min_confidence: minConfidence } }
    )
    return res.data
  },
}

// 헬스 체크
export const healthCheck = async (): Promise<boolean> => {
  try {
    const res = await api.get('/health')
    return res.data.status === 'ok'
  } catch {
    return false
  }
}

export default api
