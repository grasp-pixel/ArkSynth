import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { settingsApi, createInstallStream, type InstallProgress, type GptSovitsInstallInfo } from '../services/api'

interface GPTSoVITSInstallDialogProps {
  isOpen: boolean
  onClose: () => void
  onInstallComplete: () => void
}

export default function GPTSoVITSInstallDialog({
  isOpen,
  onClose,
  onInstallComplete,
}: GPTSoVITSInstallDialogProps) {
  const { t } = useTranslation()
  const [installInfo, setInstallInfo] = useState<GptSovitsInstallInfo | null>(null)
  const [isInstalling, setIsInstalling] = useState(false)
  const [progress, setProgress] = useState<InstallProgress | null>(null)
  const [error, setError] = useState<string | null>(null)
  const streamRef = useRef<{ close: () => void } | null>(null)

  // PyTorch 업그레이드 단계 감지 (GPU 비호환 시에만 서버에서 전송)
  const [hasPytorchUpgrade, setHasPytorchUpgrade] = useState(false)

  const STAGES = [
    { id: 'downloading', label: t('install.stage.downloading') },
    { id: 'extracting', label: t('install.stage.extracting') },
    { id: 'verifying', label: t('install.stage.verifying') },
    ...(hasPytorchUpgrade ? [{ id: 'pytorch_upgrade', label: t('install.stage.pytorchUpgrade') }] : []),
    { id: 'complete', label: t('install.stage.complete') },
  ]

  function getStageIndex(stage: string | undefined): number {
    if (!stage) return -1
    // upgrade_pytorch 내부 stage를 pytorch_upgrade로 매핑
    const mapped = (stage === 'upgrading' || stage === 'checking') ? 'pytorch_upgrade' : stage
    const index = STAGES.findIndex(s => s.id === mapped)
    return index
  }

  useEffect(() => {
    if (isOpen) {
      loadInstallInfo()
    }
    return () => {
      // 컴포넌트 언마운트 시 스트림 정리
      if (streamRef.current) {
        streamRef.current.close()
        streamRef.current = null
      }
    }
  }, [isOpen])

  const loadInstallInfo = async () => {
    try {
      const info = await settingsApi.getGptSovitsInstallInfo()
      setInstallInfo(info)
    } catch (err) {
      console.error(t('install.error.loadFailed'), err)
    }
  }

  const handleStartInstall = async () => {
    setIsInstalling(true)
    setProgress({ stage: 'downloading_python', progress: 0, message: t('install.status.starting') })
    setError(null)

    try {
      // 설치 시작 요청
      await settingsApi.startGptSovitsInstall()

      // SSE 스트림 연결
      streamRef.current = createInstallStream({
        onProgress: (p) => {
          setProgress(p)
          if (p.stage === 'pytorch_upgrade' || p.stage === 'upgrading') {
            setHasPytorchUpgrade(true)
          }
          if (p.error) {
            setError(p.error)
          }
        },
        onComplete: () => {
          setIsInstalling(false)
          setProgress({ stage: 'complete', progress: 1, message: t('install.status.complete') })
          loadInstallInfo()
          onInstallComplete()
        },
        onError: (err) => {
          setIsInstalling(false)
          setError(err)
        },
      })
    } catch (err) {
      setIsInstalling(false)
      setError(err instanceof Error ? err.message : t('install.error.startFailed'))
    }
  }

  const handleCancelInstall = async () => {
    try {
      await settingsApi.cancelGptSovitsInstall()
      if (streamRef.current) {
        streamRef.current.close()
        streamRef.current = null
      }
      setIsInstalling(false)
      setProgress(null)
    } catch (err) {
      console.error(t('install.error.cancelFailed'), err)
    }
  }

  const handleCleanup = async () => {
    if (!confirm(t('install.confirm.deleteFolder'))) return

    try {
      await settingsApi.cleanupGptSovitsInstall()
      loadInstallInfo()
      setProgress(null)
      setError(null)
    } catch (err) {
      console.error(t('install.error.cleanupFailed'), err)
    }
  }

  if (!isOpen) return null

  const currentStageIndex = getStageIndex(progress?.stage)

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      {/* 오버레이 */}
      <div
        className="absolute inset-0 bg-black/80"
        onClick={!isInstalling ? onClose : undefined}
      />

      {/* 다이얼로그 */}
      <div className="relative bg-ark-dark border border-ark-border rounded-lg w-full max-w-lg overflow-hidden">
        {/* 헤더 */}
        <div className="p-4 border-b border-ark-border flex items-center justify-between">
          <h3 className="text-lg font-bold text-ark-white">
            {t('install.title')}
          </h3>
          {!isInstalling && (
            <button
              onClick={onClose}
              className="text-ark-gray hover:text-ark-white transition-colors"
            >
              <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
              </svg>
            </button>
          )}
        </div>

        {/* 컨텐츠 */}
        <div className="p-4">
          {!isInstalling && !progress ? (
            // 설치 옵션 폼
            <div className="space-y-4">
              {/* 현재 상태 */}
              {installInfo && (
                <div className="p-3 bg-ark-black/50 rounded border border-ark-border">
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`w-2 h-2 rounded-full ${installInfo.is_installed ? 'bg-green-500' : 'bg-yellow-500'}`} />
                    <span className="text-sm text-ark-white">
                      {installInfo.is_installed ? t('install.status.installed') : t('install.status.notInstalled')}
                    </span>
                  </div>
                  {installInfo.is_installed && (
                    <div className="text-xs text-ark-gray space-y-1">
                      {installInfo.torch_version && (
                        <p>{t('install.info.pytorch', { version: installInfo.torch_version })}</p>
                      )}
                      {installInfo.cuda_available !== undefined && (
                        <p>{installInfo.cuda_available ? t('install.info.cudaAvailable') : t('install.info.cudaNotAvailable')}</p>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* 설치 안내 */}
              <div className="p-3 bg-ark-panel rounded border border-ark-border">
                <p className="text-sm text-ark-white mb-2">{t('install.section.items')}</p>
                <ul className="text-xs text-ark-gray space-y-1">
                  <li>{t('install.item.gptSovits')}</li>
                  <li>{t('install.item.python')}</li>
                  <li>{t('install.item.pytorch')}</li>
                  <li>{t('install.item.dependencies')}</li>
                </ul>
                <p className="text-xs text-ark-orange mt-2">
                  {t('install.info.diskSpace')}
                </p>
              </div>

              {/* GPU 정보 */}
              <div className="p-3 bg-green-500/10 border border-green-500/30 rounded">
                <p className="text-sm text-green-400">
                  {t('install.info.gpuSupport')}
                </p>
                <p className="text-xs text-ark-gray mt-1">
                  {t('install.info.includedPackages')}
                </p>
              </div>

              {/* 버튼 */}
              <div className="flex gap-3 pt-2">
                <button
                  onClick={onClose}
                  className="flex-1 ark-btn ark-btn-secondary"
                >
                  {t('common.cancel')}
                </button>
                <button
                  onClick={handleStartInstall}
                  className="flex-1 ark-btn ark-btn-primary"
                  disabled={installInfo?.is_installed}
                >
                  {installInfo?.is_installed ? t('install.status.alreadyInstalled') : t('install.button.start')}
                </button>
              </div>

              {/* 재설치 옵션 */}
              {installInfo?.is_installed && (
                <button
                  onClick={handleCleanup}
                  className="w-full text-xs text-red-400 hover:text-red-300"
                >
                  {t('install.button.reinstall')}
                </button>
              )}
            </div>
          ) : (
            // 진행 상황 표시
            <div className="space-y-4">
              {/* 진행률 바 */}
              <div className="relative h-3 bg-ark-panel rounded-full overflow-hidden">
                <div
                  className="absolute h-full bg-gradient-to-r from-ark-orange to-yellow-500 transition-all duration-300"
                  style={{ width: `${(progress?.progress || 0) * 100}%` }}
                />
              </div>

              {/* 진행률 텍스트 */}
              <div className="text-center">
                <p className="text-lg font-bold text-ark-white">
                  {Math.round((progress?.progress || 0) * 100)}%
                </p>
                <p className="text-sm text-ark-gray">
                  {progress?.message || '준비 중...'}
                </p>
              </div>

              {/* 단계 표시 */}
              <div className={`grid gap-1 ${hasPytorchUpgrade ? 'grid-cols-5' : 'grid-cols-4'}`}>
                {STAGES.map((stage, i) => (
                  <div key={stage.id} className="text-center">
                    <div
                      className={`h-1.5 rounded-full mb-1 transition-colors ${
                        currentStageIndex >= i
                          ? progress?.stage === 'error' && currentStageIndex === i
                            ? 'bg-red-500'
                            : 'bg-ark-orange'
                          : 'bg-ark-panel'
                      }`}
                    />
                    <p className={`text-[10px] ${
                      currentStageIndex === i ? 'text-ark-white' : 'text-ark-gray'
                    }`}>
                      {stage.label.split(' ')[0]}
                    </p>
                  </div>
                ))}
              </div>

              {/* 에러 표시 */}
              {error && (
                <div className="p-3 bg-red-500/20 border border-red-500/50 rounded">
                  <p className="text-sm text-red-400">{error}</p>
                </div>
              )}

              {/* 버튼 */}
              {isInstalling ? (
                <button
                  onClick={handleCancelInstall}
                  className="w-full ark-btn ark-btn-secondary"
                >
                  {t('install.button.cancel')}
                </button>
              ) : progress?.stage === 'complete' ? (
                <button
                  onClick={onClose}
                  className="w-full ark-btn ark-btn-primary"
                >
                  {t('common.complete')}
                </button>
              ) : progress?.stage === 'error' ? (
                <div className="flex gap-3">
                  <button
                    onClick={handleCleanup}
                    className="flex-1 ark-btn ark-btn-secondary"
                  >
                    {t('install.button.cleanup')}
                  </button>
                  <button
                    onClick={() => {
                      setProgress(null)
                      setError(null)
                    }}
                    className="flex-1 ark-btn ark-btn-primary"
                  >
                    {t('common.retry')}
                  </button>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
