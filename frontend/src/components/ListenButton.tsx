import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { SpeakerHigh, Stop } from "@phosphor-icons/react";
import { speak } from "../lib/api";

/** Reads a short summary aloud with Amazon Polly (English and Hindi only). */
export default function ListenButton({ text, lang }: { text: string; lang: string }) {
  const { t } = useTranslation();
  const audio = useRef<HTMLAudioElement | null>(null);
  const cache = useRef<{ key: string; src: string } | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "playing" | "error">("idle");

  useEffect(() => () => audio.current?.pause(), []);
  // A language switch changes the text, so stop whatever is playing.
  useEffect(() => {
    audio.current?.pause();
    setState("idle");
  }, [text, lang]);

  async function toggle() {
    if (state === "playing" || state === "loading") {
      audio.current?.pause();
      setState("idle");
      return;
    }
    setState("loading");
    try {
      const key = `${lang}:${text}`;
      if (cache.current?.key !== key) {
        const res = await speak(text.slice(0, 1500), lang);
        cache.current = { key, src: `data:${res.contentType || "audio/mpeg"};base64,${res.audio}` };
      }
      const a = new Audio(cache.current.src);
      audio.current?.pause();
      audio.current = a;
      a.onended = () => setState("idle");
      await a.play();
      setState("playing");
    } catch {
      setState("error");
    }
  }

  const busy = state === "playing" || state === "loading";
  return (
    <span className="inline-flex flex-col">
      <button type="button" className="btn btn-line" onClick={toggle} aria-pressed={busy}>
        {busy ? <Stop size={20} weight="bold" aria-hidden /> : <SpeakerHigh size={20} weight="bold" aria-hidden />}
        {state === "loading" ? "…" : busy ? t("plan.stop") : t("plan.listen")}
      </button>
      {state === "error" ? (
        <span role="alert" className="mt-1 text-[14px] text-alert">
          {t("plan.listenError")}
        </span>
      ) : null}
    </span>
  );
}
