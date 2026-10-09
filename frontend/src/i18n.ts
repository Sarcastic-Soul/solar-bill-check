import i18n from "i18next";
import resourcesToBackend from "i18next-resources-to-backend";
import { initReactI18next } from "react-i18next";
import { UI_LANGS } from "./config";

const STORAGE_KEY = "sbc.lang";

function initialLang(): string {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && (UI_LANGS as readonly string[]).includes(saved)) return saved;
  } catch {
    // ignore
  }
  return navigator.language?.toLowerCase().startsWith("hi") ? "hi" : "en";
}

i18n
  .use(initReactI18next)
  .use(resourcesToBackend((lng: string) => import(`./locales/${lng}.json`)))
  .init({
    lng: initialLang(),
    fallbackLng: "en",
    supportedLngs: [...UI_LANGS],
    interpolation: { escapeValue: false },
    react: { useSuspense: true },
  });

i18n.on("languageChanged", (lng) => {
  document.documentElement.lang = lng;
  try {
    localStorage.setItem(STORAGE_KEY, lng);
  } catch {
    // ignore
  }
});
document.documentElement.lang = i18n.language;

export default i18n;
