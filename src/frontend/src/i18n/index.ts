import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import ko from './locales/ko.json'
import ja from './locales/ja.json'
import en from './locales/en.json'

i18n
  .use(initReactI18next)
  .init({
    resources: {
      ko: { translation: ko },
      ja: { translation: ja },
      en: { translation: en },
    },
    lng: 'ko',
    fallbackLng: 'ko',
    interpolation: {
      escapeValue: false,
    },
  })

export const changeLanguage = (lang: string) => {
  i18n.changeLanguage(lang)
}

export default i18n
