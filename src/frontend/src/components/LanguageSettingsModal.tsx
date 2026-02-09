import { useTranslation } from 'react-i18next'
import { useAppStore } from '../stores/appStore'

interface Props {
  isOpen: boolean
  onClose: () => void
}

export default function LanguageSettingsModal({ isOpen, onClose }: Props) {
  const { t } = useTranslation()
  const {
    displayLanguage,
    voiceLanguage,
    availableDisplayLanguages,
    availableVoiceLanguages,
    setDisplayLanguage,
    setVoiceLanguage,
  } = useAppStore()

  if (!isOpen) return null

  const currentDisplayLabel = availableDisplayLanguages.find(
    l => l.locale === displayLanguage
  )?.label ?? displayLanguage

  const currentVoiceLabel = availableVoiceLanguages.find(
    l => l.short === voiceLanguage
  )?.label ?? voiceLanguage

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-ark-dark border border-ark-border rounded-lg shadow-2xl w-[420px] max-h-[90vh] overflow-y-auto">
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-ark-border">
          <h2 className="text-lg font-bold text-ark-white flex items-center gap-2">
            <svg viewBox="0 0 24 24" className="w-5 h-5 text-ark-orange" fill="currentColor">
              <path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zm6.93 6h-2.95c-.32-1.25-.78-2.45-1.38-3.56 1.84.63 3.37 1.91 4.33 3.56zM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82c.43-1.43 1.08-2.76 1.91-3.96zM4.26 14C4.1 13.36 4 12.69 4 12s.1-1.36.26-2h3.38c-.08.66-.14 1.32-.14 2 0 .68.06 1.34.14 2H4.26zm.82 2h2.95c.32 1.25.78 2.45 1.38 3.56-1.84-.63-3.37-1.9-4.33-3.56zm2.95-8H5.08c.96-1.66 2.49-2.93 4.33-3.56C8.81 5.55 8.35 6.75 8.03 8zM12 19.96c-.83-1.2-1.48-2.53-1.91-3.96h3.82c-.43 1.43-1.08 2.76-1.91 3.96zM14.34 14H9.66c-.09-.66-.16-1.32-.16-2 0-.68.07-1.35.16-2h4.68c.09.65.16 1.32.16 2 0 .68-.07 1.34-.16 2zm.25 5.56c.6-1.11 1.06-2.31 1.38-3.56h2.95c-.96 1.65-2.49 2.93-4.33 3.56zM16.36 14c.08-.66.14-1.32.14-2 0-.68-.06-1.34-.14-2h3.38c.16.64.26 1.31.26 2s-.1 1.36-.26 2h-3.38z"/>
            </svg>
            {t('languageSettings.title')}
          </h2>
          <button
            onClick={onClose}
            className="text-ark-gray hover:text-ark-white transition-colors"
          >
            <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>

        <div className="p-5 space-y-6">
          {/* 표시 언어 섹션 */}
          <div>
            <h3 className="text-sm font-semibold text-ark-white mb-1">
              {t('languageSettings.displayLanguage')}
            </h3>
            <p className="text-xs text-ark-gray mb-3">
              {t('languageSettings.displayDescription')}
            </p>
            <div className="grid grid-cols-3 gap-2">
              {availableDisplayLanguages.map((lang) => (
                <button
                  key={lang.locale}
                  onClick={() => lang.available && lang.locale && setDisplayLanguage(lang.locale)}
                  disabled={!lang.available}
                  className={`px-3 py-2.5 rounded-md text-sm font-medium transition-all border ${
                    lang.locale === displayLanguage
                      ? 'bg-ark-orange/20 text-ark-orange border-ark-orange'
                      : lang.available
                        ? 'bg-ark-panel text-ark-white border-ark-border hover:border-ark-cyan/50'
                        : 'bg-ark-panel/50 text-ark-gray/50 border-ark-border/50 cursor-not-allowed'
                  }`}
                >
                  <div>{lang.label}</div>
                  {!lang.available && (
                    <div className="text-[10px] mt-0.5 opacity-70">{t('languageSettings.notAvailable')}</div>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* 구분선 */}
          <div className="border-t border-ark-border" />

          {/* 음성 언어 섹션 */}
          <div>
            <h3 className="text-sm font-semibold text-ark-white mb-1">
              {t('languageSettings.voiceLanguage')}
            </h3>
            <p className="text-xs text-ark-gray mb-3">
              {t('languageSettings.voiceDescription')}
            </p>
            <div className="grid grid-cols-3 gap-2">
              {availableVoiceLanguages.map((lang) => (
                <button
                  key={lang.short}
                  onClick={() => lang.available && setVoiceLanguage(lang.short)}
                  disabled={!lang.available}
                  className={`px-3 py-2.5 rounded-md text-sm font-medium transition-all border ${
                    lang.short === voiceLanguage
                      ? 'bg-ark-cyan/20 text-ark-cyan border-ark-cyan'
                      : lang.available
                        ? 'bg-ark-panel text-ark-white border-ark-border hover:border-ark-cyan/50'
                        : 'bg-ark-panel/50 text-ark-gray/50 border-ark-border/50 cursor-not-allowed'
                  }`}
                >
                  <div>{lang.label}</div>
                  {!lang.available && (
                    <div className="text-[10px] mt-0.5 opacity-70">{t('languageSettings.notAvailable')}</div>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* 현재 조합 미리보기 */}
          <div className="bg-ark-panel/50 rounded-md px-4 py-3 text-center text-sm text-ark-gray">
            {t('languageSettings.currentCombo', {
              display: currentDisplayLabel,
              voice: currentVoiceLabel,
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
