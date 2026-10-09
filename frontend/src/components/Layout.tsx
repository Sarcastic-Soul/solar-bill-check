import { Suspense } from "react";
import { Link, Outlet, ScrollRestoration } from "react-router";
import { useTranslation } from "react-i18next";
import { UI_LANGS } from "../config";
import { setFlow } from "../lib/store";
import Spinner from "./Spinner";

const LANG_LABEL: Record<string, string> = { en: "English", hi: "हिन्दी" };

export function LangSwitch({ className = "" }: { className?: string }) {
  const { t, i18n } = useTranslation();
  return (
    <nav aria-label={t("app.language")} className={`flex items-stretch ${className}`}>
      {UI_LANGS.map((l) => {
        const on = i18n.resolvedLanguage === l;
        return (
          <button
            key={l}
            type="button"
            lang={l}
            aria-pressed={on}
            onClick={() => {
              setFlow({ langChosen: true });
              void i18n.changeLanguage(l);
            }}
            className={`min-h-11 px-3 font-medium ${on ? "border-b-2 border-ink" : "border-b-2 border-transparent text-ink-2 hover:text-ink"}`}
          >
            {LANG_LABEL[l]}
          </button>
        );
      })}
    </nav>
  );
}

export default function Layout() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-sun focus:px-4 focus:py-2">
        {t("app.skip")}
      </a>
      <header className="rule-b">
        <div className="wrap flex h-[68px] items-center justify-between gap-4">
          <Link to="/" className="display flex items-center gap-2.5 text-[21px] font-semibold">
            <span aria-hidden className="size-[22px] rounded-full border-2 border-ink bg-sun" />
            {t("app.name")}
          </Link>
          <LangSwitch />
        </div>
      </header>
      <main id="main" className="flex-1">
        <Suspense fallback={<Spinner />}>
          <Outlet />
        </Suspense>
      </main>
      <footer className="wrap">
        <div className="rule-t flex flex-wrap justify-between gap-x-6 gap-y-2 py-7 text-[14px] text-ink-2">
          <span>{t("app.footerSources")}</span>
          <span>{t("app.notGov")}</span>
          <span>{t("app.footerAws")}</span>
        </div>
      </footer>
      <ScrollRestoration />
    </div>
  );
}
