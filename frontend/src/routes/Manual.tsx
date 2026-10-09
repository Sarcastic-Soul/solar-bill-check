import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight } from "@phosphor-icons/react";
import ErrorPanel from "../components/ErrorPanel";
import { createPlan } from "../lib/api";
import { setFlow } from "../lib/store";
import type { PlanRequest } from "../lib/types";

const STATES = [
  "Andaman and Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chandigarh", "Chhattisgarh",
  "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jammu and Kashmir",
  "Jharkhand", "Karnataka", "Kerala", "Ladakh", "Lakshadweep", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
  "Mizoram", "Nagaland", "Odisha", "Puducherry", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
  "Uttar Pradesh", "Uttarakhand", "West Bengal",
];

export default function Manual() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [state, setState] = useState("");
  const [units, setUnits] = useState("");
  const [load, setLoad] = useState("");
  const [pincode, setPincode] = useState("");
  const [errs, setErrs] = useState<Record<string, string>>({});

  const mutation = useMutation({
    mutationFn: createPlan,
    onSuccess: (res, req) => {
      qc.setQueryData(["plan", res.planId], { ...res, inputs: { fields: req.fields, pincode: req.pincode ?? null } });
      setFlow({ planId: res.planId, consumerNumber: null });
      navigate(`/plan/${res.planId}`);
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    const u = Number(units.replace(/,/g, ""));
    const l = load.trim() ? Number(load) : null;
    const next: Record<string, string> = {};
    if (!state) next.state = t("manual.badState");
    if (!units.trim() || !Number.isFinite(u) || u < 1 || u > 20000) next.units = t("manual.badUnits");
    if (pincode && !/^[1-9]\d{5}$/.test(pincode)) next.pincode = t("errors.BAD_PINCODE");
    setErrs(next);
    if (Object.keys(next).length) {
      document.getElementById(Object.keys(next)[0])?.focus();
      return;
    }
    const req: PlanRequest = {
      fields: {
        is_electricity_bill: true,
        state,
        is_residential: true,
        billing_cycle: "monthly",
        units_billed_kwh: u,
        sanctioned_load_kw: l != null && Number.isFinite(l) && l > 0 ? l : null,
      },
      pincode: pincode || undefined,
      answers: { owns_roof: null, name_matches_bank: null, previous_subsidy: null },
      overrides: {},
      monthly_units: u,
    };
    mutation.mutate(req);
  }

  const err = (k: string) =>
    errs[k] ? (
      <p id={`${k}-err`} className="mt-1.5 font-semibold text-alert">
        {errs[k]}
      </p>
    ) : null;

  return (
    <form onSubmit={submit} noValidate className="wrap max-w-[760px] py-10 md:py-16">
      <h1 className="display text-[clamp(38px,6vw,64px)] font-semibold leading-[0.95]">{t("manual.title")}</h1>
      <p className="mt-3 text-[18px] text-ink-2">{t("manual.lead")}</p>

      <div className="mt-8 space-y-6 border-t-2 border-ink pt-8">
        <div>
          <label htmlFor="state" className="label">
            {t("manual.state")}
          </label>
          <select
            id="state"
            className="input cursor-pointer"
            value={state}
            onChange={(e) => setState(e.target.value)}
            aria-invalid={!!errs.state}
            aria-describedby={errs.state ? "state-err" : undefined}
          >
            <option value="">{t("manual.statePick")}</option>
            {STATES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          {err("state")}
        </div>
        <div>
          <label htmlFor="units" className="label">
            {t("manual.units")}
          </label>
          <input
            id="units"
            className="input"
            inputMode="numeric"
            value={units}
            onChange={(e) => setUnits(e.target.value)}
            aria-invalid={!!errs.units}
            aria-describedby={errs.units ? "units-err" : "units-help"}
          />
          <p id="units-help" className="help">
            {t("manual.unitsHelp")}
          </p>
          {err("units")}
        </div>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <div>
            <label htmlFor="load" className="label">
              {t("manual.load")}
            </label>
            <input id="load" className="input" inputMode="decimal" value={load} onChange={(e) => setLoad(e.target.value)} aria-describedby="load-help" />
            <p id="load-help" className="help">
              {t("manual.loadHelp")}
            </p>
          </div>
          <div>
            <label htmlFor="pincode" className="label">
              {t("check.pincode")}
            </label>
            <input
              id="pincode"
              className="input"
              inputMode="numeric"
              autoComplete="postal-code"
              maxLength={6}
              value={pincode}
              onChange={(e) => setPincode(e.target.value.replace(/\D/g, ""))}
              aria-invalid={!!errs.pincode}
              aria-describedby={errs.pincode ? "pincode-err" : "pincode-help"}
            />
            <p id="pincode-help" className="help">
              {t("check.pincodeHelp")}
            </p>
            {err("pincode")}
          </div>
        </div>

        {mutation.error ? <ErrorPanel error={mutation.error} /> : null}

        <button type="submit" disabled={mutation.isPending} className="btn btn-sun w-full justify-between !min-h-16 text-[19px]">
          {mutation.isPending ? t("check.building") : t("check.submit")}
          {mutation.isPending ? (
            <span aria-hidden className="size-6 animate-spin rounded-full border-[3px] border-ink border-t-transparent" />
          ) : (
            <ArrowRight size={24} weight="bold" aria-hidden />
          )}
        </button>
      </div>
    </form>
  );
}
