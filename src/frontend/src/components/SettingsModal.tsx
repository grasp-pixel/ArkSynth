import { useEffect, useState, useRef } from "react";
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

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
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

  // 게임 데이터 업데이트 관련 상태
  const [gamedataStatus, setGamedataStatus] = useState<GamedataStatus | null>(
    null,
  );
  const [isUpdatingGamedata, setIsUpdatingGamedata] = useState(false);
  const [gamedataUpdateProgress, setGamedataUpdateProgress] =
    useState<GamedataUpdateProgress | null>(null);
  const [gamedataUpdateError, setGamedataUpdateError] = useState<string | null>(
    null,
  );
  const gamedataStreamRef = useRef<{ close: () => void } | null>(null);
  const [gamedataRepo, setGamedataRepo] = useState('');
  const [gamedataRepoInput, setGamedataRepoInput] = useState('');
  const [isRepoSaving, setIsRepoSaving] = useState(false);
  const [gamedataSource, setGamedataSource] = useState<string>('github');

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
      checkVoiceAssets();
      checkImageAssets();
      checkGamedataStatus();
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
      setError("설정을 불러오는데 실패했습니다");
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
    setFFmpegInstallMsg("설치 시작 중...");
    setFFmpegInstallError(null);
    try {
      await settingsApi.startFFmpegInstall();
      ffmpegInstallStreamRef.current = createFFmpegInstallStream({
        onProgress: (p) => setFFmpegInstallMsg(p.message),
        onComplete: () => {
          setIsInstallingFFmpeg(false);
          setFFmpegInstallMsg("FFmpeg 설치 완료! 새로고침하세요.");
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
      setFFmpegInstallError(err instanceof Error ? err.message : "FFmpeg 설치 시작 실패");
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
      console.error("캐릭터 데이터 새로고침 실패:", err);
    } finally {
      setIsRefreshingCharacters(false);
    }
  };

  const handleOpenFolder = async (path: string) => {
    try {
      await settingsApi.openFolder(path);
    } catch (err) {
      console.error("폴더 열기 실패:", err);
    }
  };

  const checkVoiceAssets = async () => {
    try {
      const status = await extractApi.checkVoiceAssets();
      setVoiceAssetsStatus(status);
    } catch (err) {
      console.error("VoiceAssets 확인 실패:", err);
    }
  };

  const checkImageAssets = async () => {
    try {
      const status = await imageExtractApi.checkImageAssets();
      setImageAssetsStatus(status);
    } catch (err) {
      console.error("ImageAssets 확인 실패:", err);
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
            message: `추출 완료: ${extracted}개 이미지`,
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
        err instanceof Error ? err.message : "이미지 추출 시작 실패",
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
      console.error("이미지 추출 취소 실패:", err);
    }
  };

  const checkGamedataStatus = async () => {
    try {
      const status = await gamedataApi.getStatus("kr");
      setGamedataStatus(status);
    } catch (err) {
      console.error("게임 데이터 상태 확인 실패:", err);
    }
  };

  const loadGamedataSource = async () => {
    try {
      const { source, repo } = await gamedataApi.getSource();
      setGamedataSource(source);
      setGamedataRepo(repo);
      setGamedataRepoInput(repo);
    } catch (err) {
      console.error("데이터 소스 설정 로드 실패:", err);
    }
  };

  const changeGamedataSource = async (newSource: string) => {
    try {
      await gamedataApi.setSource(newSource);
      setGamedataSource(newSource);
    } catch (err) {
      console.error("데이터 소스 변경 실패:", err);
    }
  };

  const loadGamedataRepo = async () => {
    try {
      const { repo } = await gamedataApi.getRepo();
      setGamedataRepo(repo);
      setGamedataRepoInput(repo);
    } catch (err) {
      console.error("레포지토리 설정 로드 실패:", err);
    }
  };

  const saveGamedataRepo = async () => {
    if (!gamedataRepoInput.trim() || gamedataRepoInput === gamedataRepo) return;
    setIsRepoSaving(true);
    try {
      await gamedataApi.setRepo(gamedataRepoInput.trim());
      setGamedataRepo(gamedataRepoInput.trim());
    } catch (err) {
      console.error("레포지토리 설정 저장 실패:", err);
    } finally {
      setIsRepoSaving(false);
    }
  };

  const loadAliasesInfo = async () => {
    try {
      const info = await aliasesApi.listAliases();
      setAliasesInfo(info);
    } catch (err) {
      console.error("별칭 정보 로드 실패:", err);
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
      console.error("본명 추출 실패:", err);
    } finally {
      setIsExtractingAliases(false);
    }
  };

  const startGamedataUpdate = async () => {
    setIsUpdatingGamedata(true);
    setGamedataUpdateProgress(null);
    setGamedataUpdateError(null);

    try {
      await gamedataApi.startUpdate("kr");

      // SSE 스트림 연결
      gamedataStreamRef.current = createGamedataUpdateStream({
        onProgress: (progress) => {
          setGamedataUpdateProgress(progress);
        },
        onComplete: () => {
          setIsUpdatingGamedata(false);
          setGamedataUpdateProgress({
            stage: "complete",
            progress: 1,
            message: "업데이트 완료!",
          });
          // 상태 새로고침
          checkGamedataStatus();
          loadSettings();
        },
        onError: (error) => {
          setIsUpdatingGamedata(false);
          setGamedataUpdateError(error);
        },
      });
    } catch (err) {
      setIsUpdatingGamedata(false);
      setGamedataUpdateError(
        err instanceof Error ? err.message : "업데이트 시작 실패",
      );
    }
  };

  const cancelGamedataUpdate = async () => {
    try {
      await gamedataApi.cancelUpdate();
      gamedataStreamRef.current?.close();
      setIsUpdatingGamedata(false);
      setGamedataUpdateProgress(null);
    } catch (err) {
      console.error("업데이트 취소 실패:", err);
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
        languages.length > 0 ? languages : ["voice", "voice_kr"],
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
            message: `추출 완료: ${extracted}개 파일`,
          });
          // 설정 새로고침
          loadSettings();
        },
        onError: (error) => {
          setIsExtracting(false);
          setExtractError(error);
        },
      });
    } catch (err) {
      setIsExtracting(false);
      setExtractError(err instanceof Error ? err.message : "추출 시작 실패");
    }
  };

  const cancelExtraction = async () => {
    try {
      await extractApi.cancelExtract();
      extractStreamRef.current?.close();
      setIsExtracting(false);
      setExtractProgress(null);
    } catch (err) {
      console.error("추출 취소 실패:", err);
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
            설정
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
              <span className="text-ark-gray ark-pulse">로딩 중...</span>
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <p className="text-red-400 mb-4">{error}</p>
              <button
                onClick={loadSettings}
                className="ark-btn ark-btn-secondary text-sm"
              >
                다시 시도
              </button>
            </div>
          ) : (
            settings && (
              <>
                {/* ===== 초기 설정 ===== */}
                <div className="ark-divider">
                  <span>초기 설정</span>
                </div>
                <p className="text-[11px] text-ark-gray/70 -mt-3 text-center mb-2">
                  처음 사용 시 아래 항목을 순서대로 완료하세요
                </p>

                {/* 의존성 상태 */}
                <section>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-medium text-ark-white">
                      의존성
                    </h3>
                    <button
                      onClick={refreshDependencies}
                      className="text-xs text-ark-gray hover:text-ark-white"
                    >
                      새로고침
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
                              <p className="text-xs text-red-400">미설치</p>
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
                              {isInstallingFFmpeg ? '설치 중...' : '자동 설치'}
                            </button>
                            <button
                              onClick={loadFFmpegGuide}
                              className="text-xs text-ark-gray hover:underline"
                            >
                              수동
                            </button>
                          </div>
                        )}
                        {!dep.installed && dep.name === "FFprobe" && (
                          <span className="text-xs text-ark-gray">
                            FFmpeg에 포함
                          </span>
                        )}
                        {!dep.installed && dep.name === "7-Zip" && (
                          <button
                            onClick={load7ZipGuide}
                            className="text-xs text-ark-orange hover:underline"
                          >
                            설치 방법
                          </button>
                        )}
                        {!dep.installed && dep.name === "flatc" && (
                          <button
                            onClick={loadFlatcGuide}
                            className="text-xs text-ark-orange hover:underline"
                          >
                            설치 방법
                          </button>
                        )}
                        {!dep.installed && dep.name === "GPT-SoVITS" && (
                          <button
                            onClick={() => setShowGptSovitsInstall(true)}
                            className="text-xs text-ark-orange hover:underline"
                          >
                            자동 설치
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
                          FFmpeg 설치 방법
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
                          Windows (winget 사용):
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
                            title="복사"
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
                        <p className="text-xs text-ark-gray mb-2">수동 설치:</p>
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
                          7-Zip 설치 방법
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
                          Windows (winget 사용):
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
                            title="복사"
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
                        <p className="text-xs text-ark-gray mb-2">수동 설치:</p>
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
                          {flatcGuide.name} 설치 방법
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
                          Windows (winget 사용):
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
                            title="복사"
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
                        <p className="text-xs text-ark-gray mb-2">수동 설치:</p>
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
                    게임 데이터
                  </h3>
                  <p className="text-[11px] text-ark-gray/70 mb-3">
                    스토리 텍스트를 다운로드합니다. 스토리 표시에 필수입니다.
                  </p>
                  <div className="p-4 bg-ark-black/50 rounded border border-ark-border">
                    {gamedataStatus === null ? (
                      <p className="text-sm text-ark-gray">확인 중...</p>
                    ) : (
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <p className="text-sm text-ark-white">
                              {gamedataStatus.exists ? (
                                <>
                                  스토리 데이터 준비됨 (
                                  {gamedataStatus.story_count}개 파일)
                                </>
                              ) : (
                                <>스토리 데이터 없음</>
                              )}
                            </p>
                            {gamedataStatus.last_updated && (
                              <p className="text-xs text-ark-gray mt-1">
                                마지막 업데이트:{" "}
                                {new Date(
                                  gamedataStatus.last_updated,
                                ).toLocaleString("ko-KR")}
                              </p>
                            )}
                          </div>
                          {!isUpdatingGamedata &&
                            gamedataUpdateProgress?.stage !== "complete" && (
                              <button
                                onClick={startGamedataUpdate}
                                className="ark-btn ark-btn-primary text-sm"
                              >
                                {gamedataStatus.exists
                                  ? "데이터 업데이트"
                                  : "데이터 다운로드"}
                              </button>
                            )}
                        </div>

                        {/* 업데이트 진행률 */}
                        {isUpdatingGamedata && gamedataUpdateProgress && (
                          <div className="mt-3">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-xs text-ark-gray">
                                {gamedataUpdateProgress.message}
                              </span>
                              <button
                                onClick={cancelGamedataUpdate}
                                className="text-xs text-red-400 hover:text-red-300"
                              >
                                취소
                              </button>
                            </div>
                            <div className="relative h-2 bg-ark-panel rounded overflow-hidden">
                              <div
                                className="absolute inset-y-0 left-0 bg-ark-orange transition-all duration-300"
                                style={{
                                  width: `${gamedataUpdateProgress.progress * 100}%`,
                                }}
                              />
                            </div>
                          </div>
                        )}

                        {/* 완료 메시지 */}
                        {gamedataUpdateProgress?.stage === "complete" &&
                          !isUpdatingGamedata && (
                            <div className="mt-3 p-2 bg-green-500/10 border border-green-500/30 rounded">
                              <div className="flex items-center justify-between">
                                <p className="text-xs text-green-400">
                                  {gamedataUpdateProgress.message}
                                </p>
                                <button
                                  onClick={refreshCharacterData}
                                  disabled={isRefreshingCharacters}
                                  className="text-xs text-ark-orange hover:underline disabled:opacity-50"
                                >
                                  {isRefreshingCharacters
                                    ? "새로고침 중..."
                                    : "캐릭터 데이터 새로고침"}
                                </button>
                              </div>
                            </div>
                          )}

                        {/* 에러 메시지 */}
                        {gamedataUpdateError && (
                          <div className="mt-3 p-2 bg-red-500/10 border border-red-500/30 rounded">
                            <p className="text-xs text-red-400">
                              {gamedataUpdateError}
                            </p>
                          </div>
                        )}

                        <div className="mt-3 pt-3 border-t border-ark-border">
                          <label className="text-xs text-ark-gray block mb-1">
                            데이터 소스
                          </label>
                          <select
                            value={gamedataSource}
                            onChange={(e) => changeGamedataSource(e.target.value)}
                            disabled={isUpdatingGamedata}
                            className="w-full px-2 py-1 text-xs bg-ark-black border border-ark-border rounded text-ark-white focus:border-ark-orange focus:outline-none disabled:opacity-50"
                          >
                            <option value="github">GitHub (ArknightsGamedata)</option>
                            <option value="arkprts">arkprts (게임 서버 직접)</option>
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
                                {isRepoSaving ? '...' : '저장'}
                              </button>
                            </div>
                          )}
                          {gamedataSource === 'arkprts' && (
                            <p className="text-[10px] text-ark-gray/60 mt-1">
                              게임 서버에서 직접 최신 데이터를 다운로드합니다.
                            </p>
                          )}
                        </div>

                        {/* 수동 캐릭터 새로고침 */}
                        {gamedataStatus?.exists && (
                          <div className="flex items-center justify-between mt-2 pt-2 border-t border-ark-border">
                            <span className="text-xs text-ark-gray">
                              캐릭터 매핑 캐시
                            </span>
                            <button
                              onClick={refreshCharacterData}
                              disabled={isRefreshingCharacters}
                              className="text-xs text-ark-orange hover:underline disabled:opacity-50"
                            >
                              {isRefreshingCharacters
                                ? "새로고침 중..."
                                : "새로고침"}
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </section>

                {/* 음성 추출 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-2">
                    음성 추출
                  </h3>
                  <p className="text-[11px] text-ark-gray/70 mb-3">
                    게임 음성 번들에서 캐릭터별 MP3를 추출합니다. 음성 학습과 제로샷 TTS에 사용됩니다.
                  </p>
                  <div className="p-4 bg-ark-black/50 rounded border border-ark-border">
                    {voiceAssetsStatus === null ? (
                      <p className="text-sm text-ark-gray">확인 중...</p>
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
                              Assets/Voice 준비됨
                            </p>
                            <p className="text-xs text-ark-gray mt-1">
                              {Object.entries(
                                voiceAssetsStatus.languages || {},
                              ).map(([lang, count]) => (
                                <span key={lang} className="mr-3">
                                  {lang}: {count}개 번들
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
                                음성 추출
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
                                취소
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
                              {extractProgress.processed} /{" "}
                              {extractProgress.total} 파일 처리됨 •{" "}
                              {extractProgress.extracted}개 추출됨
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
                        <span className="text-ark-gray">게임 원본:</span> Android/Data/com.YoStarKR.Arknights/files/Bundles/audio/sound_beta_2/voice_kr
                      </p>
                      <div className="flex items-center justify-between">
                        <p className="text-[10px] text-ark-gray/60">
                          <span className="text-ark-gray">복사 위치:</span> Assets/Voice/voice_kr
                        </p>
                        <button
                          onClick={async () => {
                            try {
                              if (voiceAssetsStatus?.exists) {
                                await settingsApi.openFolder('Assets/Voice/voice_kr');
                              } else {
                                await settingsApi.createFolder('Assets/Voice/voice_kr');
                                checkVoiceAssets();
                              }
                            } catch (err) {
                              console.error('폴더 작업 실패:', err);
                            }
                          }}
                          className="text-[10px] text-ark-cyan hover:text-ark-white transition-colors"
                        >
                          {voiceAssetsStatus?.exists ? '열기' : '폴더 생성'}
                        </button>
                      </div>
                      <p className="text-[10px] text-ark-gray/60">
                        <span className="text-ark-gray">추출 결과:</span> extracted/ 폴더에 캐릭터별 MP3 생성
                      </p>
                    </div>
                  </div>
                </section>

                {/* 이미지 추출 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-2">
                    이미지 추출
                  </h3>
                  <p className="text-[11px] text-ark-gray/70 mb-3">
                    캐릭터 일러스트 번들에서 이미지를 추출합니다. 두 종류의 이미지를 각각 추출할 수 있습니다.
                  </p>

                  {imageAssetsStatus === null ? (
                    <div className="p-4 bg-ark-black/50 rounded border border-ark-border">
                      <p className="text-sm text-ark-gray">확인 중...</p>
                    </div>
                  ) : !imageAssetsStatus.exists ? (
                    <div className="p-4 bg-ark-black/50 rounded border border-ark-border">
                      <p className="text-sm text-red-400 mb-2">
                        {imageAssetsStatus.message}
                      </p>
                      <p className="text-xs text-ark-gray">
                        {imageAssetsStatus.hint}
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {/* 카드 1: 캐릭터 일러스트 (characters) */}
                      <div className="p-4 bg-ark-black/50 rounded border border-ark-border">
                        <div className="flex items-center justify-between mb-2">
                          <div>
                            <p className="text-sm text-ark-white font-medium">캐릭터 일러스트</p>
                            <p className="text-[10px] text-ark-gray mt-0.5">대화 화면에 표시되는 캐릭터 전신 일러스트</p>
                          </div>
                          {imageAssetsStatus.characters_exists && !isExtractingImages && (
                            <button
                              onClick={() => startImageExtraction('characters')}
                              className="ark-btn ark-btn-primary text-xs"
                            >
                              추출
                            </button>
                          )}
                        </div>

                        {!imageAssetsStatus.characters_exists ? (
                          <div className="p-2 bg-yellow-500/10 border border-yellow-500/30 rounded">
                            <p className="text-xs text-yellow-400">폴더 없음 — 게임 번들의 avg/characters를 복사해주세요</p>
                          </div>
                        ) : (
                          <p className="text-xs text-green-400/80">{imageAssetsStatus.characters_bundles ?? 0}개 번들 준비됨</p>
                        )}

                        {/* 진행률/완료 (이 카드 대상일 때만) */}
                        {extractingImageTarget === 'characters' && (
                          <>
                            {isExtractingImages && imageExtractProgress && (
                              <div className="mt-3">
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-xs text-ark-gray">{imageExtractProgress.message}</span>
                                  <button onClick={cancelImageExtraction} className="text-xs text-red-400 hover:text-red-300">취소</button>
                                </div>
                                {imageExtractProgress.total > 0 && (
                                  <div className="relative h-2 bg-ark-panel rounded overflow-hidden">
                                    <div className="absolute inset-y-0 left-0 bg-ark-orange transition-all duration-300" style={{ width: `${(imageExtractProgress.processed / imageExtractProgress.total) * 100}%` }} />
                                  </div>
                                )}
                                <p className="text-xs text-ark-gray mt-1">{imageExtractProgress.processed} / {imageExtractProgress.total} 처리됨 • {imageExtractProgress.extracted}개 추출</p>
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
                            <span className="text-ark-gray">게임 원본:</span> Android/Data/com.YoStarKR.Arknights/files/Bundles/Assets/Image/avg/characters
                          </p>
                          <div className="flex items-center justify-between">
                            <p className="text-[10px] text-ark-gray/60">
                              <span className="text-ark-gray">복사 위치:</span> Assets/Image/avg/characters
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
                                  console.error('폴더 작업 실패:', err);
                                }
                              }}
                              className="text-[10px] text-ark-cyan hover:text-ark-white transition-colors"
                            >
                              {imageAssetsStatus?.characters_exists ? '열기' : '폴더 생성'}
                            </button>
                          </div>
                          <p className="text-[10px] text-ark-gray/60">
                            <span className="text-ark-gray">추출 결과:</span> extracted/images/ 폴더에 PNG 생성
                          </p>
                        </div>
                      </div>

                      {/* 카드 2: 캐릭터 초상화 (chararts) */}
                      <div className="p-4 bg-ark-black/50 rounded border border-ark-border">
                        <div className="flex items-center justify-between mb-2">
                          <div>
                            <p className="text-sm text-ark-white font-medium">캐릭터 초상화</p>
                            <p className="text-[10px] text-ark-gray mt-0.5">캐릭터 얼굴 아이콘 (프로필, 매핑 표시용)</p>
                          </div>
                          {imageAssetsStatus.chararts_exists && !isExtractingImages && (
                            <button
                              onClick={() => startImageExtraction('chararts')}
                              className="ark-btn ark-btn-primary text-xs"
                            >
                              추출
                            </button>
                          )}
                        </div>

                        {!imageAssetsStatus.chararts_exists ? (
                          <div className="p-2 bg-yellow-500/10 border border-yellow-500/30 rounded">
                            <p className="text-xs text-yellow-400">폴더 없음 — 게임 번들의 chararts를 복사해주세요</p>
                          </div>
                        ) : (
                          <p className="text-xs text-green-400/80">{imageAssetsStatus.chararts_bundles ?? 0}개 번들 준비됨</p>
                        )}

                        {/* 진행률/완료 (이 카드 대상일 때만) */}
                        {extractingImageTarget === 'chararts' && (
                          <>
                            {isExtractingImages && imageExtractProgress && (
                              <div className="mt-3">
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-xs text-ark-gray">{imageExtractProgress.message}</span>
                                  <button onClick={cancelImageExtraction} className="text-xs text-red-400 hover:text-red-300">취소</button>
                                </div>
                                {imageExtractProgress.total > 0 && (
                                  <div className="relative h-2 bg-ark-panel rounded overflow-hidden">
                                    <div className="absolute inset-y-0 left-0 bg-ark-orange transition-all duration-300" style={{ width: `${(imageExtractProgress.processed / imageExtractProgress.total) * 100}%` }} />
                                  </div>
                                )}
                                <p className="text-xs text-ark-gray mt-1">{imageExtractProgress.processed} / {imageExtractProgress.total} 처리됨 • {imageExtractProgress.extracted}개 추출</p>
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
                            <span className="text-ark-gray">게임 원본:</span> Android/Data/com.YoStarKR.Arknights/files/Bundles/Assets/Image/chararts
                          </p>
                          <div className="flex items-center justify-between">
                            <p className="text-[10px] text-ark-gray/60">
                              <span className="text-ark-gray">복사 위치:</span> Assets/Image/chararts
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
                                  console.error('폴더 작업 실패:', err);
                                }
                              }}
                              className="text-[10px] text-ark-cyan hover:text-ark-white transition-colors"
                            >
                              {imageAssetsStatus?.chararts_exists ? '열기' : '폴더 생성'}
                            </button>
                          </div>
                          <p className="text-[10px] text-ark-gray/60">
                            <span className="text-ark-gray">추출 결과:</span> extracted/images/ 폴더에 PNG 생성
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
                  <span>음성 설정</span>
                </div>

                {/* 캐릭터 별칭 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-3">
                    캐릭터 별칭 (본명)
                  </h3>
                  <div className="p-4 bg-ark-black/50 rounded border border-ark-border">
                    <p className="text-xs text-ark-gray mb-3">
                      스토리에서 본명으로 등장하는 캐릭터를 오퍼레이터와 연결합니다.
                      <br />
                      예: "조르디" → 루멘, "안젤리나" → 안젤리나
                    </p>

                    <div className="flex items-center gap-3 mb-3">
                      <div className="flex-1">
                        <span className="text-sm text-ark-white">
                          등록된 별칭: {aliasesInfo?.total ?? 0}개
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
                        {isExtractingAliases ? "추출 중..." : "본명 자동 추출"}
                      </button>
                    </div>

                    {aliasExtractResult && (
                      <div className="p-2 bg-green-500/10 border border-green-500/30 rounded text-xs text-green-400">
                        ✓ {aliasExtractResult.extracted_count}명의 캐릭터에서 {aliasExtractResult.alias_count}개 별칭 추가됨
                      </div>
                    )}

                    <p className="text-[10px] text-ark-gray/60 mt-2">
                      * handbook 데이터에서 "본명은 XXX" 패턴을 추출합니다
                    </p>
                  </div>
                </section>

                {/* ===== 고급 설정 ===== */}
                <div className="ark-divider mt-2">
                  <span>고급 설정</span>
                </div>

                {/* TTS 추론 파라미터 */}
                <TTSParamsSection />

                {/* 언어 설정 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-2">
                    언어
                  </h3>
                  <p className="text-[11px] text-ark-gray/70 mb-3">
                    게임 클라이언트 언어와 TTS 합성 언어를 표시합니다.
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 bg-ark-black/50 rounded border border-ark-border">
                      <p className="text-xs text-ark-gray mb-1">게임 언어</p>
                      <p className="text-sm text-ark-white">
                        {settings.game_language}
                      </p>
                    </div>
                    <div className="p-3 bg-ark-black/50 rounded border border-ark-border">
                      <p className="text-xs text-ark-gray mb-1">
                        GPT-SoVITS 언어
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
                    경로
                  </h3>
                  <p className="text-[11px] text-ark-gray/70 mb-3">
                    주요 리소스 폴더 경로입니다. 폴더 열기 버튼으로 탐색기에서 확인할 수 있습니다.
                  </p>
                  <div className="space-y-2">
                    <PathItem
                      label="GPT-SoVITS"
                      path={settings.gpt_sovits_path}
                      onOpen={() => handleOpenFolder(settings.gpt_sovits_path)}
                    />
                    <PathItem
                      label="모델"
                      path={settings.models_path}
                      onOpen={() => handleOpenFolder(settings.models_path)}
                    />
                    <PathItem
                      label="추출된 음성"
                      path={settings.extracted_path}
                      onOpen={() => handleOpenFolder(settings.extracted_path)}
                    />
                    <PathItem
                      label="게임 데이터"
                      path={settings.gamedata_path}
                      onOpen={() => handleOpenFolder(settings.gamedata_path)}
                    />
                  </div>
                </section>

                {/* Whisper 전처리 설정 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-2">
                    Whisper 전처리
                  </h3>
                  <p className="text-[11px] text-ark-gray/70 mb-3">
                    음성 학습 전처리에 사용되는 Whisper 설정입니다. 기본값으로도 충분합니다.
                  </p>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="p-3 bg-ark-black/50 rounded border border-ark-border">
                      <p className="text-xs text-ark-gray mb-1">모델</p>
                      <p className="text-sm text-ark-white">
                        {settings.whisper_model_size}
                      </p>
                    </div>
                    <div className="p-3 bg-ark-black/50 rounded border border-ark-border">
                      <p className="text-xs text-ark-gray mb-1">연산 타입</p>
                      <p className="text-sm text-ark-white">
                        {settings.whisper_compute_type}
                      </p>
                    </div>
                    <div className="p-3 bg-ark-black/50 rounded border border-ark-border">
                      <p className="text-xs text-ark-gray mb-1">사용</p>
                      <p
                        className={`text-sm ${settings.use_whisper_preprocessing ? "text-green-400" : "text-red-400"}`}
                      >
                        {settings.use_whisper_preprocessing
                          ? "활성화"
                          : "비활성화"}
                      </p>
                    </div>
                  </div>
                  <p className="text-xs text-ark-gray/70 mt-2">
                    * 음성 준비 시 Faster-Whisper로 긴 오디오를 분할합니다
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
            닫기
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
      desc: '음성 랜덤성 (낮을수록 안정, 높을수록 다양)',
      min: 0.1, max: 2.0, step: 0.05,
    },
    {
      key: 'top_k' as const,
      label: 'Top K',
      desc: '샘플링 다양성 (5~15 권장)',
      min: 1, max: 30, step: 1,
    },
    {
      key: 'top_p' as const,
      label: 'Top P',
      desc: 'Nucleus sampling (1.0이면 비활성)',
      min: 0.1, max: 1.0, step: 0.05,
    },
    {
      key: 'speed_factor' as const,
      label: '음성 속도',
      desc: '1.0 = 기본 속도',
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
          <h3 className="text-sm font-medium text-ark-white">TTS 추론 파라미터</h3>
          <p className="text-[11px] text-ark-gray/70 text-left">
            기본값 권장. 음성 합성 품질에 영향을 주는 파라미터입니다.
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
            <p className="text-sm text-ark-gray">로딩 중...</p>
          ) : (
            <>
              <p className="text-xs text-ark-gray">
                변경 즉시 적용됩니다.
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
        열기
      </button>
    </div>
  );
}
