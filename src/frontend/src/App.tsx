import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAppStore } from './stores/appStore'
import EpisodeSelector from './components/EpisodeSelector'
import DialogueViewer from './components/DialogueViewer'
import VoiceSetupPanel from './components/VoiceSetupPanel'
import GroupSetupPanel from './components/GroupSetupPanel'
import DubbingDashboard from './components/DubbingDashboard'
import DubbingControlBar from './components/DubbingControlBar'
import StatusBar from './components/StatusBar'
import SettingsModal from './components/SettingsModal'
import CharacterManagerModal from './components/CharacterManagerModal'
import LanguageSettingsModal from './components/LanguageSettingsModal'

function App() {
  const {
    selectedEpisode,
    selectedEpisodeId,
    selectedGroupId,
    backendStatus,
    checkBackendStatus,
    categories,
    selectedCategoryId,
    selectCategory,
    isLoadingCategories,
    loadCategories,
    isDubbingMode,
    isPrepared,
    prepareForDubbing,
    isLoadingCharacters,
    // GPT-SoVITS
    gptSovitsStatus,
    isStartingGptSovits,
    gptSovitsError,
    checkGptSovitsStatus,
    startGptSovits,
    // TTS 엔진 설정
    defaultTtsEngine,
    loadTtsEngineSetting,
    // GPU 세마포어
    gpuSemaphoreEnabled,
    loadGpuSemaphoreStatus,
    toggleGpuSemaphore,
    // 음성 캐릭터
    loadVoiceCharacters,
    loadVoiceMappings,
    // 언어 설정
    loadLanguageSettings,
    voiceLanguage,
    // 패널 접기
    isLeftPanelCollapsed,
    isRightPanelCollapsed,
    toggleLeftPanel,
    toggleRightPanel,
    // 에피소드 선택 해제
    clearEpisode,
    goHome,
    // 전체 새로고침
    isRefreshingAll,
    refreshAll,
  } = useAppStore()

  const { t } = useTranslation()

  useEffect(() => {
    checkBackendStatus()
    const interval = setInterval(checkBackendStatus, 10000)
    return () => clearInterval(interval)
  }, [checkBackendStatus])

  useEffect(() => {
    if (backendStatus === 'connected') {
      loadCategories()
      checkGptSovitsStatus()
      loadTtsEngineSetting()  // TTS 엔진 설정 로드
      loadVoiceCharacters()  // 음성 캐릭터 목록 로드 (getSpeakerVoice에서 사용)
      loadVoiceMappings()  // 백엔드 음성 매핑 로드 (에피소드 전환 시 유지)
      loadGpuSemaphoreStatus()  // GPU 세마포어 상태 로드
      loadLanguageSettings()  // 언어 설정 로드
    }
  }, [backendStatus, loadCategories, checkGptSovitsStatus, loadTtsEngineSetting, loadVoiceCharacters, loadVoiceMappings, loadGpuSemaphoreStatus, loadLanguageSettings])

  // GPT-SoVITS 상태 주기적 확인 (30초)
  useEffect(() => {
    if (backendStatus !== 'connected') return
    const interval = setInterval(checkGptSovitsStatus, 30000)
    return () => clearInterval(interval)
  }, [backendStatus, checkGptSovitsStatus])

  // 설정 모달 상태
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)

  // 캐릭터 관리 모달 상태
  const [isCharacterManagerOpen, setIsCharacterManagerOpen] = useState(false)

  // 언어 설정 모달 상태
  const [isLanguageSettingsOpen, setIsLanguageSettingsOpen] = useState(false)

  // 준비 버튼 핸들러
  const handlePrepare = () => {
    if (!selectedGroupId) {
      alert(t('app.alert.selectGroup'))
      return
    }
    prepareForDubbing()
  }

  return (
    <div className="flex flex-col h-screen bg-ark-black">
      {/* 헤더 */}
      <header className="ark-header relative px-6 py-4 flex items-center justify-between">
        <button
          onClick={goHome}
          className="flex items-center gap-3 hover:opacity-80 transition-opacity"
          title={t('app.header.homeTitle')}
        >
          {/* 로고 아이콘 */}
          <div className="w-8 h-8 flex items-center justify-center">
            <svg viewBox="0 0 24 24" className="w-6 h-6 text-ark-orange" fill="currentColor">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
                    stroke="currentColor" strokeWidth="2" fill="none"/>
            </svg>
          </div>
          <h1 className="text-xl font-bold text-ark-white tracking-wide">
            <span className="text-ark-orange">ArkSynth</span>
            <span className="text-ark-gray mx-2">|</span>
            <span className="text-sm font-normal">ARKNIGHTS STORY VOICE</span>
          </h1>
        </button>
        <div className="flex items-center gap-4">
          {/* 더빙 상태 표시 */}
          {isDubbingMode && (
            <div className="ark-btn-dual ark-corner-cut-sm flex items-center gap-2 px-4 py-2">
              <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.91-3c-.49 0-.9.36-.98.85C16.52 14.2 14.47 16 12 16s-4.52-1.8-4.93-4.15c-.08-.49-.49-.85-.98-.85-.61 0-1.09.54-1 1.14.49 3 2.89 5.35 5.91 5.78V20c0 .55.45 1 1 1s1-.45 1-1v-2.08c3.02-.43 5.42-2.78 5.91-5.78.1-.6-.39-1.14-1-1.14z"/>
              </svg>
              <span>{t('app.header.dubbing')}</span>
              <span className="w-2 h-2 bg-ark-black ark-pulse" style={{clipPath: 'polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)'}} />
            </div>
          )}

          {/* GPT-SoVITS 상태 - 기본 엔진일 때만 강조 */}
          {defaultTtsEngine === 'gpt_sovits' && (
            <div className="flex items-center gap-2">
              {gptSovitsStatus?.api_running ? (
                gptSovitsStatus?.synthesizing ? (
                  <>
                    <span className="w-2 h-2 rounded-full bg-ark-cyan ark-pulse-cyan" />
                    <span className="text-sm text-ark-cyan">{t('app.gpt.synthesizing')}</span>
                  </>
                ) : (
                  <>
                    <span className="w-2 h-2 rounded-full bg-ark-cyan" />
                    <span className="text-sm text-ark-cyan">{t('app.gpt.label')}</span>
                  </>
                )
              ) : gptSovitsStatus?.installed ? (
                <button
                  onClick={startGptSovits}
                  disabled={isStartingGptSovits}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-lg shadow-orange-500/30 hover:from-amber-400 hover:to-orange-400 hover:shadow-orange-500/50 transition-all animate-pulse hover:animate-none disabled:opacity-50 disabled:animate-none"
                >
                  {isStartingGptSovits ? (
                    <span>{t('app.gpt.starting')}</span>
                  ) : (
                    <>
                      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                        <path d="M8 5v14l11-7z"/>
                      </svg>
                      <span>{t('app.gpt.startButton')}</span>
                    </>
                  )}
                </button>
              ) : gptSovitsStatus !== null ? (
                <div className="flex items-center gap-1.5 text-sm text-red-400">
                  <span className="w-2 h-2 rounded-full bg-red-500" />
                  <span>{t('app.gpt.notInstalled')}</span>
                </div>
              ) : null}
              {gptSovitsError && (
                <span className="text-xs text-red-400" title={gptSovitsError}>
                  {t('common.error')}
                </span>
              )}
            </div>
          )}

          {/* GPU 세마포어 토글 */}
          <button
            onClick={toggleGpuSemaphore}
            className={`flex items-center gap-1.5 px-2 py-1 text-xs rounded transition-colors ${
              gpuSemaphoreEnabled
                ? 'bg-ark-gray/30 text-ark-gray hover:bg-ark-gray/40'
                : 'bg-ark-orange/20 text-ark-orange hover:bg-ark-orange/30'
            }`}
            title={gpuSemaphoreEnabled
              ? t('app.gpu.lockEnabled')
              : t('app.gpu.lockDisabled')
            }
          >
            <svg viewBox="0 0 24 24" className="w-3.5 h-3.5" fill="currentColor">
              {gpuSemaphoreEnabled ? (
                <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/>
              ) : (
                <path d="M12 17c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm6-9h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6h1.9c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm0 12H6V10h12v10z"/>
              )}
            </svg>
            <span>{t('app.gpu.label')}</span>
          </button>

          {/* 백엔드 상태 */}
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${
              backendStatus === 'connected' ? 'bg-ark-cyan' : 'bg-red-500'
            }`} />
            <span className={`text-sm ${
              backendStatus === 'connected' ? 'text-ark-cyan' : 'text-red-400'
            }`}>
              {backendStatus === 'connected' ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>

          {/* 언어 설정 버튼 */}
          <button
            onClick={() => setIsLanguageSettingsOpen(true)}
            className="flex items-center gap-1.5 px-2 py-1.5 text-ark-gray hover:text-ark-white border border-ark-border hover:border-ark-cyan/50 rounded transition-colors"
            title={t('languageSettings.title')}
          >
            <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
              <path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zm6.93 6h-2.95c-.32-1.25-.78-2.45-1.38-3.56 1.84.63 3.37 1.91 4.33 3.56zM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82c.43-1.43 1.08-2.76 1.91-3.96zM4.26 14C4.1 13.36 4 12.69 4 12s.1-1.36.26-2h3.38c-.08.66-.14 1.32-.14 2 0 .68.06 1.34.14 2H4.26zm.82 2h2.95c.32 1.25.78 2.45 1.38 3.56-1.84-.63-3.37-1.9-4.33-3.56zm2.95-8H5.08c.96-1.66 2.49-2.93 4.33-3.56C8.81 5.55 8.35 6.75 8.03 8zM12 19.96c-.83-1.2-1.48-2.53-1.91-3.96h3.82c-.43 1.43-1.08 2.76-1.91 3.96zM14.34 14H9.66c-.09-.66-.16-1.32-.16-2 0-.68.07-1.35.16-2h4.68c.09.65.16 1.32.16 2 0 .68-.07 1.34-.16 2zm.25 5.56c.6-1.11 1.06-2.31 1.38-3.56h2.95c-.96 1.65-2.49 2.93-4.33 3.56zM16.36 14c.08-.66.14-1.32.14-2 0-.68-.06-1.34-.14-2h3.38c.16.64.26 1.31.26 2s-.1 1.36-.26 2h-3.38z"/>
            </svg>
            <span className="text-xs uppercase">{voiceLanguage}</span>
          </button>

          {/* 새로고침 버튼 */}
          <button
            onClick={refreshAll}
            disabled={isRefreshingAll}
            className="flex items-center gap-1.5 px-2 py-1.5 text-ark-gray hover:text-ark-white border border-ark-border hover:border-ark-cyan/50 rounded transition-colors disabled:opacity-50"
            title={t('app.refreshAll')}
          >
            <svg viewBox="0 0 24 24" className={`w-4 h-4 ${isRefreshingAll ? 'animate-spin' : ''}`} fill="currentColor">
              <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
            </svg>
          </button>

          {/* 설정 버튼 */}
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-ark-gray hover:text-ark-white border border-ark-border hover:border-ark-cyan/50 rounded transition-colors"
            title={t('app.settings')}
          >
            <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
              <path d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
            </svg>
            <span className="text-xs">{t('app.settings')}</span>
          </button>
        </div>
      </header>

      {/* 카테고리 탭 */}
      <div className="flex border-b border-ark-border bg-ark-dark">
        <div className="flex-1 flex overflow-x-auto">
          {isLoadingCategories ? (
            <div className="p-3 text-ark-gray text-sm ark-pulse">{t('common.loading')}</div>
          ) : (
            categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => selectCategory(cat.id)}
                className={`px-5 py-3 text-sm font-medium whitespace-nowrap transition-all border-b-2 ${
                  selectedCategoryId === cat.id
                    ? 'bg-ark-orange/10 text-ark-orange border-ark-orange'
                    : 'text-ark-gray hover:text-ark-white hover:bg-ark-panel/50 border-transparent'
                }`}
              >
                {cat.name}
                <span className="ml-1.5 text-xs opacity-70">({cat.group_count})</span>
              </button>
            ))
          )}
        </div>

        {/* 캐릭터 관리 버튼 */}
        <button
          onClick={() => setIsCharacterManagerOpen(true)}
          className="px-4 py-2 text-ark-orange hover:bg-ark-orange/10 flex items-center gap-2 border-l border-ark-border transition-colors"
        >
          <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
            <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
          </svg>
          <span className="text-sm font-medium">{t('app.header.characterManagement')}</span>
        </button>
      </div>

      {/* 백엔드 미연결 안내 */}
      {backendStatus === 'disconnected' && (
        <div className="flex-1 flex items-center justify-center bg-ark-black">
          <div className="text-center max-w-md mx-auto p-8">
            <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-red-500/10 flex items-center justify-center">
              <svg viewBox="0 0 24 24" className="w-8 h-8 text-red-400" fill="currentColor">
                <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
              </svg>
            </div>
            <h2 className="text-lg font-bold text-ark-white mb-2">{t('app.error.backendNotConnected')}</h2>
            <p className="text-sm text-ark-gray mb-6">
              <span className="text-ark-orange font-mono">{t('app.error.startBatFile')}</span>으로 앱을 실행해주세요.
              <br />
              {t('app.error.startBatDescription')}
            </p>
            <div className="p-3 bg-ark-panel/50 rounded border border-ark-border text-xs text-ark-gray/70 font-mono">
              {t('app.error.serverAddress')}
            </div>
            <p className="mt-4 text-xs text-ark-gray/50">{t('app.error.autoConnect')}</p>
          </div>
        </div>
      )}

      {/* 메인 컨텐츠 */}
      {backendStatus !== 'disconnected' && <main className={`flex-1 flex flex-col overflow-hidden transition-all ${
        isDubbingMode ? 'pb-16' : ''
      }`}>
        <div className="flex-1 flex overflow-hidden">
          {/* 왼쪽: 에피소드 목록 */}
          <aside className={`bg-ark-dark border-r border-ark-border overflow-hidden transition-all duration-300 ${
            isLeftPanelCollapsed ? 'w-0' : 'w-80'
          }`}>
            <div className="w-80 h-full overflow-y-auto">
              <EpisodeSelector />
            </div>
          </aside>

          {/* 왼쪽 패널 토글 버튼 */}
          <button
            onClick={toggleLeftPanel}
            className="flex-shrink-0 w-5 bg-ark-dark hover:bg-ark-panel border-r border-ark-border flex items-center justify-center text-ark-gray hover:text-ark-white transition-colors"
            title={isLeftPanelCollapsed ? t('app.panel.expandEpisodeList') : t('app.panel.collapseEpisodeList')}
          >
            <svg viewBox="0 0 24 24" className={`w-4 h-4 transition-transform duration-300 ${isLeftPanelCollapsed ? '' : 'rotate-180'}`} fill="currentColor">
              <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/>
            </svg>
          </button>

          {/* 중앙: 대사 뷰어 */}
          <section className="flex-1 overflow-y-auto bg-ark-black ark-pattern">
            {selectedEpisode ? (
              <DialogueViewer />
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-ark-gray">
                <svg viewBox="0 0 24 24" className="w-16 h-16 mb-4 opacity-30" fill="currentColor">
                  <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
                </svg>
                <p>{t('app.content.selectEpisode')}</p>
                {!selectedGroupId && (
                  <p className="mt-2 text-sm text-ark-gray/70">
                    {t('app.content.selectEpisodeGuide')}
                  </p>
                )}
              </div>
            )}
          </section>

          {/* 오른쪽 패널 토글 버튼 */}
          <button
            onClick={toggleRightPanel}
            className="flex-shrink-0 w-5 bg-ark-dark hover:bg-ark-panel border-l border-ark-border flex items-center justify-center text-ark-gray hover:text-ark-white transition-colors"
            title={isRightPanelCollapsed ? t('app.panel.expandSettings') : t('app.panel.collapseSettings')}
          >
            <svg viewBox="0 0 24 24" className={`w-4 h-4 transition-transform duration-300 ${isRightPanelCollapsed ? 'rotate-180' : ''}`} fill="currentColor">
              <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/>
            </svg>
          </button>

          {/* 오른쪽: 조건부 패널 */}
          <aside className={`bg-ark-dark border-l border-ark-border overflow-hidden transition-all duration-300 flex flex-col ${
            isRightPanelCollapsed ? 'w-0' : 'w-[400px]'
          }`}>
            <div className="w-[400px] h-full overflow-y-auto flex flex-col">
              {selectedGroupId ? (
                selectedEpisodeId ? (
                  isPrepared ? (
                    <VoiceSetupPanel />
                  ) : (
                    <div className="flex flex-col h-full">
                      {/* 더빙 준비 버튼 */}
                      <div className="p-4 border-b border-ark-border bg-ark-panel/50">
                        <button
                          onClick={handlePrepare}
                          disabled={isLoadingCharacters}
                          className={`w-full flex items-center justify-center gap-2 px-4 py-3 ark-corner-cut font-bold transition-all ${
                            !isLoadingCharacters
                              ? 'ark-btn-dual'
                              : 'bg-ark-panel border border-ark-border text-ark-gray/50 cursor-not-allowed'
                          }`}
                        >
                          {isLoadingCharacters ? (
                            <span className="ark-pulse">{t('common.loading')}</span>
                          ) : (
                            <>
                              <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                                <path d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
                              </svg>
                              <span>{t('app.dubbing.episodeSetup')}</span>
                            </>
                          )}
                        </button>
                        {!isLoadingCharacters && <div className="ark-scan-bar mt-1 rounded-full" />}
                      </div>
                      <div className="flex-1 p-4 space-y-4">
                        <p className="text-xs text-ark-gray text-center">
                          {t('app.dubbing.setupGuide')}
                        </p>
                        <button
                          onClick={clearEpisode}
                          className="w-full ark-btn text-sm text-ark-cyan hover:text-ark-white border-ark-cyan/30"
                        >
                          {t('app.panel.backToGroupSetup')}
                        </button>
                      </div>
                    </div>
                  )
                ) : (
                  <GroupSetupPanel />
                )
              ) : (
                <div className="flex flex-col h-full">
                  <div className="flex-1 p-4 space-y-4 overflow-y-auto">

                    {/* 앱 소개 */}
                    <div className="text-center py-2">
                      <h3 className="text-base font-bold text-ark-orange tracking-wide">{t('app.title')}</h3>
                      <p className="text-xs text-ark-gray mt-1">{t('app.description')}</p>
                    </div>

                    {/* 카드 1: 처음 설치 가이드 */}
                    <div className="ark-warning-box ark-corner-cut text-xs text-ark-gray space-y-2.5">
                      <h4 className="font-medium text-ark-orange flex items-center gap-2">
                        <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                          <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
                        </svg>
                        {t('app.home.installGuide')}
                      </h4>
                      <p>{t('app.home.openSettings')}</p>

                      <div className="space-y-2">
                        <div className="flex items-start gap-2">
                          <span className="flex-shrink-0 w-4 h-4 rounded-full bg-ark-orange/20 text-ark-orange text-[10px] font-bold flex items-center justify-center mt-0.5">1</span>
                          <div>
                            <p className="text-ark-white font-medium">{t('app.home.dependencies')}</p>
                            <p className="text-ark-gray/80">{t('app.home.dependenciesDesc')}</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="flex-shrink-0 w-4 h-4 rounded-full bg-ark-orange/20 text-ark-orange text-[10px] font-bold flex items-center justify-center mt-0.5">2</span>
                          <div>
                            <p className="text-ark-white font-medium">{t('app.home.copyAssets')}</p>
                            <p className="text-ark-gray/80">{t('app.home.copyAssetsDesc')}</p>
                            <div className="mt-1 space-y-0.5 text-[10px] text-ark-gray/60">
                              <p>{t('app.home.voicePath')}</p>
                              <p>{t('app.home.imagePath')}</p>
                              <p className="ml-[38px]">{t('app.home.charartPath')}</p>
                            </div>
                          </div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="flex-shrink-0 w-4 h-4 rounded-full bg-ark-orange/20 text-ark-orange text-[10px] font-bold flex items-center justify-center mt-0.5">3</span>
                          <div>
                            <p className="text-ark-white font-medium">{t('app.home.extractAssets')}</p>
                            <p className="text-ark-gray/80">{t('app.home.extractAssetsDesc')}</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="flex-shrink-0 w-4 h-4 rounded-full bg-ark-orange/20 text-ark-orange text-[10px] font-bold flex items-center justify-center mt-0.5">4</span>
                          <div>
                            <p className="text-ark-white font-medium">{t('app.home.storyData')}</p>
                            <p className="text-ark-gray/80">{t('app.home.storyDataDesc')}</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="flex-shrink-0 w-4 h-4 rounded-full bg-ark-orange/20 text-ark-orange text-[10px] font-bold flex items-center justify-center mt-0.5">5</span>
                          <div>
                            <p className="text-ark-white font-medium">{t('app.home.dataMapping')}</p>
                            <p className="text-ark-gray/80">{t('app.home.dataMappingDesc')}</p>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* 카드 2: 사용 방법 */}
                    <div className="ark-info-box ark-corner-cut text-xs text-ark-gray space-y-2.5">
                      <h4 className="font-medium text-ark-cyan flex items-center gap-2">
                        <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
                        </svg>
                        {t('app.home.howToUse')}
                      </h4>

                      <div className="space-y-2">
                        <div className="flex items-start gap-2">
                          <span className="flex-shrink-0 w-4 h-4 rounded-full bg-ark-cyan/20 text-ark-cyan text-[10px] font-bold flex items-center justify-center mt-0.5">1</span>
                          <div>
                            <p className="text-ark-white font-medium">{t('app.home.startGptSovits')}</p>
                            <p className="text-ark-gray/80">{t('app.home.startGptSovitsDesc')}</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="flex-shrink-0 w-4 h-4 rounded-full bg-ark-cyan/20 text-ark-cyan text-[10px] font-bold flex items-center justify-center mt-0.5">2</span>
                          <div>
                            <p className="text-ark-white font-medium">{t('app.home.characterManagement')}</p>
                            <p className="text-ark-gray/80">{t('app.home.characterManagementDesc')}</p>
                            <p className="text-ark-gray/60 mt-0.5">{t('app.home.characterManagementGuide')}</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="flex-shrink-0 w-4 h-4 rounded-full bg-ark-cyan/20 text-ark-cyan text-[10px] font-bold flex items-center justify-center mt-0.5">3</span>
                          <div>
                            <p className="text-ark-white font-medium">{t('app.home.selectStory')}</p>
                            <p className="text-ark-gray/80">{t('app.home.selectStoryDesc')}</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="flex-shrink-0 w-4 h-4 rounded-full bg-ark-cyan/20 text-ark-cyan text-[10px] font-bold flex items-center justify-center mt-0.5">4</span>
                          <div>
                            <p className="text-ark-white font-medium">{t('app.home.voiceMappingSetup')}</p>
                            <p className="text-ark-gray/80">{t('app.home.voiceMappingDesc')}</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="flex-shrink-0 w-4 h-4 rounded-full bg-ark-cyan/20 text-ark-cyan text-[10px] font-bold flex items-center justify-center mt-0.5">5</span>
                          <div>
                            <p className="text-ark-white font-medium">{t('app.home.voicePreparation')}</p>
                            <p className="text-ark-gray/80">{t('app.home.voicePreparationDesc')}</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="flex-shrink-0 w-4 h-4 rounded-full bg-ark-cyan/20 text-ark-cyan text-[10px] font-bold flex items-center justify-center mt-0.5">6</span>
                          <div>
                            <p className="text-ark-white font-medium">{t('app.home.realtimeDubbing')}</p>
                            <p className="text-ark-gray/80">{t('app.home.realtimeDubbingDesc')}</p>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* 참고 팁 */}
                    <div className="p-3 bg-ark-panel/50 rounded border border-ark-border text-[11px] text-ark-gray space-y-1.5">
                      <p>{t('app.home.zeroShotNote')}</p>
                      <p>{t('app.home.gpuNote')}</p>
                    </div>

                    {/* 오류 신고 안내 */}
                    <div className="p-3 bg-ark-panel/50 rounded border border-ark-border text-[11px] text-ark-gray space-y-1.5">
                      <p className="text-ark-white font-medium">{t('app.home.troubleshooting')}</p>
                      <p>{t('app.home.troubleshootingDesc')}</p>
                      <p className="text-ark-gray/60">{t('app.home.logsLocation')}</p>
                      <a
                        href="https://github.com/grasp-pixel/ArkSynth/issues"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-block text-ark-cyan hover:underline"
                      >
                        GitHub Issues
                      </a>
                    </div>

                  </div>
                </div>
              )}
            </div>
          </aside>
        </div>
      </main>}

      {/* 더빙 대시보드 (더빙 모드 시 하단 고정) */}
      <DubbingDashboard />

      {/* 더빙 컨트롤 바 (준비됨 상태 시 하단 고정) */}
      <DubbingControlBar />

      {/* 상태 바 */}
      <StatusBar onOpenSettings={() => setIsSettingsOpen(true)} />

      {/* 설정 모달 */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />

      {/* 캐릭터 관리 모달 */}
      <CharacterManagerModal
        isOpen={isCharacterManagerOpen}
        onClose={() => setIsCharacterManagerOpen(false)}
      />

      {/* 언어 설정 모달 */}
      <LanguageSettingsModal
        isOpen={isLanguageSettingsOpen}
        onClose={() => setIsLanguageSettingsOpen(false)}
      />
    </div>
  )
}

export default App
