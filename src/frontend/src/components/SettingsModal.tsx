import { useEffect, useState, useRef } from "react";
import { useAppStore } from "../stores/appStore";
import {
  settingsApi,
  extractApi,
  createExtractStream,
  imageExtractApi,
  createImageExtractStream,
  gamedataApi,
  createGamedataUpdateStream,
  voiceApi,
  type SettingsResponse,
  type DependencyStatus,
  type FFmpegInstallGuide,
  type SevenZipInstallGuide,
  type FlatcInstallGuide,
  type SoxInstallGuide,
  type VoiceAssetsStatus,
  type ExtractProgress,
  type ImageAssetsStatus,
  type ImageExtractProgress,
  type GamedataStatus,
  type GamedataUpdateProgress,
  type TTSEngine,
  type TTSEngineSetting,
} from "../services/api";
import GPTSoVITSInstallDialog from "./GPTSoVITSInstallDialog";
import Qwen3TTSInstallDialog from "./Qwen3TTSInstallDialog";
import Qwen3TTSSettings from "./Qwen3TTSSettings";
import SoxInstallDialog from "./SoxInstallDialog";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { loadTtsEngineSetting: syncAppStoreEngine } = useAppStore();
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [ffmpegGuide, setFFmpegGuide] = useState<FFmpegInstallGuide | null>(
    null,
  );
  const [sevenZipGuide, setSevenZipGuide] =
    useState<SevenZipInstallGuide | null>(null);
  const [flatcGuide, setFlatcGuide] = useState<FlatcInstallGuide | null>(null);
  const [soxGuide, setSoxGuide] = useState<SoxInstallGuide | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showFFmpegGuide, setShowFFmpegGuide] = useState(false);
  const [show7ZipGuide, setShow7ZipGuide] = useState(false);
  const [showFlatcGuide, setShowFlatcGuide] = useState(false);
  const [showSoxGuide, setShowSoxGuide] = useState(false);
  const [showGptSovitsInstall, setShowGptSovitsInstall] = useState(false);
  const [showQwen3TtsInstall, setShowQwen3TtsInstall] = useState(false);
  const [showSoxInstall, setShowSoxInstall] = useState(false);
  const [isRefreshingCharacters, setIsRefreshingCharacters] = useState(false);

  // TTS 엔진 설정
  const [ttsEngineSetting, setTtsEngineSetting] = useState<TTSEngineSetting | null>(null);
  const [isChangingEngine, setIsChangingEngine] = useState(false);

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

  useEffect(() => {
    if (isOpen) {
      loadSettings();
      checkVoiceAssets();
      checkImageAssets();
      checkGamedataStatus();
      loadTTSEngineSetting();
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

  const loadSoxGuide = async () => {
    try {
      const guide = await settingsApi.getSoxGuide();
      setSoxGuide(guide);
      setShowSoxGuide(true);
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

  const loadTTSEngineSetting = async () => {
    try {
      const setting = await settingsApi.getTTSEngineSetting();
      setTtsEngineSetting(setting);
    } catch (err) {
      console.error("TTS 엔진 설정 로드 실패:", err);
    }
  };

  const changeTTSEngine = async (engine: TTSEngine) => {
    setIsChangingEngine(true);
    try {
      await settingsApi.setTTSEngineSetting(engine);
      await loadTTSEngineSetting();
      await syncAppStoreEngine();  // 헤더 UI 업데이트
    } catch (err) {
      console.error("TTS 엔진 변경 실패:", err);
    } finally {
      setIsChangingEngine(false);
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

  const startImageExtraction = async () => {
    if (!imageAssetsStatus?.exists || !imageAssetsStatus?.characters_exists)
      return;

    setIsExtractingImages(true);
    setImageExtractProgress(null);
    setImageExtractError(null);

    try {
      await imageExtractApi.startExtract();

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
      const data = await settingsApi.checkDependencies();
      if (settings) {
        setSettings({ ...settings, dependencies: data.dependencies });
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
                          <button
                            onClick={loadFFmpegGuide}
                            className="text-xs text-ark-orange hover:underline"
                          >
                            설치 방법
                          </button>
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
                        {!dep.installed && dep.name === "SoX" && (
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => setShowSoxInstall(true)}
                              className="text-xs text-ark-orange hover:underline"
                            >
                              자동 설치
                            </button>
                            <span className="text-ark-gray">|</span>
                            <button
                              onClick={loadSoxGuide}
                              className="text-xs text-ark-gray hover:text-ark-white"
                            >
                              수동 설치
                            </button>
                          </div>
                        )}
                        {!dep.installed && dep.name === "GPT-SoVITS" && (
                          <button
                            onClick={() => setShowGptSovitsInstall(true)}
                            className="text-xs text-ark-orange hover:underline"
                          >
                            자동 설치
                          </button>
                        )}
                        {dep.name === "Qwen3-TTS" && (
                          <button
                            onClick={() => setShowQwen3TtsInstall(true)}
                            className="text-xs text-ark-orange hover:underline"
                          >
                            {dep.installed ? "설정/모델 다운로드" : "자동 설치"}
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

                  {/* SoX 설치 가이드 */}
                  {showSoxGuide && soxGuide && (
                    <div className="mt-3 p-4 bg-ark-panel rounded border border-ark-border">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-medium text-ark-white">
                          {soxGuide.name} 설치 방법
                        </h4>
                        <button
                          onClick={() => setShowSoxGuide(false)}
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
                          {soxGuide.description}
                        </p>
                      </div>

                      {/* 경고 메시지 */}
                      <div className="mb-4 p-2 bg-yellow-500/10 border border-yellow-500/30 rounded">
                        <p className="text-xs text-yellow-400">
                          {soxGuide.note}
                        </p>
                      </div>

                      {/* winget 방법 */}
                      <div className="mb-4">
                        <p className="text-xs text-ark-gray mb-2">
                          Windows (winget 사용):
                        </p>
                        <div className="flex items-center gap-2">
                          <code className="flex-1 px-3 py-2 bg-ark-black rounded text-sm text-ark-white font-mono">
                            {soxGuide.windows.command}
                          </code>
                          <button
                            onClick={() =>
                              navigator.clipboard.writeText(
                                soxGuide.windows.command,
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
                          {soxGuide.manual_steps.map((step, i) => (
                            <li key={i}>{step}</li>
                          ))}
                        </ol>
                      </div>
                    </div>
                  )}
                </section>

                {/* 게임 데이터 업데이트 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-3">
                    게임 데이터
                  </h3>
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

                        <p className="text-xs text-ark-gray mt-3">
                          arkprts를 통해 한국 서버의 최신 스토리 데이터를
                          다운로드합니다.
                        </p>

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
                  <h3 className="text-sm font-medium text-ark-white mb-3">
                    음성 추출
                  </h3>
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
                  </div>
                </section>

                {/* 이미지 추출 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-3">
                    이미지 추출
                  </h3>
                  <div className="p-4 bg-ark-black/50 rounded border border-ark-border">
                    {imageAssetsStatus === null ? (
                      <p className="text-sm text-ark-gray">확인 중...</p>
                    ) : !imageAssetsStatus.exists ? (
                      <div>
                        <p className="text-sm text-red-400 mb-2">
                          {imageAssetsStatus.message}
                        </p>
                        <p className="text-xs text-ark-gray">
                          {imageAssetsStatus.hint}
                        </p>
                      </div>
                    ) : !imageAssetsStatus.characters_exists ? (
                      <div>
                        <p className="text-sm text-yellow-400 mb-2">
                          Assets/Image/avg/characters 폴더가 없습니다
                        </p>
                        <p className="text-xs text-ark-gray">
                          게임 번들의 files/bundles/avg/characters를
                          복사해주세요
                        </p>
                      </div>
                    ) : (
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <p className="text-sm text-ark-white">
                              Assets/Image 준비됨
                            </p>
                            <p className="text-xs text-ark-gray mt-1">
                              {imageAssetsStatus.total_bundles}개 번들
                            </p>
                          </div>
                          {!isExtractingImages &&
                            imageExtractProgress?.stage !== "complete" && (
                              <button
                                onClick={startImageExtraction}
                                className="ark-btn ark-btn-primary text-sm"
                              >
                                이미지 추출
                              </button>
                            )}
                        </div>

                        {/* 추출 진행률 */}
                        {isExtractingImages && imageExtractProgress && (
                          <div className="mt-3">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-xs text-ark-gray">
                                {imageExtractProgress.message}
                              </span>
                              <button
                                onClick={cancelImageExtraction}
                                className="text-xs text-red-400 hover:text-red-300"
                              >
                                취소
                              </button>
                            </div>
                            {imageExtractProgress.total > 0 && (
                              <div className="relative h-2 bg-ark-panel rounded overflow-hidden">
                                <div
                                  className="absolute inset-y-0 left-0 bg-ark-orange transition-all duration-300"
                                  style={{
                                    width: `${(imageExtractProgress.processed / imageExtractProgress.total) * 100}%`,
                                  }}
                                />
                              </div>
                            )}
                            <p className="text-xs text-ark-gray mt-1">
                              {imageExtractProgress.processed} /{" "}
                              {imageExtractProgress.total} 파일 처리됨 •{" "}
                              {imageExtractProgress.extracted}개 추출됨
                            </p>
                          </div>
                        )}

                        {/* 완료 메시지 */}
                        {imageExtractProgress?.stage === "complete" &&
                          !isExtractingImages && (
                            <div className="mt-3 p-2 bg-green-500/10 border border-green-500/30 rounded">
                              <p className="text-xs text-green-400">
                                {imageExtractProgress.message}
                              </p>
                            </div>
                          )}

                        {/* 에러 메시지 */}
                        {imageExtractError && (
                          <div className="mt-3 p-2 bg-red-500/10 border border-red-500/30 rounded">
                            <p className="text-xs text-red-400">
                              {imageExtractError}
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </section>

                {/* 경로 설정 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-3">
                    경로
                  </h3>
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

                {/* TTS 엔진 설정 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-3">
                    TTS 엔진
                  </h3>
                  <div className="p-4 bg-ark-black/50 rounded border border-ark-border">
                    {ttsEngineSetting === null ? (
                      <p className="text-sm text-ark-gray">로딩 중...</p>
                    ) : (
                      <div className="space-y-3">
                        <p className="text-xs text-ark-gray mb-2">
                          앱 전체에서 사용할 TTS 엔진을 선택합니다.
                        </p>
                        <div className="flex gap-2 flex-wrap">
                          {/* GPT-SoVITS */}
                          <button
                            onClick={() => changeTTSEngine("gpt_sovits")}
                            disabled={isChangingEngine || !ttsEngineSetting.engine_status.gpt_sovits?.installed}
                            className={`px-4 py-2 rounded border transition-colors ${
                              ttsEngineSetting.engine === "gpt_sovits"
                                ? "bg-ark-orange/20 border-ark-orange text-ark-orange"
                                : ttsEngineSetting.engine_status.gpt_sovits?.installed
                                  ? "bg-ark-panel border-ark-border text-ark-gray hover:text-ark-white hover:border-ark-orange/50"
                                  : "bg-ark-panel/50 border-ark-border/50 text-ark-gray/50 cursor-not-allowed"
                            }`}
                          >
                            <div className="text-sm font-medium">GPT-SoVITS</div>
                            <div className="text-[10px] opacity-70">
                              {ttsEngineSetting.engine_status.gpt_sovits?.installed ? "v2" : "미설치"}
                            </div>
                          </button>

                          {/* Qwen3-TTS */}
                          <button
                            onClick={() => changeTTSEngine("qwen3_tts")}
                            disabled={isChangingEngine || !ttsEngineSetting.engine_status.qwen3_tts?.installed}
                            className={`px-4 py-2 rounded border transition-colors ${
                              ttsEngineSetting.engine === "qwen3_tts"
                                ? "bg-ark-orange/20 border-ark-orange text-ark-orange"
                                : ttsEngineSetting.engine_status.qwen3_tts?.installed
                                  ? "bg-ark-panel border-ark-border text-ark-gray hover:text-ark-white hover:border-ark-orange/50"
                                  : "bg-ark-panel/50 border-ark-border/50 text-ark-gray/50 cursor-not-allowed"
                            }`}
                          >
                            <div className="text-sm font-medium">Qwen3-TTS</div>
                            <div className="text-[10px] opacity-70">
                              {ttsEngineSetting.engine_status.qwen3_tts?.installed ? "1.7B" : "미설치"}
                            </div>
                          </button>
                        </div>

                        {/* 현재 선택된 엔진 설명 */}
                        <div className="mt-2 p-2 bg-ark-panel/50 rounded text-xs text-ark-gray">
                          {ttsEngineSetting.engine === "gpt_sovits" && (
                            <span>캐릭터별 학습 후 최상의 품질. 학습 안 된 캐릭터는 제로샷 모드로 동작.</span>
                          )}
                          {ttsEngineSetting.engine === "qwen3_tts" && (
                            <span>참조 오디오만으로 즉시 사용. 파인튜닝 모델이 있으면 우선 사용.</span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </section>

                {/* Qwen3-TTS 설정 */}
                {ttsEngineSetting?.engine_status.qwen3_tts?.installed && (
                  <section>
                    <h3 className="text-sm font-medium text-ark-white mb-3">
                      Qwen3-TTS 설정
                    </h3>
                    <Qwen3TTSSettings
                      isInstalled={ttsEngineSetting.engine_status.qwen3_tts.installed}
                    />
                  </section>
                )}

                {/* 언어 설정 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-3">
                    언어
                  </h3>
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

                {/* Whisper 전처리 설정 */}
                <section>
                  <h3 className="text-sm font-medium text-ark-white mb-3">
                    Whisper 전처리
                  </h3>
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

      {/* Qwen3-TTS 설치 다이얼로그 */}
      <Qwen3TTSInstallDialog
        isOpen={showQwen3TtsInstall}
        onClose={() => setShowQwen3TtsInstall(false)}
        onInstallComplete={() => {
          refreshDependencies();
          setShowQwen3TtsInstall(false);
        }}
      />

      {/* SoX 설치 다이얼로그 */}
      <SoxInstallDialog
        isOpen={showSoxInstall}
        onClose={() => setShowSoxInstall(false)}
        onInstallComplete={() => {
          refreshDependencies();
          setShowSoxInstall(false);
        }}
      />
    </div>
  );
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
