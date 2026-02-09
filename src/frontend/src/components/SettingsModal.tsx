import { useEffect, useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useAppStore } from "../stores/appStore";
import {
  settingsApi,
  extractApi,
  createExtractStream,
  imageExtractApi,
  createImageExtractStream,
  createFFmpegInstallStream,
  gamedataApi,
  createGamedataUpdateStream,
  voiceApi,
  ttsApi,
  aliasesApi,
  type SettingsResponse,
  type DependencyStatus,
  type FFmpegInstallGuide,
  type SevenZipInstallGuide,
  type FlatcInstallGuide,
  type VoiceAssetsStatus,
  type ExtractProgress,
  type ImageAssetsStatus,
  type ImageExtractProgress,
  type GamedataStatus,
  type GamedataUpdateProgress,
  type AliasListResponse,
} from "../services/api";
import GPTSoVITSInstallDialog from "./GPTSoVITSInstallDialog";

/** 게임 데이터 다운로드 대상 서버 목록 */
const GAMEDATA_SERVERS = [
  { server: 'kr', label: '한국어' },
  { server: 'jp', label: '日本語' },
  { server: 'en', label: 'English' },
] as const;

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { t } = useTranslation();
  const { voiceFolder, loadLanguageSettings } = useAppStore();
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [ffmpegGuide, setFFmpegGuide] = useState<FFmpegInstallGuide | null>(
    null,
  );
  const [sevenZipGuide, setSevenZipGuide] =
    useState<SevenZipInstallGuide | null>(null);
  const [flatcGuide, setFlatcGuide] = useState<FlatcInstallGuide | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showFFmpegGuide, setShowFFmpegGuide] = useState(false);
  const [show7ZipGuide, setShow7ZipGuide] = useState(false);
  const [showFlatcGuide, setShowFlatcGuide] = useState(false);
  const [showGptSovitsInstall, setShowGptSovitsInstall] = useState(false);
  const [isInstallingFFmpeg, setIsInstallingFFmpeg] = useState(false);
  const [ffmpegInstallMsg, setFFmpegInstallMsg] = useState<string | null>(null);
  const [ffmpegInstallError, setFFmpegInstallError] = useState<string | null>(null);
  const ffmpegInstallStreamRef = useRef<{ close: () => void } | null>(null);
  const [isRefreshingCharacters, setIsRefreshingCharacters] = useState(false);

  // 음성 추출 관련 상태
  const [voiceAssetsStatus, setVoiceAssetsStatus] =
    useState<VoiceAssetsStatus | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractProgress, setExtractProgress] =
    useState<ExtractProgress | null>(null);
  const [extractError, setExtractError] = useState<string | null>(null);
  const extractStreamRef = useRef<{ close: () => void } | null>(null);

  // 이미지 추출 관련 상태
  const [imageAssetsStatus, setImageAssetsStatus] =
    useState<ImageAssetsStatus | null>(null);
  const [isExtractingImages, setIsExtractingImages] = useState(false);
  const [extractingImageTarget, setExtractingImageTarget] = useState<'characters' | 'chararts' | null>(null);
  const [imageExtractProgress, setImageExtractProgress] =
    useState<ImageExtractProgress | null>(null);
  const [imageExtractError, setImageExtractError] = useState<string | null>(
    null,
  );
  const imageExtractStreamRef = useRef<{ close: () => void } | null>(null);

  // 게임 데이터 업데이트 관련 상태 (언어별 독립)
  const [gamedataStatuses, setGamedataStatuses] = useState<Record<string, GamedataStatus | null>>({});
  const [updatingServer, setUpdatingServer] = useState<string | null>(null);
  const [gamedataUpdateProgress, setGamedataUpdateProgress] =
    useState<GamedataUpdateProgress | null>(null);
  const [gamedataUpdateError, setGamedataUpdateError] = useState<{ server: string; error: string } | null>(null);
  const [lastCompletedServer, setLastCompletedServer] = useState<string | null>(null);
  const gamedataStreamRef = useRef<{ close: () => void } | null>(null);
  const [gamedataRepo, setGamedataRepo] = useState('');
  const [gamedataRepoInput, setGamedataRepoInput] = useState('');
  const [isRepoSaving, setIsRepoSaving] = useState(false);
  const [gamedataSource, setGamedataSource] = useState<string>('arkprts');

  // 별칭 추출 관련 상태
  const [aliasesInfo, setAliasesInfo] = useState<AliasListResponse | null>(null);
  const [isExtractingAliases, setIsExtractingAliases] = useState(false);
  const [aliasExtractResult, setAliasExtractResult] = useState<{
    success: boolean;
    extracted_count: number;
    alias_count: number;
  } | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadSettings();
      loadLanguageSettings();
      checkVoiceAssets();
      checkImageAssets();
      checkAllGamedataStatuses();
      loadGamedataSource();
      loadAliasesInfo();
    }
    return () => {
      // 모달 닫힐 때 스트림 정리
      extractStreamRef.current?.close();
      imageExtractStreamRef.current?.close();
      gamedataStreamRef.current?.close();
    };
  }, [isOpen]);

  const loadSettings = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await settingsApi.getSettings();
      setSettings(data);
    } catch (err) {
      setError(t('settings.loadFailed'));
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const loadFFmpegGuide = async () => {
    try {
      const guide = await settingsApi.getFFmpegGuide();
      setFFmpegGuide(guide);
      setShowFFmpegGuide(true);
    } catch (err) {
      console.error(err);
    }
  };

  const startFFmpegInstall = async () => {
    setIsInstallingFFmpeg(true);
    setFFmpegInstallMsg(t('settings.ffmpeg.installing'));
    setFFmpegInstallError(null);
    try {
      await settingsApi.startFFmpegInstall();
      ffmpegInstallStreamRef.current = createFFmpegInstallStream({
        onProgress: (p) => setFFmpegInstallMsg(p.message),
        onComplete: () => {
          setIsInstallingFFmpeg(false);
          setFFmpegInstallMsg(t('settings.ffmpeg.installed'));
          loadSettings();
        },
        onError: (error) => {
          setIsInstallingFFmpeg(false);
          setFFmpegInstallError(error);
          setFFmpegInstallMsg(null);
        },
      });
    } catch (err) {
      setIsInstallingFFmpeg(false);
      setFFmpegInstallError(err instanceof Error ? err.message : t('settings.ffmpeg.startFailed'));
    }
  };

  const load7ZipGuide = async () => {
    try {
      const guide = await settingsApi.get7ZipGuide();
      setSevenZipGuide(guide);
      setShow7ZipGuide(true);
    } catch (err) {
      console.error(err);
    }
  };

  const loadFlatcGuide = async () => {
    try {
      const guide = await settingsApi.getFlatcGuide();
      setFlatcGuide(guide);
      setShowFlatcGuide(true);
    } catch (err) {
      console.error(err);
    }
  };

  const refreshCharacterData = async () => {
    setIsRefreshingCharacters(true);
    try {
      await voiceApi.refresh();
    } catch (err) {
      console.error(t('settings.characters.refreshFailed'), err);
    } finally {
      setIsRefreshingCharacters(false);
    }
  };

  const handleOpenFolder = async (path: string) => {
    try {
      await settingsApi.openFolder(path);
    } catch (err) {
      console.error(t('settings.folder.openFailed'), err);
    }
  };

  const checkVoiceAssets = async () => {
    try {
      const status = await extractApi.checkVoiceAssets();
      setVoiceAssetsStatus(status);
    } catch (err) {
      console.error(t('settings.voice.checkFailed'), err);
    }
  };

  const checkImageAssets = async () => {
    try {
      const status = await imageExtractApi.checkImageAssets();
      setImageAssetsStatus(status);
    } catch (err) {
      console.error(t('settings.image.checkFailed'), err);
    }
  };

  const startImageExtraction = async (target: 'characters' | 'chararts') => {
    const folderReady = target === 'characters'
      ? imageAssetsStatus?.characters_exists
      : imageAssetsStatus?.chararts_exists;
    if (!imageAssetsStatus?.exists || !folderReady) return;

    setIsExtractingImages(true);
    setExtractingImageTarget(target);
    setImageExtractProgress(null);
    setImageExtractError(null);

    try {
      await imageExtractApi.startExtract(target);

      imageExtractStreamRef.current = createImageExtractStream({
        onProgress: (progress) => {
          setImageExtractProgress(progress);
        },
        onComplete: (extracted) => {
          setIsExtractingImages(false);
          setImageExtractProgress({
            stage: "complete",
            processed: 0,
            total: 0,
            extracted,
            message: t('settings.image.extractComplete', { count: extracted }),
          });
        },
        onError: (error) => {
          setIsExtractingImages(false);
          setImageExtractError(error);
        },
      });
    } catch (err) {
      setIsExtractingImages(false);
      setImageExtractError(
        err instanceof Error ? err.message : t('settings.image.startFailed'),
      );
    }
  };

  const cancelImageExtraction = async () => {
    try {
      await imageExtractApi.cancelExtract();
      imageExtractStreamRef.current?.close();
      setIsExtractingImages(false);
      setImageExtractProgress(null);
    } catch (err) {
      console.error(t('settings.image.cancelFailed'), err);
    }
  };

  const checkAllGamedataStatuses = async () => {
    const results: Record<string, GamedataStatus | null> = {};
    await Promise.all(
      GAMEDATA_SERVERS.map(async ({ server }) => {
        try {
          results[server] = await gamedataApi.getStatus(server);
        } catch {
          results[server] = null;
        }
      }),
    );
    setGamedataStatuses(results);
  };

  const loadGamedataSource = async () => {
    try {
      const { source, repo } = await gamedataApi.getSource();
      setGamedataSource(source);
      setGamedataRepo(repo);
      setGamedataRepoInput(repo);
    } catch (err) {
      console.error(t('settings.gamedata.loadSourceFailed'), err);
    }
  };

  const changeGamedataSource = async (newSource: string) => {
    try {
      await gamedataApi.setSource(newSource);
      setGamedataSource(newSource);
    } catch (err) {
      console.error(t('settings.gamedata.changeSourceFailed'), err);
    }
  };

  const saveGamedataRepo = async () => {
    if (!gamedataRepoInput.trim() || gamedataRepoInput === gamedataRepo) return;
    setIsRepoSaving(true);
    try {
      await gamedataApi.setRepo(gamedataRepoInput.trim());
      setGamedataRepo(gamedataRepoInput.trim());
    } catch (err) {
      console.error(t('settings.gamedata.saveRepoFailed'), err);
    } finally {
      setIsRepoSaving(false);
    }
  };

  const loadAliasesInfo = async () => {
    try {
      const info = await aliasesApi.listAliases();
      setAliasesInfo(info);
    } catch (err) {
      console.error(t('settings.aliases.loadFailed'), err);
    }
  };

  const handleExtractAliases = async () => {
    setIsExtractingAliases(true);
    setAliasExtractResult(null);
    try {
      const result = await aliasesApi.extractRealnames(false);
      setAliasExtractResult({
        success: result.success,
        extracted_count: result.extracted_count,
        alias_count: result.alias_count,
      });
      // 별칭 목록 새로고침
      await loadAliasesInfo();
    } catch (err) {
      console.error(t('settings.aliases.extractFailed'), err);
    } finally {
      setIsExtractingAliases(false);
    }
  };

  const startGamedataUpdate = async (server: string) => {
    setUpdatingServer(server);
    setGamedataUpdateProgress(null);
    setGamedataUpdateError(null);
    setLastCompletedServer(null);

    try {
      await gamedataApi.startUpdate(server);

      // SSE 스트림 연결
      gamedataStreamRef.current = createGamedataUpdateStream({
        onProgress: (progress) => {
          setGamedataUpdateProgress(progress);
        },
        onComplete: () => {
          setUpdatingServer(null);
          setLastCompletedServer(server);
          setGamedataUpdateProgress({
            stage: "complete",
            progress: 1,
            message: t('settings.gamedata.updateComplete'),
          });
          checkAllGamedataStatuses();
          loadSettings();
        },
        onError: (error) => {
          setUpdatingServer(null);
          setGamedataUpdateError({ server, error });
        },
      });
    } catch (err) {
      setUpdatingServer(null);
      setGamedataUpdateError({
        server,
        error: err instanceof Error ? err.message : t('settings.gamedata.startFailed'),
      });
    }
  };

  const cancelGamedataUpdate = async () => {
    try {
      await gamedataApi.cancelUpdate();
      gamedataStreamRef.current?.close();
      setUpdatingServer(null);
      setGamedataUpdateProgress(null);
    } catch (err) {
      console.error(t('settings.gamedata.cancelFailed'), err);
    }
  };

  const startExtraction = async () => {
    if (!voiceAssetsStatus?.exists) return;

    setIsExtracting(true);
    setExtractProgress(null);
    setExtractError(null);

    try {
      // 추출 시작
      const languages = Object.keys(voiceAssetsStatus.languages || {});
      await extractApi.startExtract(
        languages.length > 0 ? languages : [voiceFolder],
      );

      // SSE 스트림 연결
      extractStreamRef.current = createExtractStream({
        onProgress: (progress) => {
          setExtractProgress(progress);
        },
        onComplete: (extracted) => {
          setIsExtracting(false);
          setExtractProgress({
            stage: "complete",
            processed: 0,
            total: 0,
            extracted,
            message: t('settings.voice.extractComplete', { count: extracted }),
          });
          // 설정 새로고침
          loadSettings();
          loadLanguageSettings();
        },
        onError: (error) => {
          setIsExtracting(false);
          setExtractError(error);
        },
      });
    } catch (err) {
      setIsExtracting(false);
      setExtractError(err instanceof Error ? err.message : t('settings.voice.startFailed'));
    }
  };

  const cancelExtraction = async () => {
    try {
      await extractApi.cancelExtract();
      extractStreamRef.current?.close();
      setIsExtracting(false);
      setExtractProgress(null);
    } catch (err) {
      console.error(t('settings.voice.cancelFailed'), err);
    }
  };

  const refreshDependencies = async () => {
    try {
      const [depData] = await Promise.all([
        settingsApi.refreshDependencies(),
        ttsApi.reinitGptSovits().catch(() => {}),
      ]);
      if (settings) {
        setSettings({ ...settings, dependencies: depData.dependencies });
      }
    } catch (err) {
      console.error(err);
    }
  };

  if (!isOpen) return null;

  const getDependencyIcon = (dep: DependencyStatus) => {
    if (dep.installed) {
      return (
        <span className="w-5 h-5 flex items-center justify-center rounded-full bg-green-500/20 text-green-400">
          <svg viewBox="0 0 24 24" className="w-3 h-3" fill="currentColor">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
          </svg>
        </span>
      );
    }
    return (
      <span className="w-5 h-5 flex items-center justify-center rounded-full bg-red-500/20 text-red-400">
        <svg viewBox="0 0 24 24" className="w-3 h-3" fill="currentColor">
          <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
        </svg>
      </span>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 오버레이 */}
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />

      {/* 모달 */}
      <div className="relative bg-ark-dark border border-ark-border rounded-lg w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        {/* 헤더 */}
        <div className="p-4 border-b border-ark-border flex items-center justify-between">
          <h2 className="text-lg font-bold text-ark-white flex items-center gap-2">
            <svg
              viewBox="0 0 24 24"
              className="w-5 h-5 text-ark-orange"
              fill="currentColor"
            >
              <path d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z" />
            </svg>
            {t('settings.title')}
          </h2>
          <button
            onClick={onClose}
            className="text-ark-gray hover:text-ark-white transition-colors"
          >
            <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
            </svg>
          </button>
        </div>

        {/* 컨텐츠 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <span className="text-ark-gray ark-pulse">{t('common.loading')}</span>
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <p className="text-red-400 mb-4">{error}</p>
              <button
                onClick={loadSettings}
                className="ark-btn ark-btn-secondary text-sm"
              >
                {t('common.retry')}
              </button>
            </div>
          ) : (
            settings && (
              <>
                {/* ===== 초기 설정 ===== */}
                <div className="ark-divider">
                  <span>{t('settings.section.initialSetup')}</span>
                </div>
                <p className="text-[11px] text-ark-gray/70 -mt-3 text-center mb-2">
                  {t('settings.initialSetupDesc')}
                </p>

                {/* 의존성 상태 */}
                <section>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-medium text-ark-white">
                      {t('settings.section.dependencies')}
                    </h3>
                    <button
                      onClick={refreshDependencies}
                      className="text-xs text-ark-gray hover:text-ark-white"
                    >
                      {t('common.refresh')}
                    </button>
                  </div>
                  <div className="space-y-2">
                    {settings.dependencies.map((dep) => (
                      <div
                        key={dep.name}
                        className="flex items-center justify-between p-3 bg-ark-black/50 rounded border border-ark-border"
                      >
                        <div className="flex items-center gap-3">
                          {getDependencyIcon(dep)}
                          <div>
                            <p className="text-sm text-ark-white font-medium">
                              {dep.name}
                            </p>
                            {dep.installed ? (
                              <p className="text-xs text-ark-gray">
                                {dep.version && `v${dep.version}`}
                                {dep.path && ` • ${dep.path}`}
                              </p>
                            ) : (
                              <p className="text-xs text-red-400">{t('settings.status.notInstalled')}</p>
                            )}
                          </div>
                        </div>
                        {!dep.installed && dep.name === "FFmpeg" && (
                          <div className="flex items-center gap-2">
                            <button
                              onClick={startFFmpegInstall}
                              disabled={isInstallingFFmpeg}
                              className="text-xs text-ark-orange hover:underline disabled:opacity-50"
                            >
                              {isInstallingFFmpeg ? t('settings.installing') : t('settings.autoInstall')}
                            </button>
                            <button
                              onClick={loadFFmpegGuide}
                              className="text-xs text-ark-gray hover:underline"
                            >
                              {t('settings.manual')}
                            </button>
                          </div>
                        )}
                        {!dep.installed && dep.name === "FFprobe" && (
                          <span className="text-xs text-ark-gray">
                            {t('settings.ffmpeg.included')}
                          </span>
                        )}
                        {!dep.installed && dep.name === "7-Zip" && (
                          <button
                            onClick={load7ZipGuide}
                            className="text-xs text-ark-orange hover:underline"
                          >
                            {t('settings.installMethod')}
                          </button>
                        )}
                        {!dep.installed && dep.name === "flatc" && (
                          <button
                            onClick={loadFlatcGuide}
                            className="text-xs text-ark-orange hover:underline"
                          >
                            {t('settings.installMethod')}
                          </button>
                        )}
                        {!dep.installed && dep.name === "GPT-SoVITS" && (
                          <button
                            onClick={() => setShowGptSovitsInstall(true)}
                            className="text-xs text-ark-orange hover:underline"
                          >
                            {t('settings.autoInstall')}
                          </button>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* FFmpeg 설치 가이드 */}
                  {showFFmpegGuide && ffmpegGuide && (
                    <div className="mt-3 p-4 bg-ark-panel rounded border border-ark-border">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-medium text-ark-white">
                          {t('settings.ffmpeg.installMethod')}
                        </h4>
                        <button
                          onClick={() => setShowFFmpegGuide(false)}
                          className="text-ark-gray hover:text-ark-white"
                        >
                          <svg
                            viewBox="0 0 24 24"
                            className="w-4 h-4"
                            fill="currentColor"
                          >
                            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
                          </svg>
                        </button>
                      </div>

                      {/* winget 방법 */}
                      <div className="mb-4">
                        <p className="text-xs text-ark-gray mb-2">
                          {t('settings.os.windows')}
                        </p>
                        <div className="flex items-center gap-2">
                          <code className="flex-1 px-3 py-2 bg-ark-black rounded text-sm text-ark-white font-mono">
                            {ffmpegGuide.windows.command}
                          </code>
                          <button
                            onClick={() =>
                              navigator.clipboard.writeText(
                                ffmpegGuide.windows.command,
                              )
                            }
                            className="px-3 py-2 bg-ark-black rounded text-ark-gray hover:text-ark-white"
                            title={t('common.copy')}
                          >
                            <svg
                              viewBox="0 0 24 24"
                              className="w-4 h-4"
                              fill="currentColor"
                            >
                              <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z" />
                            </svg>
                          </button>
                        </div>
                      </div>

                      {/* 수동 설치 */}
                      <div>
                        <p className="text-xs text-ark-gray mb-2">{t('settings.manualInstall')}</p>
                        <ol className="text-xs text-ark-white space-y-1">
                          {ffmpegGuide.manual_steps.map((step, i) => (
                            <li key={i}>{step}</li>
                          ))}
                        </ol>
                      </div>
                    </div>
                  )}

                  {/* FFmpeg 설치 진행/결과 */}
                  {(isInstallingFFmpeg || ffmpegInstallMsg || ffmpegInstallError) && (
                    <div className="mt-3 p-3 bg-ark-panel rounded border border-ark-border">
                      {isInstallingFFmpeg && (
                        <div className="flex items-center gap-2">
                          <svg className="animate-spin w-4 h-4 text-ark-orange" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                          <span className="text-xs text-ark-white">{ffmpegInstallMsg}</span>
                        </div>
                      )}
                      {!isInstallingFFmpeg && ffmpegInstallMsg && (
                        <p className="text-xs text-green-400">{ffmpegInstallMsg}</p>
                      )}
                      {ffmpegInstallError && (
                        <p className="text-xs text-red-400">{ffmpegInstallError}</p>
                      )}
                    </div>
                  )}

                  {/* 7-Zip 설치 가이드 */}
                  {show7ZipGuide && sevenZipGuide && (
                    <div className="mt-3 p-4 bg-ark-panel rounded border border-ark-border">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-medium text-ark-white">
                          {t('settings.sevenzip.installMethod')}
                        </h4>
                        <button
                          onClick={() => setShow7ZipGuide(false)}
                          className="text-ark-gray hover:text-ark-white"
                        >
                          <svg
                            viewBox="0 0 24 24"
                            className="w-4 h-4"
                            fill="currentColor"
                          >
                            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
                          </svg>
                        </button>
                      </div>

                      {/* 안내 메시지 */}
                      <div className="mb-4 p-2 bg-blue-500/10 border border-blue-500/30 rounded">
                        <p className="text-xs text-blue-400">
                          {sevenZipGuide.note}
                        </p>
                      </div>

                      {/* winget 방법 */}
                      <div className="mb-4">
                        <p className="text-xs text-ark-gray mb-2">
                          {t('settings.os.windows')}
                        </p>
                        <div className="flex items-center gap-2">
                          <code className="flex-1 px-3 py-2 bg-ark-black rounded text-sm text-ark-white font-mono">
                            {sevenZipGuide.windows.command}
                          </code>
                          <button
                            onClick={() =>
                              navigator.clipboard.writeText(
                                sevenZipGuide.windows.command,
                              )
                            }
                            className="px-3 py-2 bg-ark-black rounded text-ark-gray hover:text-ark-white"
                            title={t('common.copy')}
                          >
                            <svg
                              viewBox="0 0 24 24"
                              className="w-4 h-4"
                              fill="currentColor"
                            >
                              <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z" />
                            </svg>
                          </button>
                        </div>
                      </div>

                      {/* 수동 설치 */}
                      <div>
                        <p className="text-xs text-ark-gray mb-2">{t('settings.manualInstall')}</p>
                        <ol className="text-xs text-ark-white space-y-1">
                          {sevenZipGuide.manual_steps.map((step, i) => (
                            <li key={i}>{step}</li>
                          ))}
                        </ol>
                      </div>
                    </div>
                  )}

                  {/* flatc 설치 가이드 */}
                  {showFlatcGuide && flatcGuide && (
                    <div className="mt-3 p-4 bg-ark-panel rounded border border-ark-border">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-medium text-ark-white">
                          {t('settings.flatc.installMethodPrefix')}{flatcGuide.name}{t('settings.flatc.installMethodSuffix')}
                        </h4>
                        <button
                          onClick={() => setShowFlatcGuide(false)}
                          className="text-ark-gray hover:text-ark-white"
                        >
                          <svg
                            viewBox="0 0 24 24"
                            className="w-4 h-4"
                            fill="currentColor"
                          >
                            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
                          </svg>
                        </button>
                      </div>

                      {/* 안내 메시지 */}
                      <div className="mb-4 p-2 bg-blue-500/10 border border-blue-500/30 rounded">
                        <p className="text-xs text-blue-400">
                          {flatcGuide.description}
                        </p>
                      </div>

                      {/* winget 방법 */}
                      <div className="mb-4">
                        <p className="text-xs text-ark-gray mb-2">
                          {t('settings.os.windows')}
                        </p>
                        <div className="flex items-center gap-2">
                          <code className="flex-1 px-3 py-2 bg-ark-black rounded text-sm text-ark-white font-mono">
                            {flatcGuide.windows.command}
                          </code>
                          <button
                            onClick={() =>
                              navigator.clipboard.writeText(
                                flatcGuide.windows.command,
                              )
                            }
                            className="px-3 py-2 bg-ark-black rounded text-ark-gray hover:text-ark-white"
                            title={t('common.copy')}
                          >
                            <svg
                              viewBox="0 0 24 24"
                              className="w-4 h-4"
                              fill="currentColor"
                            >
                              <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z" />
                            </svg>
                          </button>
                        </div>
                      </div>

                      {/* 수동 설치 */}
                      <div>
                        <p className="text-xs text-ark-gray mb-2">{t('settings.manualInstall')}</p>
                        <ol className="text-xs text-ark-white space-y-1">
                          {flatcGuide.manual_steps.map((step, i) => (
                            <li key={i}>{step}</li>
                          ))}
                        </ol>
                      </div>
                    </div>
                  )}

                </section>

                {/* 게임 데이터 업데이트 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-2">
                    {t('settings.section.gamedata')}
                  </h3>
                  <p className="text-[11px] text-ark-gray/70 mb-3">
                    {t('settings.gamedata.description')}
                  </p>
                  <div className="p-4 bg-ark-black/50 rounded border border-ark-border space-y-2">
                    {/* 언어별 다운로드 섹션 */}
                    {GAMEDATA_SERVERS.map(({ server, label }) => {
                      const status = gamedataStatuses[server];
                      const isThisUpdating = updatingServer === server;
                      const thisCompleted = lastCompletedServer === server
                        && gamedataUpdateProgress?.stage === 'complete'
                        && updatingServer === null;
                      const thisError = gamedataUpdateError?.server === server
                        ? gamedataUpdateError.error
                        : null;

                      return (
                        <div key={server} className="py-2 border-b border-ark-border/50 last:border-b-0">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="text-sm font-medium text-ark-white w-16 shrink-0">
                                {label}
                              </span>
                              {status === undefined ? (
                                <span className="text-xs text-ark-gray">{t('common.checking')}</span>
                              ) : status?.exists ? (
                                <span className="text-xs text-ark-gray">
                                  {t('settings.gamedata.ready', { count: status.story_count })}
                                  {status.last_updated && (
                                    <span className="ml-2 text-ark-gray/50">
                                      {new Date(status.last_updated).toLocaleDateString()}
                                    </span>
                                  )}
                                </span>
                              ) : (
                                <span className="text-xs text-ark-gray/50">{t('settings.gamedata.notReady')}</span>
                              )}
                            </div>
                            {!isThisUpdating && !thisCompleted && (
                              <button
                                onClick={() => startGamedataUpdate(server)}
                                disabled={updatingServer !== null}
                                className="ark-btn ark-btn-primary text-xs px-3 py-1 shrink-0 disabled:opacity-30"
                              >
                                {status?.exists
                                  ? t('settings.gamedata.update')
                                  : t('settings.gamedata.download')}
                              </button>
                            )}
                          </div>

                          {/* 진행률 */}
                          {isThisUpdating && gamedataUpdateProgress && (
                            <div className="mt-2">
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-xs text-ark-gray">
                                  {gamedataUpdateProgress.message}
                                </span>
                                <button
                                  onClick={cancelGamedataUpdate}
                                  className="text-xs text-red-400 hover:text-red-300"
                                >
                                  {t('common.cancel')}
                                </button>
                              </div>
                              <div className="relative h-1.5 bg-ark-panel rounded overflow-hidden">
                                <div
                                  className="absolute inset-y-0 left-0 bg-ark-orange transition-all duration-300"
                                  style={{ width: `${gamedataUpdateProgress.progress * 100}%` }}
                                />
                              </div>
                            </div>
                          )}

                          {/* 완료 */}
                          {thisCompleted && (
                            <div className="mt-2 flex items-center justify-between">
                              <p className="text-xs text-green-400">
                                {gamedataUpdateProgress?.message}
                              </p>
                              <button
                                onClick={refreshCharacterData}
                                disabled={isRefreshingCharacters}
                                className="text-xs text-ark-orange hover:underline disabled:opacity-50"
                              >
                                {isRefreshingCharacters
                                  ? t('common.refreshing')
                                  : t('settings.characters.refresh')}
                              </button>
                            </div>
                          )}

                          {/* 에러 */}
                          {thisError && (
                            <div className="mt-2 p-1.5 bg-red-500/10 border border-red-500/30 rounded">
                              <p className="text-xs text-red-400">{thisError}</p>
                            </div>
                          )}
                        </div>
                      );
                    })}

                    {/* 소스 설정 (공유) */}
                    <div className="pt-2 border-t border-ark-border">
                      <label className="text-xs text-ark-gray block mb-1">
                        {t('settings.gamedata.source')}
                      </label>
                      <select
                        value={gamedataSource}
                        onChange={(e) => changeGamedataSource(e.target.value)}
                        disabled={updatingServer !== null}
                        className="w-full px-2 py-1 text-xs bg-ark-black border border-ark-border rounded text-ark-white focus:border-ark-orange focus:outline-none disabled:opacity-50"
                      >
                        <option value="github">GitHub (ArknightsGamedata)</option>
                        <option value="arkprts">arkprts</option>
                      </select>
                      {gamedataSource === 'github' && (
                        <div className="flex gap-2 mt-2">
                          <input
                            type="text"
                            value={gamedataRepoInput}
                            onChange={(e) => setGamedataRepoInput(e.target.value)}
                            placeholder="owner/repo"
                            className="flex-1 px-2 py-1 text-xs bg-ark-black border border-ark-border rounded text-ark-white placeholder:text-ark-gray/50 focus:border-ark-orange focus:outline-none"
                          />
                          <button
                            onClick={saveGamedataRepo}
                            disabled={isRepoSaving || gamedataRepoInput === gamedataRepo}
                            className="px-3 py-1 text-xs bg-ark-panel border border-ark-border rounded text-ark-gray hover:text-ark-white disabled:opacity-30 disabled:cursor-default"
                          >
                            {isRepoSaving ? '...' : t('settings.save')}
                          </button>
                        </div>
                      )}
                      {gamedataSource === 'arkprts' && (
                        <p className="text-[10px] text-ark-gray/60 mt-1">
                          {t('settings.gamedata.arkprtsDesc')}
                        </p>
                      )}
                    </div>

                    {/* 수동 캐릭터 새로고침 */}
                    {Object.values(gamedataStatuses).some(s => s?.exists) && (
                      <div className="flex items-center justify-between pt-2 border-t border-ark-border">
                        <span className="text-xs text-ark-gray">
                          {t('settings.characters.mappingCache')}
                        </span>
                        <button
                          onClick={refreshCharacterData}
                          disabled={isRefreshingCharacters}
                          className="text-xs text-ark-orange hover:underline disabled:opacity-50"
                        >
                          {isRefreshingCharacters
                            ? t('common.refreshing')
                            : t('common.refresh')}
                        </button>
                      </div>
                    )}
                  </div>
                </section>

                {/* 음성 추출 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-2">
                    {t('settings.section.voiceExtract')}
                  </h3>
                  <p className="text-[11px] text-ark-gray/70 mb-3">
                    {t('settings.voice.extractDescription')}
                    <br /><span className="text-ark-yellow/70">{t('settings.voice.extractWarning')}</span>
                  </p>
                  <div className="p-4 bg-ark-black/50 rounded border border-ark-border">
                    {voiceAssetsStatus === null ? (
                      <p className="text-sm text-ark-gray">{t('common.checking')}</p>
                    ) : !voiceAssetsStatus.exists ? (
                      <div>
                        <p className="text-sm text-red-400 mb-2">
                          {voiceAssetsStatus.message}
                        </p>
                        <p className="text-xs text-ark-gray">
                          {voiceAssetsStatus.hint}
                        </p>
                      </div>
                    ) : (
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <p className="text-sm text-ark-white">
                              {t('settings.voice.assetsReady')}
                            </p>
                            <p className="text-xs text-ark-gray mt-1">
                              {Object.entries(
                                voiceAssetsStatus.languages || {},
                              ).map(([lang, count]) => (
                                <span key={lang} className="mr-3">
                                  {t('settings.voice.bundleCount', { lang, count })}
                                </span>
                              ))}
                            </p>
                          </div>
                          {!isExtracting &&
                            extractProgress?.stage !== "complete" && (
                              <button
                                onClick={startExtraction}
                                className="ark-btn ark-btn-primary text-sm"
                              >
                                {t('settings.voice.extract')}
                              </button>
                            )}
                        </div>

                        {/* 추출 진행률 */}
                        {isExtracting && extractProgress && (
                          <div className="mt-3">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-xs text-ark-gray">
                                {extractProgress.message}
                              </span>
                              <button
                                onClick={cancelExtraction}
                                className="text-xs text-red-400 hover:text-red-300"
                              >
                                {t('common.cancel')}
                              </button>
                            </div>
                            {extractProgress.total > 0 && (
                              <div className="relative h-2 bg-ark-panel rounded overflow-hidden">
                                <div
                                  className="absolute inset-y-0 left-0 bg-ark-orange transition-all duration-300"
                                  style={{
                                    width: `${(extractProgress.processed / extractProgress.total) * 100}%`,
                                  }}
                                />
                              </div>
                            )}
                            <p className="text-xs text-ark-gray mt-1">
                              {t('settings.voice.extractProgress', { processed: extractProgress.processed, total: extractProgress.total, extracted: extractProgress.extracted })}
                            </p>
                          </div>
                        )}

                        {/* 완료 메시지 */}
                        {extractProgress?.stage === "complete" &&
                          !isExtracting && (
                            <div className="mt-3 p-2 bg-green-500/10 border border-green-500/30 rounded">
                              <p className="text-xs text-green-400">
                                {extractProgress.message}
                              </p>
                            </div>
                          )}

                        {/* 에러 메시지 */}
                        {extractError && (
                          <div className="mt-3 p-2 bg-red-500/10 border border-red-500/30 rounded">
                            <p className="text-xs text-red-400">
                              {extractError}
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                    {/* 경로 안내 (항상 표시) */}
                    <div className="mt-3 pt-3 border-t border-ark-border space-y-1">
                      <p className="text-[10px] text-ark-gray/60">
                        <span className="text-ark-gray">{t('settings.appDataPath')}</span> {t('settings.appDataNote')}
                      </p>
                      <p className="text-[10px] text-ark-gray/60">
                        <span className="text-ark-gray">{t('settings.voice.bundlePath')}</span> {t('settings.voice.bundlePathValue')}
                      </p>
                      <p className="text-[10px] text-ark-gray/60 ml-4">
                        {t('settings.voice.voiceFolders')}
                      </p>
                      <div className="flex items-center justify-between">
                        <p className="text-[10px] text-ark-gray/60">
                          <span className="text-ark-gray">{t('settings.copyLocation')}</span> {t('settings.voice.copyLocationAll')}
                        </p>
                        <button
                          onClick={async () => {
                            try {
                              const folderPath = 'Assets/Voice';
                              if (voiceAssetsStatus?.exists) {
                                await settingsApi.openFolder(folderPath);
                              } else {
                                await settingsApi.createFolder(folderPath);
                                checkVoiceAssets();
                              }
                            } catch (err) {
                              console.error(t('settings.folder.operationFailed'), err);
                            }
                          }}
                          className="text-[10px] text-ark-cyan hover:text-ark-white transition-colors"
                        >
                          {voiceAssetsStatus?.exists ? t('common.open') : t('settings.createFolder')}
                        </button>
                      </div>
                      <p className="text-[10px] text-ark-gray/60">
                        <span className="text-ark-gray">{t('settings.extractResult')}</span> {t('settings.voice.extractResultDetail')}
                      </p>
                    </div>
                  </div>
                </section>

                {/* 이미지 추출 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-2">
                    {t('settings.section.imageExtract')}
                  </h3>
                  <p className="text-[11px] text-ark-gray/70 mb-1">
                    {t('settings.image.extractDescription')}
                  </p>
                  <p className="text-[10px] text-ark-gray/50 mb-3">
                    {t('settings.appDataPath')} {t('settings.appDataNote')}
                  </p>

                  {imageAssetsStatus === null ? (
                    <div className="p-4 bg-ark-black/50 rounded border border-ark-border">
                      <p className="text-sm text-ark-gray">{t('common.checking')}</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {/* 카드 1: 캐릭터 일러스트 (characters) */}
                      <div className="p-4 bg-ark-black/50 rounded border border-ark-border">
                        <div className="flex items-center justify-between mb-2">
                          <div>
                            <p className="text-sm text-ark-white font-medium">{t('settings.image.characterIllustration')}</p>
                            <p className="text-[10px] text-ark-gray mt-0.5">{t('settings.image.characterIllustrationDesc')}</p>
                          </div>
                          {imageAssetsStatus.characters_exists && !isExtractingImages && (
                            <button
                              onClick={() => startImageExtraction('characters')}
                              className="ark-btn ark-btn-primary text-xs"
                            >
                              {t('settings.extract')}
                            </button>
                          )}
                        </div>

                        {!imageAssetsStatus.characters_exists ? (
                          <div className="p-2 bg-yellow-500/10 border border-yellow-500/30 rounded">
                            <p className="text-xs text-yellow-400">{t('settings.image.folderMissingCharacters')}</p>
                          </div>
                        ) : (
                          <p className="text-xs text-green-400/80">{imageAssetsStatus.characters_bundles ?? 0}{t('settings.bundlesReady')}</p>
                        )}

                        {/* 진행률/완료 (이 카드 대상일 때만) */}
                        {extractingImageTarget === 'characters' && (
                          <>
                            {isExtractingImages && imageExtractProgress && (
                              <div className="mt-3">
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-xs text-ark-gray">{imageExtractProgress.message}</span>
                                  <button onClick={cancelImageExtraction} className="text-xs text-red-400 hover:text-red-300">{t('common.cancel')}</button>
                                </div>
                                {imageExtractProgress.total > 0 && (
                                  <div className="relative h-2 bg-ark-panel rounded overflow-hidden">
                                    <div className="absolute inset-y-0 left-0 bg-ark-orange transition-all duration-300" style={{ width: `${(imageExtractProgress.processed / imageExtractProgress.total) * 100}%` }} />
                                  </div>
                                )}
                                <p className="text-xs text-ark-gray mt-1">{t('settings.image.extractProgress', { processed: imageExtractProgress.processed, total: imageExtractProgress.total, extracted: imageExtractProgress.extracted })}</p>
                              </div>
                            )}
                            {imageExtractProgress?.stage === "complete" && !isExtractingImages && (
                              <div className="mt-2 p-2 bg-green-500/10 border border-green-500/30 rounded">
                                <p className="text-xs text-green-400">{imageExtractProgress.message}</p>
                              </div>
                            )}
                          </>
                        )}

                        <div className="mt-2 pt-2 border-t border-ark-border space-y-1">
                          <p className="text-[10px] text-ark-gray/60">
                            <span className="text-ark-gray">{t('settings.gamePath')}</span> {t('settings.image.gameCharactersBundlePath')}
                          </p>
                          <div className="flex items-center justify-between">
                            <p className="text-[10px] text-ark-gray/60">
                              <span className="text-ark-gray">{t('settings.copyLocation')}</span> {t('settings.image.copyCharactersLocation')}
                            </p>
                            <button
                              onClick={async () => {
                                try {
                                  if (imageAssetsStatus?.characters_exists) {
                                    await settingsApi.openFolder('Assets/Image/avg/characters');
                                  } else {
                                    await settingsApi.createFolder('Assets/Image/avg/characters');
                                    checkImageAssets();
                                  }
                                } catch (err) {
                                  console.error(t('settings.folder.operationFailed'), err);
                                }
                              }}
                              className="text-[10px] text-ark-cyan hover:text-ark-white transition-colors"
                            >
                              {imageAssetsStatus?.characters_exists ? t('common.open') : t('settings.createFolder')}
                            </button>
                          </div>
                          <p className="text-[10px] text-ark-gray/60">
                            <span className="text-ark-gray">{t('settings.extractResult')}</span> {t('settings.image.extractResultDetail')}
                          </p>
                        </div>
                      </div>

                      {/* 카드 2: 캐릭터 초상화 (chararts) */}
                      <div className="p-4 bg-ark-black/50 rounded border border-ark-border">
                        <div className="flex items-center justify-between mb-2">
                          <div>
                            <p className="text-sm text-ark-white font-medium">{t('settings.image.characterPortrait')}</p>
                            <p className="text-[10px] text-ark-gray mt-0.5">{t('settings.image.characterPortraitDesc')}</p>
                          </div>
                          {imageAssetsStatus.chararts_exists && !isExtractingImages && (
                            <button
                              onClick={() => startImageExtraction('chararts')}
                              className="ark-btn ark-btn-primary text-xs"
                            >
                              {t('settings.extract')}
                            </button>
                          )}
                        </div>

                        {!imageAssetsStatus.chararts_exists ? (
                          <div className="p-2 bg-yellow-500/10 border border-yellow-500/30 rounded">
                            <p className="text-xs text-yellow-400">{t('settings.image.folderMissingChararts')}</p>
                          </div>
                        ) : (
                          <p className="text-xs text-green-400/80">{imageAssetsStatus.chararts_bundles ?? 0}{t('settings.bundlesReady')}</p>
                        )}

                        {/* 진행률/완료 (이 카드 대상일 때만) */}
                        {extractingImageTarget === 'chararts' && (
                          <>
                            {isExtractingImages && imageExtractProgress && (
                              <div className="mt-3">
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-xs text-ark-gray">{imageExtractProgress.message}</span>
                                  <button onClick={cancelImageExtraction} className="text-xs text-red-400 hover:text-red-300">{t('common.cancel')}</button>
                                </div>
                                {imageExtractProgress.total > 0 && (
                                  <div className="relative h-2 bg-ark-panel rounded overflow-hidden">
                                    <div className="absolute inset-y-0 left-0 bg-ark-orange transition-all duration-300" style={{ width: `${(imageExtractProgress.processed / imageExtractProgress.total) * 100}%` }} />
                                  </div>
                                )}
                                <p className="text-xs text-ark-gray mt-1">{t('settings.image.extractProgress', { processed: imageExtractProgress.processed, total: imageExtractProgress.total, extracted: imageExtractProgress.extracted })}</p>
                              </div>
                            )}
                            {imageExtractProgress?.stage === "complete" && !isExtractingImages && (
                              <div className="mt-2 p-2 bg-green-500/10 border border-green-500/30 rounded">
                                <p className="text-xs text-green-400">{imageExtractProgress.message}</p>
                              </div>
                            )}
                          </>
                        )}

                        <div className="mt-2 pt-2 border-t border-ark-border space-y-1">
                          <p className="text-[10px] text-ark-gray/60">
                            <span className="text-ark-gray">{t('settings.gamePath')}</span> {t('settings.image.gameCharartsBundlePath')}
                          </p>
                          <div className="flex items-center justify-between">
                            <p className="text-[10px] text-ark-gray/60">
                              <span className="text-ark-gray">{t('settings.copyLocation')}</span> {t('settings.image.copyCharartsLocation')}
                            </p>
                            <button
                              onClick={async () => {
                                try {
                                  if (imageAssetsStatus?.chararts_exists) {
                                    await settingsApi.openFolder('Assets/Image/chararts');
                                  } else {
                                    await settingsApi.createFolder('Assets/Image/chararts');
                                    checkImageAssets();
                                  }
                                } catch (err) {
                                  console.error(t('settings.folder.operationFailed'), err);
                                }
                              }}
                              className="text-[10px] text-ark-cyan hover:text-ark-white transition-colors"
                            >
                              {imageAssetsStatus?.chararts_exists ? t('common.open') : t('settings.createFolder')}
                            </button>
                          </div>
                          <p className="text-[10px] text-ark-gray/60">
                            <span className="text-ark-gray">{t('settings.extractResult')}</span> {t('settings.image.extractResultDetail')}
                          </p>
                        </div>
                      </div>

                      {/* 에러 메시지 (공통) */}
                      {imageExtractError && (
                        <div className="p-2 bg-red-500/10 border border-red-500/30 rounded">
                          <p className="text-xs text-red-400">{imageExtractError}</p>
                        </div>
                      )}
                    </div>
                  )}
                </section>

                {/* ===== 음성 설정 ===== */}
                <div className="ark-divider mt-2">
                  <span>{t('settings.section.voiceSettings')}</span>
                </div>

                {/* 캐릭터 별칭 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-3">
                    {t('settings.section.aliases')}
                  </h3>
                  <div className="p-4 bg-ark-black/50 rounded border border-ark-border">
                    <p className="text-xs text-ark-gray mb-3">
                      {t('settings.aliases.description')}
                      <br />
                      {t('settings.aliases.descriptionExample')}
                    </p>

                    <div className="flex items-center gap-3 mb-3">
                      <div className="flex-1">
                        <span className="text-sm text-ark-white">
                          {t('settings.aliases.count')} {aliasesInfo?.total ?? 0}
                        </span>
                      </div>
                      <button
                        onClick={handleExtractAliases}
                        disabled={isExtractingAliases}
                        className={`px-4 py-2 rounded border transition-colors ${
                          isExtractingAliases
                            ? "bg-ark-panel/50 border-ark-border/50 text-ark-gray/50 cursor-not-allowed"
                            : "bg-ark-panel border-ark-border text-ark-gray hover:text-ark-white hover:border-ark-orange"
                        }`}
                      >
                        {isExtractingAliases ? t('settings.aliases.extracting') : t('settings.aliases.autoExtract')}
                      </button>
                    </div>

                    {aliasExtractResult && (
                      <div className="p-2 bg-green-500/10 border border-green-500/30 rounded text-xs text-green-400">
                        {t('settings.aliases.extractedComplete', { charCount: aliasExtractResult.extracted_count, aliasCount: aliasExtractResult.alias_count })}
                      </div>
                    )}

                    <p className="text-[10px] text-ark-gray/60 mt-2">
                      {t('settings.aliases.note')}
                    </p>
                  </div>
                </section>

                {/* ===== 고급 설정 ===== */}
                <div className="ark-divider mt-2">
                  <span>{t('settings.section.advanced')}</span>
                </div>

                {/* TTS 추론 파라미터 */}
                <TTSParamsSection />

                {/* 언어 설정 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-2">
                    {t('settings.section.language')}
                  </h3>
                  <p className="text-[11px] text-ark-gray/70 mb-3">
                    {t('settings.language.description')}
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 bg-ark-black/50 rounded border border-ark-border">
                      <p className="text-xs text-ark-gray mb-1">{t('settings.language.game')}</p>
                      <p className="text-sm text-ark-white">
                        {settings.game_language}
                      </p>
                    </div>
                    <div className="p-3 bg-ark-black/50 rounded border border-ark-border">
                      <p className="text-xs text-ark-gray mb-1">
                        {t('settings.language.gptSovits')}
                      </p>
                      <p className="text-sm text-ark-white">
                        {settings.gpt_sovits_language}
                      </p>
                    </div>
                  </div>
                </section>

                {/* 경로 설정 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-2">
                    {t('settings.section.paths')}
                  </h3>
                  <p className="text-[11px] text-ark-gray/70 mb-3">
                    {t('settings.paths.description')}
                  </p>
                  <div className="space-y-2">
                    <PathItem
                      label={t('settings.paths.gptSovits')}
                      path={settings.gpt_sovits_path}
                      onOpen={() => handleOpenFolder(settings.gpt_sovits_path)}
                    />
                    <PathItem
                      label={t('settings.paths.models')}
                      path={settings.models_path}
                      onOpen={() => handleOpenFolder(settings.models_path)}
                    />
                    <PathItem
                      label={t('settings.paths.extracted')}
                      path={settings.extracted_path}
                      onOpen={() => handleOpenFolder(settings.extracted_path)}
                    />
                    <PathItem
                      label={t('settings.paths.gamedata')}
                      path={settings.gamedata_path}
                      onOpen={() => handleOpenFolder(settings.gamedata_path)}
                    />
                  </div>
                </section>

                {/* Whisper 전처리 설정 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-2">
                    {t('settings.section.whisperPreprocessing')}
                  </h3>
                  <p className="text-[11px] text-ark-gray/70 mb-3">
                    {t('settings.whisper.description')}
                  </p>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="p-3 bg-ark-black/50 rounded border border-ark-border">
                      <p className="text-xs text-ark-gray mb-1">{t('settings.whisper.model')}</p>
                      <p className="text-sm text-ark-white">
                        {settings.whisper_model_size}
                      </p>
                    </div>
                    <div className="p-3 bg-ark-black/50 rounded border border-ark-border">
                      <p className="text-xs text-ark-gray mb-1">{t('settings.whisper.computeType')}</p>
                      <p className="text-sm text-ark-white">
                        {settings.whisper_compute_type}
                      </p>
                    </div>
                    <div className="p-3 bg-ark-black/50 rounded border border-ark-border">
                      <p className="text-xs text-ark-gray mb-1">{t('settings.whisper.usage')}</p>
                      <p
                        className={`text-sm ${settings.use_whisper_preprocessing ? "text-green-400" : "text-red-400"}`}
                      >
                        {settings.use_whisper_preprocessing
                          ? t('common.enabled')
                          : t('common.disabled')}
                      </p>
                    </div>
                  </div>
                  <p className="text-xs text-ark-gray/70 mt-2">
                    {t('settings.whisper.note')}
                  </p>
                </section>
              </>
            )
          )}
        </div>

        {/* 푸터 */}
        <div className="p-4 border-t border-ark-border">
          <button
            onClick={onClose}
            className="w-full ark-btn ark-btn-secondary"
          >
            {t('common.close')}
          </button>
        </div>
      </div>

      {/* GPT-SoVITS 설치 다이얼로그 */}
      <GPTSoVITSInstallDialog
        isOpen={showGptSovitsInstall}
        onClose={() => setShowGptSovitsInstall(false)}
        onInstallComplete={() => {
          refreshDependencies();
          setShowGptSovitsInstall(false);
        }}
      />

    </div>
  );
}

// TTS 추론 파라미터 섹션 (접기/펼치기)
function TTSParamsSection() {
  const { t } = useTranslation()
  const { ttsParams, loadTtsParams, updateTtsParams } = useAppStore()
  const [isLoaded, setIsLoaded] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)

  useEffect(() => {
    loadTtsParams().then(() => setIsLoaded(true))
  }, [loadTtsParams])

  const params = [
    {
      key: 'temperature' as const,
      label: 'Temperature',
      desc: t('settings.tts.temperatureDesc'),
      min: 0.1, max: 2.0, step: 0.05,
    },
    {
      key: 'top_k' as const,
      label: 'Top K',
      desc: t('settings.tts.topKDesc'),
      min: 1, max: 30, step: 1,
    },
    {
      key: 'top_p' as const,
      label: 'Top P',
      desc: t('settings.tts.topPDesc'),
      min: 0.1, max: 1.0, step: 0.05,
    },
    {
      key: 'speed_factor' as const,
      label: t('settings.tts.speedFactorLabel'),
      desc: t('settings.tts.speedFactorDesc'),
      min: 0.5, max: 2.0, step: 0.05,
    },
  ]

  return (
    <section>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between mb-2 group"
      >
        <div>
          <h3 className="text-sm font-medium text-ark-white">{t('settings.section.ttsParams')}</h3>
          <p className="text-[11px] text-ark-gray/70 text-left">
            {t('settings.tts.description')}
          </p>
        </div>
        <svg
          viewBox="0 0 24 24"
          className={`w-4 h-4 text-ark-gray group-hover:text-ark-white transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="currentColor"
        >
          <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z" />
        </svg>
      </button>
      {isExpanded && (
        <div className="p-4 bg-ark-black/50 rounded border border-ark-border space-y-4">
          {!isLoaded ? (
            <p className="text-sm text-ark-gray">{t('common.loading')}</p>
          ) : (
            <>
              <p className="text-xs text-ark-gray">
                {t('settings.tts.appliedImmediately')}
              </p>
              {params.map(({ key, label, desc, min, max, step }) => (
                <div key={key}>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs text-ark-gray">{label}</label>
                    <span className="text-xs text-ark-white font-mono w-12 text-right">
                      {key === 'top_k' ? ttsParams[key] : ttsParams[key].toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={min}
                    max={max}
                    step={step}
                    value={ttsParams[key]}
                    onChange={(e) => {
                      const value = key === 'top_k' ? parseInt(e.target.value) : parseFloat(e.target.value)
                      updateTtsParams({ [key]: value })
                    }}
                    className="w-full h-1.5 bg-ark-border rounded-lg appearance-none cursor-pointer accent-ark-orange"
                  />
                  <div className="flex justify-between mt-0.5">
                    <span className="text-[10px] text-ark-gray/50">{min}</span>
                    <span className="text-[10px] text-ark-gray/50">{desc}</span>
                    <span className="text-[10px] text-ark-gray/50">{max}</span>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </section>
  )
}

// 경로 아이템 컴포넌트
function PathItem({
  label,
  path,
  onOpen,
}: {
  label: string;
  path: string;
  onOpen: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-between p-3 bg-ark-black/50 rounded border border-ark-border">
      <div className="flex-1 min-w-0 mr-3">
        <p className="text-xs text-ark-gray mb-1">{label}</p>
        <p className="text-sm text-ark-white truncate" title={path}>
          {path}
        </p>
      </div>
      <button
        onClick={onOpen}
        className="flex-shrink-0 px-3 py-1.5 text-xs text-ark-gray hover:text-ark-white bg-ark-panel rounded border border-ark-border hover:border-ark-orange transition-colors"
      >
        {t('common.open')}
      </button>
    </div>
  );
}
