import { useRef, useState, type ChangeEvent } from "react";
import { Link, useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { ArrowRight, Camera, FilePdf, LockSimple, PencilSimpleLine } from "@phosphor-icons/react";
import SunBlock from "../components/SunBlock";
import UsageChart from "../components/UsageChart";
import ErrorPanel from "../components/ErrorPanel";
import { checkFile } from "../lib/api";
import { setFlow, setPendingFile } from "../lib/store";

// Real output for the Delhi BRPL sample bill (plan vViU9XBJBJnN5aYL).
const EXAMPLE_USED = [220, 205, 186, 251, 398, 455, 412, 389, 342, 279, 220, 205];
const EXAMPLE_SOLAR = [349, 336, 378, 360, 342, 290, 240, 249, 285, 357, 343, 353];

export default function Home() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const camRef = useRef<HTMLInputElement>(null);
  const pdfRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<unknown>(null);

  function onPick(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    const bad = checkFile(f);
    if (bad) {
      setError(bad);
      return;
    }
    setError(null);
    setPendingFile(f);
    setFlow({ extract: null, consumerNumber: null });
    navigate("/reading");
  }

  return (
    <div className="wrap">
      <section className="grid grid-cols-1 rule-b md:grid-cols-12">
        <div className="py-9 md:col-span-7 md:border-r-2 md:border-ink md:py-14 md:pr-10">
          <h1 className="display text-[clamp(46px,7.4vw,108px)] font-semibold leading-[0.92] tracking-[-0.025em] [&>span]:block">
            <span>{t("home.title1")}</span>
            <span>{t("home.title2")}</span>
            <span>{t("home.title3")}</span>
          </h1>
          <p className="mt-6 max-w-[34em] text-[18px] text-ink-2 md:mt-10">{t("home.lead")}</p>

          <div className="mt-8 flex max-w-[560px] flex-col border-2 border-ink sm:flex-row md:mt-10">
            <button
              type="button"
              onClick={() => camRef.current?.click()}
              className="group flex min-h-16 flex-1 cursor-pointer items-center justify-between gap-3 bg-ink px-5 py-4 text-paper hover:bg-[#34302a]"
            >
              <span className="flex items-center gap-3">
                <Camera size={26} weight="bold" aria-hidden />
                <span className="display text-[21px] font-semibold">{t("home.snap")}</span>
              </span>
              <ArrowRight size={24} weight="bold" aria-hidden className="transition-transform duration-200 group-hover:translate-x-1" />
            </button>
            <button
              type="button"
              onClick={() => pdfRef.current?.click()}
              className="flex min-h-14 cursor-pointer items-center gap-2 border-t-2 border-ink px-5 font-medium hover:bg-paper-2 sm:border-t-0 sm:border-l-2"
            >
              <FilePdf size={22} weight="bold" aria-hidden />
              {t("home.upload")}
            </button>
          </div>
          <input ref={camRef} type="file" accept="image/*" capture="environment" className="sr-only" tabIndex={-1} aria-hidden onChange={onPick} />
          <input ref={pdfRef} type="file" accept="application/pdf,image/jpeg,image/png,image/webp" className="sr-only" tabIndex={-1} aria-hidden onChange={onPick} data-testid="file-input" />

          <p className="mt-3.5 flex items-start gap-2 text-[15px] text-ink-2">
            <LockSimple size={18} weight="bold" aria-hidden className="mt-0.5 shrink-0" />
            {t("home.privacy")}
          </p>
          <Link to="/manual" className="mt-6 inline-flex min-h-12 items-center gap-2 font-semibold underline decoration-2 underline-offset-4 hover:decoration-sun">
            <PencilSimpleLine size={20} weight="bold" aria-hidden />
            {t("home.manual")}
          </Link>
          {error ? (
            <div className="mt-6 max-w-[560px]">
              <ErrorPanel error={error} />
            </div>
          ) : null}
        </div>
        <div className="-mx-4 md:col-span-5 md:mx-0">
          <SunBlock tag={t("home.exampleTag")} value="5.7" unit={t("home.years")}>
            {t("home.exampleText")}
          </SunBlock>
        </div>
      </section>

      <section className="grid grid-cols-2 rule-b md:grid-cols-4" aria-label={t("home.exampleTag")}>
        {[
          [t("home.stripCost"), "₹1,62,500"],
          [t("home.stripSubsidy"), "− ₹69,000"],
          [t("home.stripPay"), "₹93,500"],
          [t("home.stripCo2"), "2.76 t"],
        ].map(([k, v], i) => (
          <div
            key={k}
            className={`py-5 pr-3 md:py-7 md:pr-6 ${i % 2 === 1 ? "border-l-2 border-ink pl-3.5" : "pl-0"} ${i >= 2 ? "border-t-2 border-ink md:border-t-0" : ""} ${i > 0 ? "md:border-l-2 md:border-ink md:pl-6" : ""}`}
          >
            <small className="block text-[15px] font-medium text-ink-2">{k}</small>
            <b className={`display tabular mt-2 block whitespace-nowrap text-[clamp(22px,7vw,32px)] font-semibold leading-tight md:text-[44px] ${i === 1 ? "text-sun-ink" : ""}`}>{v}</b>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-1 rule-b md:grid-cols-12">
        <div className="border-b-2 border-ink py-9 md:col-span-5 md:border-r-2 md:border-b-0 md:py-12 md:pr-10">
          <h2 className="display text-[clamp(30px,4vw,40px)] font-semibold leading-none">{t("home.howTitle")}</h2>
          <ol className="mt-7">
            {[1, 2, 3].map((n) => (
              <li key={n} className="grid grid-cols-[56px_1fr] border-t border-rule py-4">
                <b className="display text-[30px] font-semibold">0{n}</b>
                <div>
                  <strong className="block font-bold">{t(`home.how${n}t`)}</strong>
                  <span className="text-[16px] text-ink-2">{t(`home.how${n}`)}</span>
                </div>
              </li>
            ))}
          </ol>
        </div>
        <div className="py-9 md:col-span-7 md:py-12 md:pl-10">
          <h2 className="display text-[clamp(30px,4vw,40px)] font-semibold leading-none">{t("plan.chartTitle")}</h2>
          <p className="mt-2 text-[15px] text-ink-2">{t("home.exampleTag")}</p>
          <div className="mt-6">
            <UsageChart used={EXAMPLE_USED} solar={EXAMPLE_SOLAR} />
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-y-8 py-10 md:grid-cols-12 md:py-14">
        <div className="md:col-span-5 md:pr-10">
          <h2 className="display text-[clamp(28px,3.6vw,36px)] font-semibold leading-none">{t("home.whyTitle")}</h2>
          <p className="mt-5 max-w-[30em] text-[18px]">{t("home.why")}</p>
        </div>
        <div className="md:col-span-7 md:pl-10">
          <h2 className="display text-[clamp(28px,3.6vw,36px)] font-semibold leading-none">{t("home.faqTitle")}</h2>
          <dl className="mt-5">
            {[1, 2, 3].map((n) => (
              <div key={n} className="border-t-2 border-ink py-4">
                <dt className="font-bold">{t(`home.faq${n}q`)}</dt>
                <dd className="mt-1 text-ink-2">{t(`home.faq${n}a`)}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>
    </div>
  );
}
