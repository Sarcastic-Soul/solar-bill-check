import { useMemo, useRef, useState, type FormEvent, type ReactNode, type RefObject } from "react";
import { Link, useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check as CheckIcon, Info, Translate, WarningDiamond } from "@phosphor-icons/react";
import ErrorPanel from "../components/ErrorPanel";
import { createPlan } from "../lib/api";
import { inr, num } from "../lib/format";
import { setFlow, useFlow } from "../lib/store";
import type { BillFields, Confidence, Disagreement, FieldKey, HistoryPoint, PlanResponse } from "../lib/types";

const HINDI_STATES = [
  "Delhi",
  "Uttar Pradesh",
  "Bihar",
  "Madhya Pradesh",
  "Rajasthan",
  "Haryana",
  "Chhattisgarh",
  "Jharkhand",
  "Uttarakhand",
  "Himachal Pradesh",
];

const PIN_RE = /^[1-9]\d{5}$/;
type YesNo = boolean | null;
type Shade = "none" | "some" | "lot";
const SHADE_PCT: Record<Shade, number | undefined> = { none: undefined, some: 15, lot: 30 };

const toStr = (n: number | null | undefined) => (n == null ? "" : String(n));
const toNum = (s: string) => {
  const v = Number(s.replace(/,/g, "").trim());
  return s.trim() === "" || !Number.isFinite(v) ? null : v;
};

export default function Check() {
  const { t } = useTranslation();
  const { extract } = useFlow();
  if (!extract) {
    return (
      <div className="wrap max-w-[760px] py-16">
        <h1 className="display text-[40px] font-semibold">{t("check.empty")}</h1>
        <Link to="/" className="btn btn-ink mt-6">
          {t("check.start")}
        </Link>
      </div>
    );
  }
  return <CheckForm />;
}

