import type { ReactNode } from "react";
import { Link, useRouteError } from "react-router";
import { useTranslation } from "react-i18next";
import { WarningDiamond } from "@phosphor-icons/react";
import { ApiError } from "../lib/api";

/** Plain-language message for an error code, falling back to the server's message, then a generic one. */
export function useErrorText() {
  const { t, i18n } = useTranslation();
  return (err: unknown) => {
    if (err instanceof ApiError) {
      const key = `errors.${err.code}`;
      if (i18n.exists(key)) return t(key);
      if (err.message && i18n.resolvedLanguage === "en" && err.message.length > 12) return err.message;
    }
    return t("errors.generic");
  };
}

export default function ErrorPanel({ error, children }: { error: unknown; children?: ReactNode }) {
  const { t } = useTranslation();
  const text = useErrorText()(error);
  return (
    <div role="alert" className="border-2 border-ink bg-card">
      <div className="flex items-start gap-4 border-b-2 border-ink bg-sun p-5">
        <WarningDiamond size={30} weight="bold" aria-hidden className="mt-0.5 shrink-0" />
        <div>
          <h2 className="display text-[26px] font-semibold leading-tight">{t("errors.title")}</h2>
          <p className="mt-1 text-[17px]">{text}</p>
        </div>
      </div>
      {children ? <div className="flex flex-wrap gap-3 p-5">{children}</div> : null}
    </div>
  );
}

export function RouteError() {
  const err = useRouteError();
  const { t } = useTranslation();
  return (
    <div className="wrap py-16">
      <ErrorPanel error={err}>
        <Link to="/" className="btn btn-ink">
          {t("errors.home")}
        </Link>
      </ErrorPanel>
    </div>
  );
}
