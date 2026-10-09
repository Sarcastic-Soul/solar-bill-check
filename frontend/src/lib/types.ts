export type Confidence = "high" | "medium" | "check" | "missing";

export interface HistoryPoint {
  month: string;
  units_kwh: number | null;
}

export interface BillFields {
  is_electricity_bill?: boolean | null;
  discom?: string | null;
  state?: string | null;
  consumer_number?: string | null;
  consumer_name?: string | null;
  tariff_category?: string | null;
  is_residential?: boolean | null;
  sanctioned_load_kw?: number | null;
  connection_phase?: "single" | "three" | null;
  billing_period_start?: string | null;
  billing_period_end?: string | null;
  billing_days?: number | null;
  billing_cycle?: "monthly" | "bimonthly" | null;
  units_billed_kwh?: number | null;
  bill_amount_rs?: number | null;
  consumption_history?: HistoryPoint[] | null;
  has_solar_net_meter?: boolean | null;
  export_units_kwh?: number | null;
  meter_reading_type?: "actual" | "estimated" | "unknown" | null;
  pincode?: string | null;
}

export type FieldKey = keyof BillFields;

export interface Disagreement {
  field: FieldKey;
  kind: string;
  candidates: unknown[];
}

export interface Warning {
  code: string;
  field: FieldKey | null;
  level: "info" | "check" | "error";
  message: string;
}

export interface ExtractResult {
  fields: BillFields;
  confidence: Partial<Record<FieldKey, Confidence>>;
  disagreements: Disagreement[];
  warnings: Warning[];
  models_used: { id: string; ok: boolean; latency_ms?: number; error?: string }[];
  latency_ms: { total: number };
}

export interface Answers {
  owns_roof: boolean | null;
  name_matches_bank: boolean | null;
  previous_subsidy: boolean | null;
}

export interface Overrides {
  roof_area_m2?: number;
  shading_loss_pct?: number;
}

export interface PlanRequest {
  fields: BillFields;
  pincode?: string;
  answers: Answers;
  overrides: Overrides;
  monthly_units?: number | number[];
}

export interface Loan {
  loan_amount: number;
  margin_amount: number;
  rate_pct: number;
  years: number;
  emi: number;
  monthly_saving: number;
  emi_covered_by_saving: boolean;
}

export interface MonthRow {
  month: number;
  units: number;
  solar_kwh: number;
  bill_before: number;
  bill_after: number;
  saving: number;
}

export interface Subsidy {
  central: number;
  state_topup: number;
  state_topup_status: string;
  state_topup_included: boolean;
  total: number;
  mode: "individual" | "rwa" | "none";
  eligible_kw: number;
  notes: string[];
}

export interface SystemOption {
  label: "recommended" | "full_subsidy_3kw" | "custom";
  kw: number;
  cost_per_kw: number;
  gross_cost: number;
  subsidy: Subsidy;
  net_cost: number;
  annual_generation_kwh: number;
  roof_area_needed_m2: number;
  monthly: MonthRow[];
  bill_before_year: number;
  bill_after_year: number;
  export_kwh: number;
  export_income: number;
  year1_savings: number;
  monthly_saving_avg: number;
  payback_years: number | null;
  savings_25y: number;
  net_gain_25y: number;
  co2_kg_per_year: number;
  trees_equivalent: number;
  loan: Loan | null;
  flags: string[];
}

export interface ReadinessItem {
  code: string;
  status: "pass" | "warn" | "fail";
  reason: string;
  fix: string | null;
}

export interface Assumption {
  key: string;
  value: string | number | null;
  unit: string | null;
  source: string | null;
  status: string;
}

export interface Plan {
  engine_version: string;
  state: string | null;
  special_category: boolean;
  accuracy: "exact" | "estimate" | "rough";
  accuracy_notes: string[];
  discom: { code: string | null; name: string | null; state: string | null; accuracy: string; effective_rate_rs: number | null };
  location: { pincode: string | null; state: string | null; district: string | null } | null;
  consumption: { monthly_kwh: number[]; annual_kwh: number; average_monthly_kwh: number; months_from_bill: number; method: string };
  solar: { annual_kwh_per_kw: number; source: string };
  sizing: { ideal_kw: number; recommended_kw: number; caps_applied: string[]; cap_kw: number | null };
  verdict: { code: "worth_it" | "worth_it_with_loan" | "not_now"; reasons: string[] };
  recommended: SystemOption;
  alternative: SystemOption | null;
  readiness: ReadinessItem[];
  assumptions: Assumption[];
  warnings: string[];
}

export interface PlanResponse {
  planId: string;
  plan: Plan;
  expiresAt: number;
  inputs?: { fields: BillFields; pincode: string | null };
}
