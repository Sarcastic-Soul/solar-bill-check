import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { Check, CircleNotch } from "@phosphor-icons/react";
import ErrorPanel from "../components/ErrorPanel";
import { ApiError, extractBill, uploadBill } from "../lib/api";
import { getPendingFile, setFlow, setPendingFile } from "../lib/store";
import type { ExtractResult } from "../lib/types";

type Stage = 0 | 1 | 2;

// One run per file, so StrictMode's double effect doesn't upload twice.
let running: { file: File; promise: Promise<ExtractResult> } | null = null;

function run(file: File, onStage: (s: Stage) => void) {
  if (running?.file === file) return running.promise;
  const promise = (async () => {
    onStage(0);
    const key = await uploadBill(file);
    onStage(1);
    const res = await extractBill(key);
    onStage(2);
    return res;
  })();
  running = { file, promise };
  promise.catch(() => {
    if (running?.promise === promise) running = null;
  });
  return promise;
}

export default function Reading() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const file = getPendingFile();
  const [stage, setStage] = useState<Stage>(0);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!file) return;
    let live = true;
    setError(null);
    run(file, (s) => live && setStage(s))
      .then((res) => {
        if (!live) return;
        if (res.fields.is_electricity_bill === false) {
          running = null;
          setError(new ApiError("NOT_ELECTRICITY_BILL", "not a bill"));
          return;
        }
        setFlow({ extract: res, consumerNumber: res.fields.consumer_number ?? null });
        setPendingFile(null);
        running = null;
        // Hold the last tick for a moment so the "checking" step is seen.
        setTimeout(() => navigate("/check", { replace: true }), 350);
      })
      .catch((e: unknown) => live && setError(e));
    return () => {
      live = false;
    };
  }, [file, attempt, navigate]);

  if (!file) return <Navigate to="/" replace />;

  const steps = [t("reading.step1"), t("reading.step2"), t("reading.step3")];

  return (
    <div className="wrap max-w-[760px] py-12 md:py-20">
      <h1 className="display text-[clamp(36px,6vw,64px)] font-semibold leading-[0.95]">{t("reading.title")}</h1>
      {!error ? <p className="mt-3 text-ink-2">{t("reading.note")}</p> : null}

      {error ? (
        <div className="mt-10">
          <ErrorPanel error={error}>
            {!(error instanceof ApiError && error.code === "NOT_ELECTRICITY_BILL") ? (
              <button type="button" className="btn btn-ink" onClick={() => setAttempt((a) => a + 1)}>
                {t("errors.retry")}
              </button>
            ) : null}
            <Link to="/" className={`btn ${error instanceof ApiError && error.code === "NOT_ELECTRICITY_BILL" ? "btn-ink" : "btn-line"}`}>
              {t("errors.newPhoto")}
            </Link>
            <Link to="/manual" className="btn btn-line">
              {t("errors.manual")}
            </Link>
          </ErrorPanel>
        </div>
      ) : (
        <ol className="mt-10 border-t-2 border-ink" aria-live="polite">
          {steps.map((label, i) => {
            const done = i < stage || (i === 2 && stage === 2);
            const now = i === stage && !done;
            return (
              <li
                key={label}
                className={`flex min-h-[72px] items-center gap-4 border-b-2 border-ink px-1 text-[19px] ${now ? "font-semibold" : ""} ${i > stage ? "text-ink-2" : ""}`}
                aria-current={now ? "step" : undefined}
              >
                <span
                  aria-hidden
                  className={`grid size-10 shrink-0 place-items-center border-2 border-ink ${done ? "bg-ink text-paper" : now ? "bg-sun" : ""}`}
                >
                  {done ? <Check size={22} weight="bold" /> : now ? <CircleNotch size={22} weight="bold" className="animate-spin" /> : <span className="display text-[16px]">{i + 1}</span>}
                </span>
                {label}
              </li>
            );
          })}
        </ol>
      )}
      {!error ? (
        <Link to="/" className="mt-8 inline-flex min-h-12 items-center font-medium underline decoration-2 underline-offset-4">
          {t("reading.cancel")}
        </Link>
      ) : null}
    </div>
  );
}
