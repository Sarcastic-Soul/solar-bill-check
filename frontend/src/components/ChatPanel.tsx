import { useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { m, LazyMotion, domAnimation, useReducedMotion } from "motion/react";
import { PaperPlaneRight, X } from "@phosphor-icons/react";
import { ApiError, sendChat } from "../lib/api";

interface Msg {
  role: "user" | "bot";
  text: string;
}

const SESSION_KEY = "sbc.chat.v1";

/** Replies use light markdown: **bold** and "- " bullets. Render just those, as text nodes. */
function Reply({ text }: { text: string }) {
  return (
    <>
      {text.split("\n").map((line, i) => {
        const bullet = /^\s*[-*•]\s+/.test(line);
        const body = line.replace(/^\s*[-*•]\s+/, "").replace(/^#+\s*/, "");
        const parts = body.split(/\*\*(.+?)\*\*/g).map((p, j) => (j % 2 ? <strong key={j}>{p}</strong> : p));
        if (!body.trim()) return <span key={i} className="block h-2" />;
        return (
          <span key={i} className={`block ${bullet ? "relative pl-4" : ""}`}>
            {bullet ? <span aria-hidden className="absolute left-0 top-[0.62em] size-1.5 bg-ink" /> : null}
            {parts}
          </span>
        );
      })}
    </>
  );
}

function loadSession(planId: string): { sessionId: string | null; msgs: Msg[] } {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    const d = raw ? JSON.parse(raw) : null;
    if (d?.planId === planId) return { sessionId: d.sessionId, msgs: d.msgs };
  } catch {
    // ignore
  }
  return { sessionId: null, msgs: [] };
}

export default function ChatPanel({ planId, onClose }: { planId: string; onClose: () => void }) {
  const { t, i18n } = useTranslation();
  const reduce = useReducedMotion();
  const init = useRef(loadSession(planId)).current;
  const [sessionId, setSessionId] = useState<string | null>(init.sessionId);
  const [msgs, setMsgs] = useState<Msg[]>(init.msgs);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [soon, setSoon] = useState(false);
  const [error, setError] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeRef.current();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: reduce ? "auto" : "smooth" });
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({ planId, sessionId, msgs }));
    } catch {
      // ignore
    }
  }, [msgs, planId, sessionId, reduce]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    setError(false);
    setMsgs((ms) => [...ms, { role: "user", text: q }]);
    setBusy(true);
    try {
      const res = await sendChat({ sessionId, planId, message: q, lang: i18n.resolvedLanguage ?? "en" });
      setSessionId(res.sessionId);
      setMsgs((ms) => [...ms, { role: "bot", text: res.reply }]);
    } catch (e) {
      // No chat endpoint deployed yet: say so instead of showing an error.
      if (e instanceof ApiError && (e.status === 404 || e.status === 403 || e.code === "NOT_FOUND")) setSoon(true);
      else setError(true);
    } finally {
      setBusy(false);
    }
  }

  const suggest = t("chat.suggest", { returnObjects: true }) as string[];

  return (
    <LazyMotion features={domAnimation} strict>
      <div className="fixed inset-0 z-40">
        <m.div
          className="absolute inset-0 bg-ink/40"
          onClick={onClose}
          initial={reduce ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.2 }}
          aria-hidden
        />
        <m.aside
          role="dialog"
          aria-modal="true"
          aria-labelledby="chat-title"
          className="absolute inset-y-0 right-0 flex w-full max-w-[460px] flex-col border-l-2 border-ink bg-paper"
          initial={reduce ? false : { x: "100%" }}
          animate={{ x: 0 }}
          transition={{ type: "spring", bounce: 0, duration: 0.35 }}
        >
          <header className="flex items-center justify-between border-b-2 border-ink bg-sun px-5 py-3">
            <h2 id="chat-title" className="display text-[22px] font-semibold">
              {t("chat.title")}
            </h2>
            <button type="button" onClick={onClose} className="grid size-12 cursor-pointer place-items-center hover:bg-[#ffb912]" aria-label={t("chat.close")}>
              <X size={24} weight="bold" aria-hidden />
            </button>
          </header>
          <div ref={listRef} className="flex-1 space-y-4 overflow-y-auto p-5" aria-live="polite">
            {msgs.length === 0 && !soon ? <p className="text-ink-2">{t("chat.intro")}</p> : null}
            {msgs.map((msg, i) => (
              <div
                key={i}
                className={`max-w-[88%] border-2 border-ink px-4 py-3 ${msg.role === "user" ? "ml-auto bg-ink text-paper" : "bg-card"}`}
              >
                {msg.role === "bot" ? <Reply text={msg.text} /> : msg.text}
              </div>
            ))}
            {busy ? <p className="text-ink-2">{t("chat.thinking")}…</p> : null}
            {soon ? <p className="border-2 border-ink bg-sun-soft p-4 font-medium">{t("chat.soon")}</p> : null}
            {error ? (
              <p role="alert" className="font-semibold text-alert">
                {t("chat.error")}
              </p>
            ) : null}
          </div>
          {msgs.length === 0 && !soon ? (
            <div className="flex flex-wrap gap-2 px-5 pb-3">
              {suggest.map((s) => (
                <button key={s} type="button" onClick={() => send(s)} className="min-h-11 cursor-pointer border-2 border-ink px-3 text-[15px] font-medium hover:bg-paper-2">
                  {s}
                </button>
              ))}
            </div>
          ) : null}
          <form
            className="flex border-t-2 border-ink"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              void send(input);
            }}
          >
            <label htmlFor="chat-input" className="sr-only">
              {t("chat.placeholder")}
            </label>
            <textarea
              id="chat-input"
              ref={inputRef}
              rows={2}
              value={input}
              disabled={soon}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send(input);
                }
              }}
              placeholder={t("chat.placeholder")}
              className="min-h-16 flex-1 resize-none bg-card px-4 py-3 outline-none focus:shadow-[inset_0_0_0_3px_var(--color-sun)]"
            />
            <button type="submit" disabled={busy || soon || !input.trim()} className="btn btn-ink !min-h-16 rounded-none !border-0 !border-l-2" aria-label={t("chat.send")}>
              <PaperPlaneRight size={22} weight="bold" aria-hidden />
            </button>
          </form>
        </m.aside>
      </div>
    </LazyMotion>
  );
}