function CheckForm() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const flow = useFlow();
  const ex = flow.extract!;
  const f0 = ex.fields;

  const [units, setUnits] = useState(toStr(f0.units_billed_kwh));
  const [amount, setAmount] = useState(toStr(f0.bill_amount_rs));
  const [load, setLoad] = useState(toStr(f0.sanctioned_load_kw));
  const [consumer, setConsumer] = useState(flow.consumerNumber ?? f0.consumer_number ?? "");
  const [cycle, setCycle] = useState(f0.billing_cycle ?? "monthly");
  const [residential, setResidential] = useState<YesNo>(f0.is_residential ?? null);
  const [history, setHistory] = useState<HistoryPoint[]>(f0.consumption_history ?? []);
  const [picked, setPicked] = useState<Partial<Record<FieldKey, number | "other">>>({});

  const [pincode, setPincode] = useState(f0.pincode ?? "");
  const [ownsRoof, setOwnsRoof] = useState<YesNo>(null);
  const [nameMatches, setNameMatches] = useState<YesNo>(null);
  const [prevSubsidy, setPrevSubsidy] = useState<YesNo>(null);
  const [roof, setRoof] = useState("");
  const [shade, setShade] = useState<Shade>("none");
  const [formError, setFormError] = useState<string | null>(null);

  const unitsRef = useRef<HTMLInputElement>(null);
  const amountRef = useRef<HTMLInputElement>(null);
  const refs: Partial<Record<FieldKey, RefObject<HTMLInputElement | null>>> = {
    units_billed_kwh: unitsRef,
    bill_amount_rs: amountRef,
  };

  const dis = useMemo(() => {
    const m: Partial<Record<FieldKey, Disagreement>> = {};
    for (const d of ex.disagreements) m[d.field] = d;
    return m;
  }, [ex.disagreements]);

  const conf = (k: FieldKey): Confidence => (dis[k] && picked[k] == null ? "check" : (ex.confidence[k] ?? "missing"));

  function pick(d: Disagreement, i: number | "other") {
    setPicked((p) => ({ ...p, [d.field]: i }));
    if (i === "other") {
      refs[d.field]?.current?.focus();
      return;
    }
    const v = d.candidates[i];
    if (d.field === "units_billed_kwh") setUnits(toStr(v as number));
    else if (d.field === "bill_amount_rs") setAmount(toStr(v as number));
    else if (d.field === "sanctioned_load_kw") setLoad(toStr(v as number));
    else if (d.field === "consumer_number") setConsumer(String(v ?? ""));
    else if (d.field === "consumption_history") setHistory((v as HistoryPoint[]) ?? []);
  }

  const mutation = useMutation({
    mutationFn: createPlan,
    onSuccess: (res: PlanResponse, req) => {
      qc.setQueryData(["plan", res.planId], { ...res, inputs: { fields: req.fields, pincode: req.pincode ?? null } });
      setFlow({ planId: res.planId, consumerNumber: consumer.trim() || null });
      navigate(`/plan/${res.planId}`);
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    const u = toNum(units);
    const cleanHistory = history.filter((h) => h.units_kwh != null && h.units_kwh > 0);
    if ((u == null || u <= 0) && cleanHistory.length === 0) {
      setFormError(t("check.missingUnits"));
      unitsRef.current?.focus();
      return;
    }
    const pin = pincode.replace(/\D/g, "");
    if (pin && !PIN_RE.test(pin)) {
      setFormError(t("errors.BAD_PINCODE"));
      return;
    }
    const fields: BillFields = {
      ...f0,
      units_billed_kwh: u,
      bill_amount_rs: toNum(amount),
      sanctioned_load_kw: toNum(load),
      consumer_number: consumer.trim() || null,
      billing_cycle: cycle,
      is_residential: residential,
      consumption_history: cleanHistory.length ? cleanHistory : null,
    };
    const roofM2 = toNum(roof);
    mutation.mutate({
      fields,
      pincode: pin || undefined,
      answers: { owns_roof: ownsRoof, name_matches_bank: nameMatches, previous_subsidy: prevSubsidy },
      overrides: {
        ...(roofM2 && roofM2 > 0 ? { roof_area_m2: roofM2 } : {}),
        ...(SHADE_PCT[shade] != null ? { shading_loss_pct: SHADE_PCT[shade] } : {}),
      },
    });
  }

  const showHindiHint = !flow.langChosen && i18n.resolvedLanguage !== "hi" && !!f0.state && HINDI_STATES.includes(f0.state);
  const warnings = ex.warnings.filter((w) => w.level !== "error");
  const scalarDis = ex.disagreements.filter((d) => d.field !== "consumption_history" && ["units_billed_kwh", "bill_amount_rs", "sanctioned_load_kw", "consumer_number"].includes(d.field));
  const historyDis = dis.consumption_history;
  const fmtCand = (d: Disagreement, v: unknown) =>
    d.field === "bill_amount_rs" ? inr(v as number) : d.field === "consumer_number" ? String(v) : `${num(v as number)}${d.field === "sanctioned_load_kw" ? " kW" : ""}`;

  return (
    <form onSubmit={submit} noValidate className="wrap pb-16">
      {showHindiHint ? (
        <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-3 border-2 border-ink bg-card p-4">
          <Translate size={26} weight="bold" aria-hidden />
          <p className="flex-1 font-medium">
            {t("check.hindiHint", { state: f0.state })}
          </p>
          <button
            type="button"
            lang="hi"
            className="btn btn-sun"
            onClick={() => {
              setFlow({ langChosen: true });
              void i18n.changeLanguage("hi");
            }}
          >
            {t("check.hindiSwitch")}
          </button>
        </div>
      ) : null}

      <header className="rule-b py-8 md:py-12">
        <h1 className="display text-[clamp(38px,6vw,72px)] font-semibold leading-[0.95]">{t("check.title")}</h1>
        <p className="mt-3 max-w-[38em] text-[18px] text-ink-2">{t("check.lead")}</p>
      </header>

      {scalarDis.map((d) => (
        <section key={d.field} className="rule-b flex flex-wrap items-center gap-x-6 gap-y-4 py-6" aria-label={t("check.disagreeTitle")}>
          <WarningDiamond size={30} weight="bold" aria-hidden />
          <p className="min-w-[240px] flex-1">
            <b>
              {t("check.disagreeTitle")}: {t(`fields.${d.field}`)}.
            </b>{" "}
            {t("check.disagreeText")}
          </p>
          <div role="radiogroup" aria-label={t(`fields.${d.field}`)} className="flex flex-wrap border-2 border-ink">
            {d.candidates.map((c, i) => (
              <button
                key={i}
                type="button"
                role="radio"
                aria-checked={picked[d.field] === i}
                onClick={() => pick(d, i)}
                className={`display tabular min-h-14 min-w-[120px] cursor-pointer px-5 text-[20px] font-semibold ${i > 0 ? "border-l-2 border-ink" : ""} ${picked[d.field] === i ? "bg-sun" : "hover:bg-paper-2"}`}
              >
                {fmtCand(d, c)}
              </button>
            ))}
            <button
              type="button"
              role="radio"
              aria-checked={picked[d.field] === "other"}
              onClick={() => pick(d, "other")}
              className={`min-h-14 cursor-pointer border-l-2 border-ink px-4 text-[15px] font-medium ${picked[d.field] === "other" ? "bg-sun" : "hover:bg-paper-2"}`}
            >
              {t("check.other")}
            </button>
          </div>
        </section>
      ))}

      <div className="grid grid-cols-1 md:grid-cols-12">
        <div className="py-8 md:col-span-7 md:border-r-2 md:border-ink md:pr-10">
          <h2 className="display text-[28px] font-semibold">{t("check.billSection")}</h2>
          <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2">
            <NumField id="units" label={t("fields.units_billed_kwh")} value={units} onChange={setUnits} conf={conf("units_billed_kwh")} inputRef={unitsRef} />
            <NumField id="amount" label={t("fields.bill_amount_rs")} value={amount} onChange={setAmount} conf={conf("bill_amount_rs")} inputRef={amountRef} />
            <NumField id="load" label={t("fields.sanctioned_load_kw")} value={load} onChange={setLoad} conf={conf("sanctioned_load_kw")} />
            <div>
              <FieldLabel htmlFor="consumer" conf={conf("consumer_number")}>
                {t("fields.consumer_number")}
              </FieldLabel>
              <input id="consumer" className="input" value={consumer} onChange={(e) => setConsumer(e.target.value)} autoComplete="off" spellCheck={false} />
            </div>
          </div>

          <dl className="mt-7 grid grid-cols-1 border-t-2 border-ink sm:grid-cols-2">
            <ReadOnly label={t("fields.discom")} value={f0.discom} conf={conf("discom")} />
            <ReadOnly label={t("fields.state")} value={f0.state} conf={conf("state")} />
            <ReadOnly label={t("fields.tariff_category")} value={f0.tariff_category} conf={conf("tariff_category")} />
            <ReadOnly
              label={t("fields.connection_phase")}
              value={f0.connection_phase ? t(`fields.${f0.connection_phase}`) : null}
              conf={conf("connection_phase")}
            />
            <ReadOnly
              label={t("fields.meter_reading_type")}
              value={f0.meter_reading_type && f0.meter_reading_type !== "unknown" ? t(`fields.${f0.meter_reading_type}`) : null}
              conf={conf("meter_reading_type")}
            />
            <ReadOnly
              label={t("fields.has_solar_net_meter")}
              value={f0.has_solar_net_meter == null ? null : f0.has_solar_net_meter ? t("check.yes") : t("check.no")}
              conf={conf("has_solar_net_meter")}
            />
          </dl>

          <div className="mt-7 grid grid-cols-1 gap-5 sm:grid-cols-2">
            <Choice
              label={t("fields.billing_cycle")}
              value={cycle}
              onChange={(v) => setCycle(v as "monthly" | "bimonthly")}
              options={[
                ["monthly", t("fields.monthly")],
                ["bimonthly", t("fields.bimonthly")],
              ]}
            />
            <Choice
              label={t("fields.is_residential")}
              value={residential == null ? "" : String(residential)}
              onChange={(v) => setResidential(v === "true")}
              options={[
                ["true", t("check.yes")],
                ["false", t("check.no")],
              ]}
            />
          </div>

          <h2 className="display mt-10 text-[28px] font-semibold">{t("check.historySection")}</h2>
          {historyDis ? (
            <div className="mt-4 border-2 border-ink bg-card p-4">
              <p className="flex items-start gap-2 font-medium">
                <WarningDiamond size={22} weight="bold" aria-hidden className="mt-0.5 shrink-0" />
                {t("check.disagreeTitle")}. {t("check.disagreeText")}
              </p>
              <div role="radiogroup" aria-label={t("check.historySection")} className="mt-3 flex flex-wrap gap-3">
                {historyDis.candidates.map((c, i) => {
                  const arr = (c as HistoryPoint[]) ?? [];
                  const first = arr.slice(0, 3).map((h) => num(h.units_kwh, 0)).join(", ");
                  return (
                    <button
                      key={i}
                      type="button"
                      role="radio"
                      aria-checked={picked.consumption_history === i}
                      onClick={() => pick(historyDis, i)}
                      className={`min-h-14 cursor-pointer border-2 border-ink px-4 py-2 text-left ${picked.consumption_history === i ? "bg-sun" : "hover:bg-paper-2"}`}
                    >
                      <span className="block font-semibold">{t("check.readerN", { n: i + 1, count: arr.length })}</span>
                      <span className="tabular text-[15px] text-ink-2">{first} …</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}
          {history.length ? (
            <div className="mt-4 grid grid-cols-3 gap-3 sm:grid-cols-4">
              {history.map((h, i) => (
                <div key={`${h.month}-${i}`}>
                  <label htmlFor={`h${i}`} className="block text-[14px] font-semibold text-ink-2">
                    <MonthName ym={h.month} />
                  </label>
                  <input
                    id={`h${i}`}
                    className="input !min-h-12 !text-[17px]"
                    inputMode="decimal"
                    value={toStr(h.units_kwh)}
                    onChange={(e) => {
                      const v = toNum(e.target.value);
                      setHistory((hs) => hs.map((x, j) => (j === i ? { ...x, units_kwh: v } : x)));
                    }}
                  />
                </div>
              ))}
            </div>
          ) : (
            <p className="help">{t("check.historyNone")}</p>
          )}

          {warnings.length ? (
            <section className="mt-10">
              <h2 className="display text-[24px] font-semibold">{t("check.warningsTitle")}</h2>
              <ul className="mt-3 border-t-2 border-ink">
                {warnings.map((w) => (
                  <li key={w.code} className="flex items-start gap-3 border-b border-rule py-3">
                    {w.level === "check" ? (
                      <WarningDiamond size={22} weight="bold" aria-hidden className="mt-0.5 shrink-0 text-sun-ink" />
                    ) : (
                      <Info size={22} weight="bold" aria-hidden className="mt-0.5 shrink-0" />
                    )}
                    <span>{i18n.exists(`warn.${w.code}`) ? t(`warn.${w.code}`) : w.message}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>

        <aside className="border-t-2 border-ink py-8 md:col-span-5 md:border-t-0 md:pl-10">
          <h2 className="display text-[28px] font-semibold">{t("check.questionsSection")}</h2>
          <div className="mt-5 space-y-6">
            <div>
              <label htmlFor="pin" className="label">
                {t("check.pincode")}
              </label>
              <input
                id="pin"
                className="input"
                inputMode="numeric"
                autoComplete="postal-code"
                maxLength={6}
                value={pincode}
                onChange={(e) => setPincode(e.target.value.replace(/\D/g, ""))}
                aria-describedby="pin-help"
              />
              <p id="pin-help" className="help">
                {t("check.pincodeHelp")}
              </p>
            </div>
            <YesNoQ label={t("check.ownsRoof")} value={ownsRoof} onChange={setOwnsRoof} />
            <YesNoQ label={t("check.nameMatches")} help={t("check.nameMatchesHelp")} value={nameMatches} onChange={setNameMatches} />
            <YesNoQ label={t("check.previousSubsidy")} value={prevSubsidy} onChange={setPrevSubsidy} />

            <details className="border-2 border-ink">
              <summary className="flex min-h-14 cursor-pointer items-center justify-between px-4 font-semibold">
                {t("check.optional")}: {t("check.roofArea").toLowerCase()}, {t("check.shade").toLowerCase()}
              </summary>
              <div className="space-y-5 border-t-2 border-ink p-4">
                <div>
                  <label htmlFor="roof" className="label">
                    {t("check.roofArea")}
                  </label>
                  <input id="roof" className="input" inputMode="decimal" value={roof} onChange={(e) => setRoof(e.target.value)} aria-describedby="roof-help" />
                  <p id="roof-help" className="help">
                    {t("check.roofAreaHelp")}
                  </p>
                </div>
                <Choice
                  label={t("check.shade")}
                  value={shade}
                  onChange={(v) => setShade(v as Shade)}
                  options={[
                    ["none", t("check.shadeNone")],
                    ["some", t("check.shadeSome")],
                    ["lot", t("check.shadeLot")],
                  ]}
                />
              </div>
            </details>

            {formError ? (
              <p role="alert" className="border-2 border-ink bg-sun-soft p-3 font-medium">
                {formError}
              </p>
            ) : null}
            {mutation.error ? (
              <ErrorPanel error={mutation.error}>
                <button type="submit" className="btn btn-ink">
                  {t("errors.retry")}
                </button>
              </ErrorPanel>
            ) : null}

            <button type="submit" disabled={mutation.isPending} className="btn btn-sun w-full justify-between !min-h-16 text-[19px]">
              {mutation.isPending ? t("check.building") : t("check.submit")}
              {mutation.isPending ? (
                <span aria-hidden className="size-6 animate-spin rounded-full border-[3px] border-ink border-t-transparent" />
              ) : (
                <ArrowRight size={24} weight="bold" aria-hidden />
              )}
            </button>
          </div>
        </aside>
      </div>
    </form>
  );
}

function ConfBadge({ conf }: { conf: Confidence }) {
  const { t } = useTranslation();
  const map: Record<Confidence, [string, string]> = {
    high: [t("check.agree"), "text-ink-2"],
    medium: [t("check.oneReader"), "text-ink-2"],
    check: [t("check.pleaseCheck"), "bg-sun px-1.5 text-ink"],
    missing: [t("check.notFound"), "text-ink-2"],
  };
  const [label, cls] = map[conf];
  return (
    <span className={`inline-flex items-center gap-1 text-[13px] font-semibold ${cls}`}>
      {conf === "high" ? <CheckIcon size={14} weight="bold" aria-hidden /> : null}
      {label}
    </span>
  );
}

function FieldLabel({ htmlFor, conf, children }: { htmlFor: string; conf: Confidence; children: ReactNode }) {
  return (
    <div className="mb-1.5 flex items-baseline justify-between gap-2">
      <label htmlFor={htmlFor} className="font-semibold">
        {children}
      </label>
      <ConfBadge conf={conf} />
    </div>
  );
}

function NumField(props: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  conf: Confidence;
  inputRef?: RefObject<HTMLInputElement | null>;
}) {
  return (
    <div>
      <FieldLabel htmlFor={props.id} conf={props.conf}>
        {props.label}
      </FieldLabel>
      <input
        id={props.id}
        ref={props.inputRef}
        className={`input ${props.conf === "check" ? "!bg-sun-soft" : ""}`}
        inputMode="decimal"
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
      />
    </div>
  );
}

function ReadOnly({ label, value, conf }: { label: string; value: string | null | undefined; conf: Confidence }) {
  return (
    <div className="border-b border-rule py-3 sm:odd:pr-4 sm:even:border-l sm:even:pl-4">
      <dt className="flex items-baseline justify-between gap-2 text-[14px] text-ink-2">
        {label}
        <ConfBadge conf={value ? conf : "missing"} />
      </dt>
      <dd className="mt-0.5 font-semibold">{value || "–"}</dd>
    </div>
  );
}

function Choice({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <fieldset>
      <legend className="label">{label}</legend>
      <div className="flex border-2 border-ink">
        {options.map(([v, l], i) => (
          <button
            key={v}
            type="button"
            aria-pressed={value === v}
            onClick={() => onChange(v)}
            className={`min-h-12 flex-1 cursor-pointer px-3 font-semibold ${i > 0 ? "border-l-2 border-ink" : ""} ${value === v ? "bg-ink text-paper" : "hover:bg-paper-2"}`}
          >
            {l}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

function YesNoQ({ label, help, value, onChange }: { label: string; help?: string; value: YesNo; onChange: (v: YesNo) => void }) {
  const { t } = useTranslation();
  const opts: [string, string, YesNo][] = [
    ["y", t("check.yes"), true],
    ["n", t("check.no"), false],
    ["u", t("check.notSure"), null],
  ];
  const [touched, setTouched] = useState(false);
  return (
    <fieldset>
      <legend className="label">{label}</legend>
      <div className="flex border-2 border-ink">
        {opts.map(([k, l, v], i) => {
          const on = touched && value === v;
          return (
            <button
              key={k}
              type="button"
              aria-pressed={on}
              onClick={() => {
                setTouched(true);
                onChange(v);
              }}
              className={`min-h-14 flex-1 cursor-pointer px-3 font-semibold ${i > 0 ? "border-l-2 border-ink" : ""} ${on ? "bg-ink text-paper" : "hover:bg-paper-2"}`}
            >
              {l}
            </button>
          );
        })}
      </div>
      {help ? <p className="help">{help}</p> : null}
    </fieldset>
  );
}

function MonthName({ ym }: { ym: string }) {
  const { i18n } = useTranslation();
  const [y, m] = ym.split("-").map(Number);
  if (!y || !m) return <>{ym}</>;
  return <>{new Intl.DateTimeFormat(i18n.resolvedLanguage === "hi" ? "hi-IN" : "en-IN", { month: "short", year: "2-digit" }).format(new Date(y, m - 1, 1))}</>;
}
