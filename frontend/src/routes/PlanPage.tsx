import { lazy, Suspense, useRef, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ArrowCounterClockwise, ChatCircleText, CheckCircle, ShareNetwork, WarningCircle, XCircle } from "@phosphor-icons/react";
import ErrorPanel from "../components/ErrorPanel";
import Spinner from "../components/Spinner";
import SunBlock from "../components/SunBlock";
import UsageChart from "../components/UsageChart";
import CopyButton, { copyText } from "../components/CopyButton";
import ListenButton from "../components/ListenButton";
import { SPEAK_LANGS } from "../config";
import { getPlan } from "../lib/api";
import { inr, inrShort, num, tonnes } from "../lib/format";
import { useFlow } from "../lib/store";
import type { Plan, PlanResponse, ReadinessItem, SystemOption } from "../lib/types";

const ChatPanel = lazy(() => import("../components/ChatPanel"));

export default function PlanPage() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["plan", id], queryFn: () => getPlan(id), retry: (n, e) => n < 1 && (e as { status?: number }).status !== 404 });

  if (q.isPending) return <Spinner label={t("plan.loading")} />;
  if (q.error)
    return (
      <div className="wrap max-w-[760px] py-16">
        <ErrorPanel error={q.error}>
          {(q.error as { status?: number }).status !== 404 ? (
            <button type="button" className="btn btn-ink" onClick={() => q.refetch()}>
              {t("errors.retry")}
            </button>
          ) : null}
          <Link to="/" className="btn btn-line">
            {t("errors.home")}
          </Link>
        </ErrorPanel>
      </div>
    );
  return <PlanView data={q.data} />;
}

