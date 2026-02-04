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

export interface GroupCharacterInfo {
  char_id: string | null  // null이면 나레이터
  name: string
  dialogue_count: number
  has_voice: boolean
  voice_char_id: string | null  // 실제 음성 파일이 있는 캐릭터 ID (이름 매칭 시)
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

  // 에피소드 캐릭터(화자) 목록 - speaker_name 기준
  getEpisodeCharacters: async (episodeId: string) => {
    const res = await api.get<{
      episode_id: string
      total: number
      characters: GroupCharacterInfo[]  // GroupCharacterInfo와 동일 구조
      narration_count: number  // 나레이션 대사 수 (화자 없는 대사)
    }>(`/api/episodes/${episodeId}/characters`)
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

  // 그룹별 캐릭터 목록 (음성 보유 여부 포함)
  listGroupCharacters: async (groupId: string, lang?: string) => {
    const params = lang ? { lang } : {}
    const res = await api.get<{
      group_id: string
      group_name: string
      total: number
      characters: GroupCharacterInfo[]
    }>(`/api/stories/groups/${groupId}/characters`, { params })
    return res.data
  },
}

// TTS 관련 API
export const ttsApi = {
  // 음성 합성 (GPT-SoVITS)
  // TTS 파라미터는 백엔드 config의 기본값 사용
  // 첫 합성은 API 서버 시작 + 참조 오디오 준비로 오래 걸릴 수 있음 (최대 120초)
  synthesize: async (text: string, charId: string): Promise<Blob> => {
    const res = await api.post('/api/tts/synthesize',
      { text, char_id: charId },
      {
        responseType: 'blob',
        timeout: 120000,  // 120초 (첫 합성 시 API 서버 시작 + 참조 준비 포함)
      }
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

  // GPT-SoVITS 상태 확인
  getGptSovitsStatus: async () => {
    const res = await api.get<{
      installed: boolean
      api_running: boolean
      synthesizing?: boolean  // 합성 진행 중 여부
      ready_characters: string[]
      ready_count: number
      error?: string
    }>('/api/tts/gpt-sovits/status')
    return res.data
  },

  // GPT-SoVITS API 서버 시작
  startGptSovits: async () => {
    const res = await api.post<{
      status: string
      message: string
    }>('/api/tts/gpt-sovits/start', {}, { timeout: 70000 })  // 60초 대기 + 여유
    return res.data
  },

  // GPT-SoVITS 진단 정보
  diagnoseGptSovits: async () => {
    const res = await api.get<GptSovitsDiagnosis>('/api/tts/gpt-sovits/diagnose')
    return res.data
  },

  // 제로샷 강제 모드 상태 조회
  getForceZeroShot: async () => {
    const res = await api.get<{ force_zero_shot: boolean }>('/api/tts/gpt-sovits/force-zero-shot')
    return res.data
  },

  // 제로샷 강제 모드 토글
  setForceZeroShot: async (enabled: boolean) => {
    const res = await api.post<{ force_zero_shot: boolean; message: string }>(
      `/api/tts/gpt-sovits/force-zero-shot?enabled=${enabled}`
    )
    return res.data
  },
}

// GPT-SoVITS 진단 타입
export interface GptSovitsDiagnosis {
  config: {
    gpt_sovits_path: string
    gpt_sovits_path_exists: boolean
    python_path: string | null
    python_exists: boolean
    api_url: string
  }
  installation: {
    is_installed: boolean
    api_v2_exists: boolean
    api_v1_exists: boolean
    runtime_dir_exists: boolean
    runtime_python_exists?: boolean
    critical_dirs: Record<string, boolean>
  }
  api_status: {
    gpt_sovits_installed: boolean
    gpt_sovits_path: string
    python_path: string | null
    api_url: string
    process_running: boolean
    process_pid: number | null
    api_script_exists: boolean
    api_script_path: string
    process_exit_code?: number
  }
  api_reachable: boolean
  error?: string
  error_type?: string
}

// 음성 자산 관련 API
export interface VoiceCharacter {
  char_id: string
  name: string
  file_count: number
  has_voice: boolean
  dialogue_count?: number  // 전체 스토리 기준 대사 수
}

// 캐릭터 별칭 타입
export interface CharacterAliases {
  total: number
  aliases: Record<string, string>  // alias -> char_id
  aliases_by_char: Record<string, string[]>  // char_id -> alias[]
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

  // 캐릭터 데이터 새로고침 (게임 데이터 업데이트 후)
  refresh: async () => {
    const res = await api.post<{ total_characters: number; message: string }>('/api/voice/refresh')
    return res.data
  },

  // === 캐릭터 별칭 API ===

  // 전체 별칭 목록 조회
  listAliases: async () => {
    const res = await api.get<CharacterAliases>('/api/voice/aliases')
    return res.data
  },

  // 특정 캐릭터의 별칭 목록 조회
  getCharacterAliases: async (charId: string) => {
    const res = await api.get<{ char_id: string; aliases: string[] }>(
      `/api/voice/aliases/${encodeURIComponent(charId)}`
    )
    return res.data
  },

  // 별칭 추가
  addAlias: async (alias: string, charId: string) => {
    const res = await api.post<{ message: string; alias: string; char_id: string }>(
      '/api/voice/aliases',
      { alias, char_id: charId }
    )
    return res.data
  },

  // 별칭 삭제
  removeAlias: async (alias: string) => {
    const res = await api.delete<{ message: string; alias: string; char_id: string }>(
      `/api/voice/aliases/${encodeURIComponent(alias)}`
    )
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

export interface StableDetectResponse {
  text: string | null
  confidence: number
  timestamp: number
  is_stable: boolean
  is_new: boolean
}

export interface MatchDialogueResponse {
  matched: boolean
  dialogue: DialogueInfo | null
  similarity: number
  index: number
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
  detectWindow: async (hwnd: number, lang: string = 'ko', minConfidence: number = 0.2) => {
    const res = await ocrApiClient.get<DetectDialogueResponse>(
      '/api/ocr/detect/window',
      { params: { hwnd, lang, min_confidence: minConfidence } }
    )
    return res.data
  },

  // 윈도우에서 대사 감지 (안정화 적용 - 타이핑 효과 대기)
  detectWindowStable: async (hwnd: number, lang: string = 'ko', minConfidence: number = 0.2, stabilityThreshold: number = 3) => {
    const res = await ocrApiClient.get<StableDetectResponse>(
      '/api/ocr/detect/window/stable',
      { params: { hwnd, lang, min_confidence: minConfidence, stability_threshold: stabilityThreshold } }
    )
    return res.data
  },

  // 윈도우 안정화 상태 초기화
  resetWindowStability: async (hwnd?: number) => {
    const params = hwnd !== undefined ? { hwnd } : {}
    const res = await api.post<{ reset: boolean }>('/api/ocr/detect/window/reset', null, { params })
    return res.data
  },

  // OCR 결과를 에피소드 대사와 매칭
  matchDialogue: async (episodeId: string, text: string, minSimilarity: number = 0.5) => {
    const res = await api.post<MatchDialogueResponse>(
      '/api/ocr/match',
      { episode_id: episodeId, text, min_similarity: minSimilarity }
    )
    return res.data
  },

  // DialogueMatcher 상태 초기화
  resetMatcher: async (episodeId?: string) => {
    const params = episodeId ? { episode_id: episodeId } : {}
    const res = await api.post<{ reset: boolean; message?: string }>('/api/ocr/match/reset', null, { params })
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

// SSE 스트리밍 타입
export interface DialogueStreamEvent {
  type: 'dialogue' | 'error' | 'status' | 'connected' | 'capture_failed' | 'setup_error'
  text?: string
  confidence?: number
  timestamp?: number
  is_new?: boolean
  message?: string
  hwnd?: number
}

// === 학습 API ===

export interface TrainingJob {
  job_id: string
  char_id: string
  char_name: string
  mode: TrainingMode
  status: 'pending' | 'preprocessing' | 'training' | 'completed' | 'failed' | 'cancelled'
  progress: number
  current_epoch: number
  total_epochs: number
  message: string
  error_message: string | null
  created_at: string | null
  started_at: string | null
  completed_at: string | null
}

export interface TrainingStatusResponse {
  is_training: boolean
  current_job: TrainingJob | null
  queue_length: number
  trained_count: number
  total_trainable: number
}

export interface TrainedModel {
  char_id: string
  char_name: string
  trained_at: string
  language: string
  model_type: 'none' | 'prepared' | 'finetuned'
  epochs_sovits: number
  epochs_gpt: number
  is_preprocessed: boolean  // 전처리 완료 여부
  segment_count: number     // 전처리된 세그먼트 수
  can_finetune: boolean     // finetune 가능 여부 (prepared이고 전처리 완료됨)
}

export type TrainingMode = 'prepare' | 'finetune'

export const trainingApi = {
  // 전체 학습 상태 요약
  getStatus: async () => {
    const res = await api.get<TrainingStatusResponse>('/api/training/status')
    return res.data
  },

  // 학습 작업 목록
  listJobs: async (status?: string) => {
    const params = status ? { status } : {}
    const res = await api.get<{ jobs: TrainingJob[]; total: number }>(
      '/api/training/jobs',
      { params }
    )
    return res.data
  },

  // 특정 작업 상태
  getJob: async (jobId: string) => {
    const res = await api.get<TrainingJob>(`/api/training/jobs/${jobId}`)
    return res.data
  },

  // 단일 캐릭터 학습 시작
  startTraining: async (charId: string, mode: TrainingMode = 'prepare') => {
    const res = await api.post<{ job: TrainingJob }>(
      `/api/training/start/${charId}`,
      { mode }
    )
    return res.data
  },

  // 일괄 학습 시작
  startBatchTraining: async (charIds?: string[], mode: TrainingMode = 'prepare') => {
    const res = await api.post<{ jobs: TrainingJob[]; total: number; message?: string }>(
      '/api/training/start-batch',
      { char_ids: charIds || null, mode }
    )
    return res.data
  },

  // 모델 타입 조회
  getModelType: async (charId: string) => {
    const res = await api.get<{
      char_id: string
      model_type: 'none' | 'prepared' | 'finetuned'
      is_preprocessed: boolean
      can_finetune: boolean
    }>(`/api/training/models/${charId}/type`)
    return res.data
  },

  // 학습 취소
  cancelTraining: async (jobId: string) => {
    const res = await api.post<{ cancelled: boolean }>(`/api/training/cancel/${jobId}`)
    return res.data
  },

  // 학습된 모델 목록
  listModels: async () => {
    const res = await api.get<{ models: TrainedModel[]; total: number }>('/api/training/models')
    return res.data
  },

  // 모델 삭제
  deleteModel: async (charId: string) => {
    const res = await api.delete<{ deleted: boolean }>(`/api/training/models/${charId}`)
    return res.data
  },

  // 모든 모델 삭제
  deleteAllModels: async () => {
    const res = await api.delete<{ deleted: boolean; deleted_count: number }>('/api/training/models')
    return res.data
  },
}

// === 렌더링 API ===

export interface RenderProgress {
  episode_id: string
  status: 'idle' | 'rendering' | 'completed' | 'cancelled' | 'failed' | 'not_started' | 'partial'
  total: number
  completed: number
  progress_percent: number
  current_index: number | null
  current_text: string | null
  error: string | null
}

export interface RenderStatusResponse {
  is_rendering: boolean
  current_episode_id: string | null
  cached_episodes: string[]
  cached_count: number
  current_progress: RenderProgress | null
}

export interface CacheInfo {
  episode_id: string
  total_dialogues: number
  rendered_count: number
  rendered_at: string
  language: string
  cache_size: number
  audios: Array<{
    index: number
    char_id: string | null
    text: string
    duration: number
  }>
}

export const renderApi = {
  // 전체 렌더링 상태
  getStatus: async () => {
    const res = await api.get<RenderStatusResponse>('/api/render/status')
    return res.data
  },

  // 에피소드 렌더링 시작
  startRender: async (
    episodeId: string,
    language: string = 'ko',
    defaultCharId?: string,
    narratorCharId?: string,
    speakerVoiceMap?: Record<string, string>,
    force: boolean = false
  ) => {
    const res = await api.post<RenderProgress>(
      `/api/render/start/${encodeURIComponent(episodeId)}`,
      {
        language,
        default_char_id: defaultCharId,
        narrator_char_id: narratorCharId,
        speaker_voice_map: speakerVoiceMap,
        force
      }
    )
    return res.data
  },

  // 렌더링 취소
  cancelRender: async (episodeId: string) => {
    const res = await api.post<{ cancelled: boolean }>(
      `/api/render/cancel/${encodeURIComponent(episodeId)}`
    )
    return res.data
  },

  // 렌더링 진행률 조회
  getProgress: async (episodeId: string) => {
    const res = await api.get<RenderProgress>(
      `/api/render/progress/${encodeURIComponent(episodeId)}`
    )
    return res.data
  },

  // 렌더링된 오디오 URL
  getAudioUrl: (episodeId: string, index: number) => {
    return `${API_BASE}/api/render/audio/${encodeURIComponent(episodeId)}/${index}`
  },

  // 캐시 정보 조회
  getCacheInfo: async (episodeId: string) => {
    const res = await api.get<CacheInfo>(
      `/api/render/cache/${encodeURIComponent(episodeId)}`
    )
    return res.data
  },

  // 캐시 삭제
  deleteCache: async (episodeId: string) => {
    const res = await api.delete<{ deleted: boolean }>(
      `/api/render/cache/${encodeURIComponent(episodeId)}`
    )
    return res.data
  },
}

// 렌더링 진행률 SSE 스트림
export function createRenderStream(
  episodeId: string,
  options: {
    onProgress?: (progress: RenderProgress) => void
    onComplete?: (progress: RenderProgress) => void
    onError?: (error: string) => void
  } = {}
): { close: () => void } {
  const { onProgress, onComplete, onError } = options

  const eventSource = new EventSource(
    `${API_BASE}/api/render/stream/${encodeURIComponent(episodeId)}`
  )

  eventSource.addEventListener('progress', (event) => {
    const progress = JSON.parse(event.data) as RenderProgress
    onProgress?.(progress)
  })

  eventSource.addEventListener('complete', (event) => {
    const progress = JSON.parse(event.data) as RenderProgress
    onComplete?.(progress)
  })

  eventSource.addEventListener('ping', () => {
    // 킵얼라이브, 무시
  })

  eventSource.onerror = () => {
    onError?.('Render stream connection failed')
  }

  return {
    close: () => {
      eventSource.close()
    }
  }
}

// 학습 진행률 SSE 스트림
export function createTrainingStream(
  options: {
    onProgress?: (job: TrainingJob) => void
    onComplete?: (job: TrainingJob) => void
    onStatus?: (status: TrainingStatusResponse) => void
    onError?: (error: string) => void
  } = {}
): { close: () => void } {
  const { onProgress, onComplete, onStatus, onError } = options

  console.log('[SSE] createTrainingStream: 연결 시작', `${API_BASE}/api/training/stream`)
  const eventSource = new EventSource(`${API_BASE}/api/training/stream`)

  eventSource.onopen = () => {
    console.log('[SSE] 연결 성공')
  }

  eventSource.addEventListener('progress', (event) => {
    console.log('[SSE] progress 이벤트:', event.data)
    const job = JSON.parse(event.data) as TrainingJob
    onProgress?.(job)
  })

  eventSource.addEventListener('complete', (event) => {
    console.log('[SSE] complete 이벤트:', event.data)
    const job = JSON.parse(event.data) as TrainingJob
    onComplete?.(job)
  })

  eventSource.addEventListener('status', (event) => {
    console.log('[SSE] status 이벤트:', event.data)
    const status = JSON.parse(event.data) as TrainingStatusResponse
    onStatus?.(status)
  })

  eventSource.addEventListener('ping', () => {
    console.log('[SSE] ping')
  })

  eventSource.onerror = (e) => {
    console.error('[SSE] 연결 오류:', e, eventSource.readyState)
    onError?.('Training stream connection failed')
  }

  return {
    close: () => {
      console.log('[SSE] 연결 종료')
      eventSource.close()
    }
  }
}

// SSE 스트리밍 연결
export function createDialogueStream(
  hwnd: number,
  lang: string = 'ko',
  options: {
    minConfidence?: number
    pollInterval?: number
    stabilityThreshold?: number
    onDialogue?: (event: DialogueStreamEvent) => void
    onError?: (event: DialogueStreamEvent) => void
    onStatus?: (event: DialogueStreamEvent) => void
  } = {}
): { close: () => void } {
  const {
    minConfidence = 0.2,
    pollInterval = 0.3,
    stabilityThreshold = 3,
    onDialogue,
    onError,
    onStatus,
  } = options

  const url = new URL(`${API_BASE}/api/ocr/stream/window`)
  url.searchParams.set('hwnd', hwnd.toString())
  url.searchParams.set('lang', lang)
  url.searchParams.set('min_confidence', minConfidence.toString())
  url.searchParams.set('poll_interval', pollInterval.toString())
  url.searchParams.set('stability_threshold', stabilityThreshold.toString())

  const eventSource = new EventSource(url.toString())

  eventSource.addEventListener('dialogue', (event) => {
    const data = JSON.parse(event.data) as DialogueStreamEvent
    onDialogue?.(data)
  })

  eventSource.addEventListener('error', (event) => {
    if (event instanceof MessageEvent) {
      const data = JSON.parse(event.data) as DialogueStreamEvent
      onError?.(data)
    } else {
      onError?.({ type: 'error', message: 'Connection error' })
    }
  })

  eventSource.addEventListener('status', (event) => {
    const data = JSON.parse(event.data) as DialogueStreamEvent
    onStatus?.(data)
  })

  // Heartbeat 이벤트 (연결 유지 확인용)
  eventSource.addEventListener('heartbeat', () => {
    // 연결 상태 확인용 - 로그 출력 없이 조용히 처리
  })

  eventSource.onerror = () => {
    onError?.({ type: 'error', message: 'EventSource connection failed' })
  }

  return {
    close: () => {
      eventSource.close()
    }
  }
}

// === 설정 API ===

export interface DependencyStatus {
  name: string
  installed: boolean
  version?: string
  path?: string
}

export interface SettingsResponse {
  gpt_sovits_path: string
  models_path: string
  extracted_path: string
  gamedata_path: string
  game_language: string
  voice_language: string
  gpt_sovits_language: string
  // Whisper 전처리 설정
  whisper_model_size: string
  whisper_compute_type: string
  use_whisper_preprocessing: boolean
  dependencies: DependencyStatus[]
}

export interface FFmpegInstallGuide {
  windows: {
    method: string
    command: string
    alternative: string
  }
  manual_steps: string[]
}

export interface SevenZipInstallGuide {
  windows: {
    method: string
    command: string
    alternative: string
  }
  manual_steps: string[]
  note: string
}

export interface FlatcInstallGuide {
  name: string
  description: string
  windows: {
    method: string
    command: string
    alternative: string
  }
  manual_steps: string[]
  required_for: string
}

// GPT-SoVITS 설치 관련 타입
export interface GptSovitsInstallInfo {
  is_installed: boolean
  install_path: string | null
  python_path: string | null
  gpt_sovits_path: string | null
  torch_version?: string
  cuda_available?: boolean
}

export interface InstallProgress {
  stage: 'downloading_python' | 'downloading' | 'extracting' | 'verifying' | 'complete' | 'error'
  progress: number
  message: string
  error?: string
}

export interface InstallVerifyResult {
  valid: boolean
  details: {
    python_exists: boolean
    gpt_sovits_exists: boolean
    api_script_exists: boolean
    torch_works?: boolean
    cuda_available?: boolean
  }
}

export const settingsApi = {
  // 설정 조회
  getSettings: async () => {
    const res = await api.get<SettingsResponse>('/api/settings')
    return res.data
  },

  // 의존성 상태만 확인
  checkDependencies: async () => {
    const res = await api.get<{ dependencies: DependencyStatus[] }>('/api/settings/dependencies')
    return res.data
  },

  // 폴더 열기
  openFolder: async (path: string) => {
    const res = await api.post<{ status: string }>('/api/settings/open-folder', null, {
      params: { path }
    })
    return res.data
  },

  // FFmpeg 설치 가이드
  getFFmpegGuide: async () => {
    const res = await api.get<FFmpegInstallGuide>('/api/settings/ffmpeg/install-guide')
    return res.data
  },

  // 7-Zip 설치 가이드
  get7ZipGuide: async () => {
    const res = await api.get<SevenZipInstallGuide>('/api/settings/7zip/install-guide')
    return res.data
  },

  // flatc 설치 가이드
  getFlatcGuide: async () => {
    const res = await api.get<FlatcInstallGuide>('/api/settings/flatc/install-guide')
    return res.data
  },

  // GPT-SoVITS 설치 정보 조회
  getGptSovitsInstallInfo: async () => {
    const res = await api.get<GptSovitsInstallInfo>('/api/settings/gpt-sovits/install-info')
    return res.data
  },

  // GPT-SoVITS 설치 시작
  startGptSovitsInstall: async (cudaVersion: string = 'cu121') => {
    const res = await api.post<{ status: string; message: string }>(
      '/api/settings/gpt-sovits/install',
      { cuda_version: cudaVersion }
    )
    return res.data
  },

  // GPT-SoVITS 설치 취소
  cancelGptSovitsInstall: async () => {
    const res = await api.post<{ status: string; message: string }>(
      '/api/settings/gpt-sovits/install/cancel'
    )
    return res.data
  },

  // GPT-SoVITS 설치 검증
  verifyGptSovitsInstall: async () => {
    const res = await api.get<InstallVerifyResult>('/api/settings/gpt-sovits/verify')
    return res.data
  },

  // GPT-SoVITS 설치 폴더 정리
  cleanupGptSovitsInstall: async () => {
    const res = await api.post<{ status: string; message: string }>(
      '/api/settings/gpt-sovits/cleanup'
    )
    return res.data
  },

  // GPU 세마포어 상태 조회
  getGpuSemaphore: async () => {
    const res = await api.get<{ enabled: boolean; description: string }>('/api/settings/gpu-semaphore')
    return res.data
  },

  // GPU 세마포어 설정
  setGpuSemaphore: async (enabled: boolean) => {
    const res = await api.post<{ enabled: boolean; message: string }>('/api/settings/gpu-semaphore', null, {
      params: { enabled }
    })
    return res.data
  },
}

// === 음성 추출 API ===

export interface ExtractProgress {
  stage: 'scanning' | 'extracting' | 'complete' | 'error'
  current_lang?: string
  current_file?: string
  processed: number
  total: number
  extracted: number
  message: string
  error?: string
}

export interface VoiceAssetsStatus {
  exists: boolean
  path?: string
  languages?: Record<string, number>
  total_bundles?: number
  message?: string
  hint?: string
}

export const extractApi = {
  // VoiceAssets 상태 확인
  checkVoiceAssets: async () => {
    const res = await api.get<VoiceAssetsStatus>('/api/settings/extract/check-source')
    return res.data
  },

  // 추출 상태 확인
  getStatus: async () => {
    const res = await api.get<{ status: string; message?: string; result?: Record<string, unknown> }>(
      '/api/settings/extract/status'
    )
    return res.data
  },

  // 추출 시작
  startExtract: async (languages: string[] = ['voice', 'voice_kr']) => {
    const res = await api.post<{ status: string; message: string; languages: string[] }>(
      '/api/settings/extract/start',
      { languages }
    )
    return res.data
  },

  // 추출 취소
  cancelExtract: async () => {
    const res = await api.post<{ status: string; message: string }>(
      '/api/settings/extract/cancel'
    )
    return res.data
  },

  // GPU 세마포어 설정
  getGpuSemaphore: async () => {
    const res = await api.get<{ enabled: boolean; description: string }>(
      '/api/settings/gpu-semaphore'
    )
    return res.data
  },

  setGpuSemaphore: async (enabled: boolean) => {
    const res = await api.post<{ enabled: boolean; message: string }>(
      '/api/settings/gpu-semaphore',
      null,
      { params: { enabled } }
    )
    return res.data
  },
}

// 추출 진행률 SSE 스트림
export function createExtractStream(
  options: {
    onProgress?: (progress: ExtractProgress) => void
    onComplete?: (extracted: number) => void
    onError?: (error: string) => void
  } = {}
): { close: () => void } {
  const { onProgress, onComplete, onError } = options

  console.log('[SSE] createExtractStream: 연결 시작')
  const eventSource = new EventSource(`${API_BASE}/api/settings/extract/stream`)

  eventSource.onopen = () => {
    console.log('[SSE] 추출 스트림 연결 성공')
  }

  eventSource.addEventListener('progress', (event) => {
    const progress = JSON.parse(event.data) as ExtractProgress
    onProgress?.(progress)
  })

  eventSource.addEventListener('complete', (event) => {
    const data = JSON.parse(event.data) as { success: boolean; extracted: number }
    console.log('[SSE] 추출 완료:', data)
    onComplete?.(data.extracted)
    eventSource.close()
  })

  eventSource.addEventListener('error', (event) => {
    if (event instanceof MessageEvent) {
      const data = JSON.parse(event.data)
      console.error('[SSE] 추출 에러:', data)
      onError?.(data.error || '추출 실패')
    }
    eventSource.close()
  })

  eventSource.addEventListener('ping', () => {
    // keep-alive
  })

  eventSource.onerror = (e) => {
    console.error('[SSE] 추출 스트림 연결 오류:', e)
  }

  return {
    close: () => {
      console.log('[SSE] 추출 스트림 종료')
      eventSource.close()
    }
  }
}

// GPT-SoVITS 설치 진행률 SSE 스트림
export function createInstallStream(
  options: {
    onProgress?: (progress: InstallProgress) => void
    onComplete?: () => void
    onError?: (error: string) => void
  } = {}
): { close: () => void } {
  const { onProgress, onComplete, onError } = options

  console.log('[SSE] createInstallStream: 연결 시작')
  const eventSource = new EventSource(`${API_BASE}/api/settings/gpt-sovits/install/stream`)

  eventSource.onopen = () => {
    console.log('[SSE] 설치 스트림 연결 성공')
  }

  eventSource.addEventListener('progress', (event) => {
    console.log('[SSE] 설치 progress:', event.data)
    const progress = JSON.parse(event.data) as InstallProgress
    onProgress?.(progress)
  })

  eventSource.addEventListener('complete', () => {
    console.log('[SSE] 설치 완료')
    onComplete?.()
    eventSource.close()
  })

  eventSource.addEventListener('error', (event) => {
    if (event instanceof MessageEvent) {
      const data = JSON.parse(event.data)
      console.error('[SSE] 설치 에러:', data)
      onError?.(data.error || '설치 실패')
    }
    eventSource.close()
  })

  eventSource.addEventListener('ping', () => {
    console.log('[SSE] 설치 ping')
  })

  eventSource.onerror = (e) => {
    console.error('[SSE] 설치 스트림 연결 오류:', e)
    // 연결 오류는 무시 (ping 타임아웃일 수 있음)
  }

  return {
    close: () => {
      console.log('[SSE] 설치 스트림 종료')
      eventSource.close()
    }
  }
}

// === 게임 데이터 API ===

export interface GamedataStatus {
  exists: boolean
  path: string
  server: string
  last_updated: string | null
  story_count: number
}

export interface GamedataUpdateProgress {
  stage: 'checking' | 'downloading' | 'complete' | 'error'
  progress: number
  message: string
  error?: string
}

export const gamedataApi = {
  // 게임 데이터 상태 확인
  getStatus: async (server: string = 'kr') => {
    const res = await api.get<GamedataStatus>('/api/data/status', {
      params: { server }
    })
    return res.data
  },

  // 업데이트 시작
  startUpdate: async (server: string = 'kr') => {
    const res = await api.post<{ status: string; message: string; server: string }>(
      '/api/data/update/start',
      { server }
    )
    return res.data
  },

  // 업데이트 취소
  cancelUpdate: async () => {
    const res = await api.post<{ status: string; message: string }>(
      '/api/data/update/cancel'
    )
    return res.data
  },
}

// 게임 데이터 업데이트 진행률 SSE 스트림
export function createGamedataUpdateStream(
  options: {
    onProgress?: (progress: GamedataUpdateProgress) => void
    onComplete?: () => void
    onError?: (error: string) => void
  } = {}
): { close: () => void } {
  const { onProgress, onComplete, onError } = options

  console.log('[SSE] createGamedataUpdateStream: 연결 시작')
  const eventSource = new EventSource(`${API_BASE}/api/data/update/stream`)

  eventSource.onopen = () => {
    console.log('[SSE] 게임 데이터 업데이트 스트림 연결 성공')
  }

  eventSource.addEventListener('progress', (event) => {
    const progress = JSON.parse(event.data) as GamedataUpdateProgress
    onProgress?.(progress)
  })

  eventSource.addEventListener('complete', () => {
    console.log('[SSE] 게임 데이터 업데이트 완료')
    onComplete?.()
    eventSource.close()
  })

  eventSource.addEventListener('error', (event) => {
    if (event instanceof MessageEvent) {
      const data = JSON.parse(event.data)
      console.error('[SSE] 게임 데이터 업데이트 에러:', data)
      onError?.(data.error || '업데이트 실패')
    }
    eventSource.close()
  })

  eventSource.addEventListener('ping', () => {
    // keep-alive
  })

  eventSource.onerror = (e) => {
    console.error('[SSE] 게임 데이터 업데이트 스트림 연결 오류:', e)
  }

  return {
    close: () => {
      console.log('[SSE] 게임 데이터 업데이트 스트림 종료')
      eventSource.close()
    }
  }
}

export default api
