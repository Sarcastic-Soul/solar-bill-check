import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, Copy } from "@phosphor-icons/react";

export async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Older browsers / insecure context: fall back to a hidden textarea.
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  }
}

export default function CopyButton({ text, label, className = "btn btn-line" }: { text: string; label?: string; className?: string }) {
  const { t } = useTranslation();
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (!done) return;
    const id = setTimeout(() => setDone(false), 2000);
    return () => clearTimeout(id);
  }, [done]);
  return (
    <button type="button" className={className} onClick={async () => setDone(await copyText(text))}>
      {done ? <Check size={20} weight="bold" aria-hidden /> : <Copy size={20} weight="bold" aria-hidden />}
      <span aria-live="polite">{done ? t("plan.copied") : (label ?? t("plan.copy"))}</span>
    </button>
  );
}