function PlanView({ data }: { data: PlanResponse }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.resolvedLanguage ?? "en";
  const flow = useFlow();
  const [chatOpen, setChatOpen] = useState(false);
  const chatBtn = useRef<HTMLButtonElement>(null);
  const [shared, setShared] = useState(false);
  const plan = data.plan;
  const r = plan.recommended;
  const alt = plan.alternative;
  const verdict = plan.verdict.code;
  const payback = r.payback_years;
  const stateName = plan.location?.state ?? plan.state ?? plan.discom.state;

  const listenText = t("plan.listenText", {
    verdict: t(`plan.verdict.${verdict}`),
    kw: num(r.kw),
    cost: inr(r.gross_cost),
    subsidy: inr(r.subsidy.total),
    pay: inr(r.net_cost),
    saving: inr(r.monthly_saving_avg),
    payback: payback == null ? "–" : num(payback),
  });

  async function share() {
    const url = window.location.href;
    if (navigator.share) {
      try {
        await navigator.share({ title: t("app.name"), url });
        return;
      } catch {
        // cancelled: fall through to copy
      }
    }
    if (await copyText(url)) {
      setShared(true);
      setTimeout(() => setShared(false), 2000);
    }
  }

  return (
    <div className="wrap pb-20">
      {/* Verdict + payback */}
      <section className="grid grid-cols-1 rule-b md:grid-cols-12">
        <div className="py-8 md:col-span-7 md:border-r-2 md:border-ink md:py-12 md:pr-10">
          <p className="eyebrow text-ink-2">
            {[plan.discom.name ?? plan.discom.code, plan.location?.district, stateName].filter(Boolean).join(" · ")}
          </p>
          <h1 className="display mt-3 text-[clamp(46px,7vw,96px)] font-semibold leading-[0.92] tracking-[-0.025em]">
            {t(`plan.verdict.${verdict}`)}
            {verdict === "not_now" ? "." : ""}
          </h1>
          <ul className="mt-6 max-w-[36em] space-y-2 text-[18px]">
            {plan.verdict.reasons
              .filter((c) => i18n.exists(`reasons.${c}`))
              .map((c) => (
                <li key={c} className="flex gap-3">
                  <span aria-hidden className="mt-[0.6em] size-2 shrink-0 bg-ink" />
                  {t(`reasons.${c}`)}
                </li>
              ))}
          </ul>
          <div className="mt-8 flex flex-wrap gap-3">
            {(SPEAK_LANGS as readonly string[]).includes(lang) ? <ListenButton text={listenText} lang={lang} /> : null}
            <button type="button" className="btn btn-line" onClick={share}>
              <ShareNetwork size={20} weight="bold" aria-hidden />
              <span aria-live="polite">{shared ? t("plan.shareCopied") : t("plan.share")}</span>
            </button>
            <Link to="/" className="btn btn-line">
              <ArrowCounterClockwise size={20} weight="bold" aria-hidden />
              {t("plan.newBill")}
            </Link>
          </div>
          <AccuracyBadge plan={plan} />
        </div>
        <div className="-mx-4 md:col-span-5 md:mx-0">
          <SunBlock tag={t("plan.paysBackIn")} value={payback == null ? "–" : num(payback)} unit={payback == null ? t("plan.noPayback") : t("plan.years")}>
            {payback != null ? t("plan.paybackLine", { kw: num(r.kw), year: inr(r.year1_savings) }) : null}
          </SunBlock>
        </div>
      </section>

      {/* Number strip */}
      <section className="grid grid-cols-2 rule-b md:grid-cols-5">
        <Cell label={t("plan.stripSize")} value={`${num(r.kw)} kW`} i={0} />
        <Cell label={t("plan.stripCost")} value={inr(r.gross_cost)} i={1} />
        <Cell label={t("plan.stripSubsidy")} value={`− ${inr(r.subsidy.total)}`} i={2} tone="sun" />
        <Cell label={t("plan.stripPay")} value={inr(r.net_cost)} i={3} />
        <Cell
          label={t("plan.stripCo2")}
          value={`${tonnes(r.co2_kg_per_year)} t`}
          note={t("plan.co2Trees", { trees: num(r.trees_equivalent, 0) })}
          i={4}
        />
      </section>
      {r.subsidy.notes.includes("STATE_TOPUP_UNCONFIRMED_EXCLUDED") && stateName ? (
        <p className="rule-b py-4 text-[16px] text-ink-2">{t("plan.stateTopup", { state: stateName })}</p>
      ) : null}

      {/* Chart + money */}
      <section className="grid grid-cols-1 rule-b md:grid-cols-12">
        <div className="border-b-2 border-ink py-9 md:col-span-7 md:border-r-2 md:border-b-0 md:py-12 md:pr-10">
          <h2 className="display text-[clamp(28px,4vw,40px)] font-semibold leading-none">{t("plan.chartTitle")}</h2>
          <div className="mt-6">
            <UsageChart used={r.monthly.map((x) => x.units)} solar={r.monthly.map((x) => x.solar_kwh)} months={r.monthly.map((x) => x.month)} />
          </div>
          <p className="help mt-4">{t("plan.chartNote")}</p>
        </div>
        <div className="py-9 md:col-span-5 md:py-12 md:pl-10">
          <h2 className="display text-[clamp(28px,4vw,40px)] font-semibold leading-none">{t("plan.moneyTitle")}</h2>
          <dl className="mt-6 border-t-2 border-ink">
            <Row label={t("plan.billNow")} value={inr(r.bill_before_year)} />
            <Row label={t("plan.billAfter")} value={inr(r.bill_after_year)} />
            <Row label={t("plan.savingMonth")} value={inr(r.monthly_saving_avg)} big />
            <Row label={t("plan.saving25")} value={inrShort(r.savings_25y, lang)} big />
            {r.export_income > 0 ? <Row label={t("plan.exportIncome")} value={inr(r.export_income)} /> : null}
          </dl>
        </div>
      </section>

      {/* Loan + alternative */}
      {r.loan || alt ? (
        <section className={`grid grid-cols-1 rule-b ${r.loan && alt ? "md:grid-cols-2" : ""}`}>
          {r.loan ? <LoanBlock option={r} border={!!alt} /> : null}
          {alt ? <AltBlock alt={alt} pad={!!r.loan} /> : null}
        </section>
      ) : null}

      {/* Readiness + sheet */}
      <section className="grid grid-cols-1 rule-b md:grid-cols-12">
        <div className="border-b-2 border-ink py-9 md:col-span-6 md:border-r-2 md:border-b-0 md:py-12 md:pr-10">
          <h2 className="display text-[clamp(28px,4vw,40px)] font-semibold leading-none">{t("plan.readyTitle")}</h2>
          <ul className="mt-6 border-t-2 border-ink">
            {plan.readiness.map((it) => (
              <ReadyRow key={it.code} item={it} />
            ))}
          </ul>
        </div>
        <div className="py-9 md:col-span-6 md:py-12 md:pl-10">
          <Sheet data={data} fullConsumer={flow.planId === data.planId ? flow.consumerNumber : null} />
        </div>
      </section>

      {/* 7 steps */}
      <section className="rule-b py-9 md:py-12">
        <h2 className="display text-[clamp(28px,4vw,40px)] font-semibold leading-none">{t("plan.stepsTitle")}</h2>
        <ol className="mt-7 grid grid-cols-1 border-t-2 border-l-2 border-ink sm:grid-cols-2 lg:grid-cols-7">
          {(t("steps", { returnObjects: true }) as { t: string; who: string; d: string }[]).map((s, i) => (
            <li key={s.t} className="border-r-2 border-b-2 border-ink p-4">
              <div className="flex items-baseline justify-between gap-2">
                <b className="display tabular text-[34px] font-semibold leading-none">{i + 1}</b>
                <span className="eyebrow text-ink-2">{s.who}</span>
              </div>
              <h3 className="mt-3 font-bold">{s.t}</h3>
              <p className="mt-1 text-[15px] text-ink-2">{s.d}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Vendor + red flags */}
      <section className="grid grid-cols-1 rule-b md:grid-cols-12">
        <div className="border-b-2 border-ink py-9 md:col-span-7 md:border-r-2 md:border-b-0 md:py-12 md:pr-10">
          <h2 className="display text-[clamp(26px,3.4vw,34px)] font-semibold leading-none">{t("plan.vendorTitle")}</h2>
          <ol className="mt-5">
            {(t("vendor", { returnObjects: true }) as string[]).map((v, i) => (
              <li key={i} className="grid grid-cols-[40px_1fr] border-t border-rule py-3">
                <b className="display tabular text-[20px]">{i + 1}</b>
                <span>{v}</span>
              </li>
            ))}
          </ol>
        </div>
        <div className="py-9 md:col-span-5 md:py-12 md:pl-10">
          <div className="border-2 border-ink">
            <h2 className="display border-b-2 border-ink bg-sun px-5 py-3 text-[26px] font-semibold">{t("plan.flagsTitle")}</h2>
            <ul className="space-y-3 p-5">
              {(t("redFlags", { returnObjects: true }) as string[]).map((v) => (
                <li key={v} className="flex gap-3">
                  <XCircle size={22} weight="bold" aria-hidden className="mt-0.5 shrink-0" />
                  {v}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* Accuracy + assumptions */}
      <section className="py-9 md:py-12">
        <h2 className="display text-[clamp(26px,3.4vw,34px)] font-semibold leading-none">{t("plan.accuracyTitle")}</h2>
        <p className="mt-4 max-w-[44em] text-[18px]">
          <b>{t(`plan.accuracy.${plan.accuracy}`)}.</b> {t(`plan.accuracyText.${plan.accuracy}`)}
        </p>
        {plan.warnings.filter((w) => i18n.exists(`warn.${w}`)).length ? (
          <ul className="mt-4 max-w-[44em] space-y-1 text-ink-2">
            {plan.warnings
              .filter((w) => i18n.exists(`warn.${w}`))
              .map((w) => (
                <li key={w}>{t(`warn.${w}`)}</li>
              ))}
          </ul>
        ) : null}
        <details className="mt-6 border-2 border-ink">
          <summary className="flex min-h-14 cursor-pointer items-center px-4 font-semibold">{t("plan.assumptions")}</summary>
          <div className="overflow-x-auto border-t-2 border-ink">
            <table className="w-full min-w-[640px] text-left text-[15px]">
              <tbody>
                {plan.assumptions.map((a) => (
                  <tr key={a.key} className="border-b border-rule align-top">
                    <th scope="row" className="w-[28%] px-4 py-2.5 font-semibold">
                      {a.key.replace(/_/g, " ")}
                    </th>
                    <td className="tabular px-4 py-2.5">
                      {String(a.value ?? "–")}
                      {a.unit ? <span className="text-ink-2"> {a.unit}</span> : null}
                    </td>
                    <td className="px-4 py-2.5 break-words text-ink-2">
                      {a.source?.startsWith("http") ? (
                        <a href={a.source.split(" ")[0]} target="_blank" rel="noreferrer" className="underline underline-offset-2">
                          {a.source}
                        </a>
                      ) : (
                        a.source
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-ink-2">{a.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>

      <button
        ref={chatBtn}
        type="button"
        onClick={() => setChatOpen(true)}
        className="btn btn-ink fixed right-4 bottom-4 z-30 shadow-[4px_4px_0_var(--color-sun)] md:right-8 md:bottom-8"
        aria-haspopup="dialog"
        aria-expanded={chatOpen}
      >
        <ChatCircleText size={22} weight="bold" aria-hidden />
        {t("chat.open")}
      </button>
      {chatOpen ? (
        <Suspense fallback={null}>
          <ChatPanel planId={data.planId} onClose={() => {
              setChatOpen(false);
              chatBtn.current?.focus();
            }}
          />
        </Suspense>
      ) : null}
    </div>
  );
}

function AccuracyBadge({ plan }: { plan: Plan }) {
  const { t } = useTranslation();
  const level = { exact: 3, estimate: 2, rough: 1 }[plan.accuracy];
  return (
    <p className="mt-6 flex items-center gap-3 text-[15px] font-semibold">
      <span aria-hidden className="flex gap-1">
        {[1, 2, 3].map((n) => (
          <i key={n} className={`block h-3.5 w-5 border-2 border-ink ${n <= level ? "bg-ink" : ""}`} />
        ))}
      </span>
      {t(`plan.accuracy.${plan.accuracy}`)}
    </p>
  );
}

function Cell({ label, value, note, i, tone }: { label: string; value: string; note?: string; i: number; tone?: "sun" }) {
  // 2 columns on phones, 5 on desktop; borders follow the grid.
  const mobileLeft = i % 2 === 1 ? "border-l-2 border-ink pl-3.5" : "pl-0";
  const mobileTop = i >= 2 ? "border-t-2 border-ink md:border-t-0" : "";
  const deskLeft = i > 0 ? "md:border-l-2 md:border-ink md:pl-5" : "md:pl-0";
  return (
    <div className={`py-5 pr-3 md:py-7 ${mobileLeft} ${mobileTop} ${deskLeft} ${i === 4 ? "col-span-2 md:col-span-1" : ""} ${i === 4 ? "!border-l-0 md:!border-l-2" : ""}`}>
      <small className="block text-[15px] font-medium text-ink-2">{label}</small>
      <b className={`display tabular mt-2 block whitespace-nowrap text-[clamp(22px,6.6vw,30px)] font-semibold leading-tight lg:text-[36px] ${tone === "sun" ? "text-sun-ink" : ""}`}>{value}</b>
      {note ? <span className="mt-1 block text-[14px] text-ink-2">{note}</span> : null}
    </div>
  );
}

function Row({ label, value, big }: { label: string; value: string; big?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-rule py-3">
      <dt className="text-ink-2">{label}</dt>
      <dd className={`display tabular font-semibold ${big ? "text-[30px]" : "text-[22px]"}`}>{value}</dd>
    </div>
  );
}

function LoanBlock({ option, border }: { option: SystemOption; border: boolean }) {
  const { t } = useTranslation();
  const loan = option.loan!;
  const gap = loan.emi - loan.monthly_saving;
  const max = Math.max(loan.emi, loan.monthly_saving);
  return (
    <div className={`py-9 md:py-12 ${border ? "border-b-2 border-ink md:border-r-2 md:border-b-0 md:pr-10" : ""}`}>
      <h2 className="display text-[clamp(26px,3.4vw,34px)] font-semibold leading-none">{t("plan.loanTitle")}</h2>
      <p className="mt-4 text-[17px]">
        {t("plan.loanLine", { amount: inr(loan.loan_amount), rate: num(loan.rate_pct), years: loan.years, margin: inr(loan.margin_amount) })}
      </p>
      <div className="mt-6 space-y-4">
        {[
          [t("plan.emi"), loan.emi, "bg-ink"],
          [t("plan.vsSaving"), loan.monthly_saving, "bg-sun"],
        ].map(([label, v, cls]) => (
          <div key={label as string}>
            <div className="flex items-baseline justify-between">
              <span className="font-medium">{label}</span>
              <span className="display tabular text-[26px] font-semibold">{inr(v as number)}</span>
            </div>
            <div className="mt-1 h-5 border-2 border-ink">
              <div className={`h-full ${cls}`} style={{ width: `${((v as number) / max) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
      <p className="mt-5 font-semibold">{loan.emi_covered_by_saving ? t("plan.emiCovered") : t("plan.emiNotCovered", { gap: inr(gap) })}</p>
      <p className="help">{t("plan.loanHow")}</p>
    </div>
  );
}

function AltBlock({ alt, pad }: { alt: SystemOption; pad: boolean }) {
  const { t, i18n } = useTranslation();
  return (
    <div className={`py-9 md:py-12 ${pad ? "md:pl-10" : ""}`}>
      <h2 className="display text-[clamp(26px,3.4vw,34px)] font-semibold leading-none">{t("plan.altTitle", { kw: num(alt.kw) })}</h2>
      <p className="mt-4 text-[17px]">
        {t("plan.altText", {
          subsidy: inr(alt.subsidy.total),
          pay: inr(alt.net_cost),
          payback: alt.payback_years == null ? "–" : num(alt.payback_years),
        })}
      </p>
      <dl className="mt-6 grid grid-cols-3 border-2 border-ink">
        {[
          [t("plan.stripPay"), inr(alt.net_cost)],
          [t("plan.savingMonth"), inr(alt.monthly_saving_avg)],
          [t("plan.paysBackIn"), alt.payback_years == null ? "–" : `${num(alt.payback_years)} ${t("plan.years")}`],
        ].map(([k, v], i) => (
          <div key={k} className={`p-3 ${i > 0 ? "border-l-2 border-ink" : ""}`}>
            <dt className="text-[13px] text-ink-2">{k}</dt>
            <dd className="display tabular mt-1 text-[clamp(17px,4.6vw,22px)] font-semibold">{v}</dd>
          </div>
        ))}
      </dl>
      {alt.flags.filter((f) => i18n.exists(`flags.${f}`)).length ? (
        <ul className="mt-4 flex flex-wrap gap-2">
          {alt.flags
            .filter((f) => i18n.exists(`flags.${f}`))
            .map((f) => (
              <li key={f} className="border-2 border-ink px-2.5 py-1 text-[14px] font-medium">
                {t(`flags.${f}`)}
              </li>
            ))}
        </ul>
      ) : null}
    </div>
  );
}

function ReadyRow({ item }: { item: ReadinessItem }) {
  const { t, i18n } = useTranslation();
  const icon: Record<ReadinessItem["status"], ReactNode> = {
    pass: <CheckCircle size={26} weight="fill" aria-hidden />,
    warn: <WarningCircle size={26} weight="bold" aria-hidden className="text-sun-ink" />,
    fail: <XCircle size={26} weight="fill" aria-hidden className="text-alert" />,
  };
  return (
    <li className="flex min-h-14 gap-3 border-b border-rule py-3">
      <span className="mt-0.5 shrink-0">{icon[item.status]}</span>
      <div className="flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
          <span className="font-semibold">{i18n.exists(`ready.${item.code}`) ? t(`ready.${item.code}`) : item.code}</span>
          <span className={`text-[13px] font-bold ${item.status === "pass" ? "text-ink-2" : item.status === "fail" ? "text-alert" : "text-sun-ink"}`}>
            {t(`status.${item.status}`)}
          </span>
        </div>
        {item.fix && i18n.exists(`fix.${item.fix}`) ? <p className="mt-1 text-[15px] text-ink-2">{t(`fix.${item.fix}`)}</p> : null}
      </div>
    </li>
  );
}

function Sheet({ data, fullConsumer }: { data: PlanResponse; fullConsumer: string | null }) {
  const { t } = useTranslation();
  const plan = data.plan;
  const f = data.inputs?.fields ?? {};
  const consumer = fullConsumer ?? f.consumer_number ?? null;
  const masked = !fullConsumer && !!consumer && /[*•xX]{2,}/.test(consumer);
  const rows: [string, string][] = [
    [t("plan.sheetState"), plan.location?.state ?? plan.state ?? "–"],
    [t("plan.sheetDistrict"), plan.location?.district ?? "–"],
    [t("plan.sheetDiscom"), plan.discom.name ?? f.discom ?? "–"],
    [t("plan.sheetConsumer"), consumer ?? "–"],
    [t("plan.sheetKw"), `${num(plan.recommended.kw)} kW`],
    [t("plan.sheetLoad"), f.sanctioned_load_kw != null ? `${num(f.sanctioned_load_kw)} kW` : "–"],
    [t("plan.sheetPin"), plan.location?.pincode ?? data.inputs?.pincode ?? "–"],
  ];
  const text = rows.map(([k, v]) => `${k}: ${v}`).join("\n");
  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="display text-[clamp(28px,4vw,40px)] font-semibold leading-none">{t("plan.sheetTitle")}</h2>
          <p className="mt-2 text-ink-2">{t("plan.sheetLead")}</p>
        </div>
        <CopyButton text={text} />
      </div>
      <dl className="mt-6 border-2 border-ink bg-card">
        {rows.map(([k, v], i) => (
          <div key={k} className={`grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-3 px-4 py-3 ${i > 0 ? "border-t border-rule" : ""}`}>
            <dt className="text-ink-2">{k}</dt>
            <dd className="tabular font-semibold break-words">
              {v}
              {k === t("plan.sheetConsumer") && masked ? <span className="block text-[14px] font-normal text-ink-2">{t("plan.sheetMasked")}</span> : null}
            </dd>
          </div>
        ))}
      </dl>
    </>
  );
}
