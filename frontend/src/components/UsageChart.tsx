import { useTranslation } from "react-i18next";
import { num } from "../lib/format";

interface Props {
  used: number[];
  solar: number[];
  /** 1-based month numbers matching the arrays (defaults to Jan..Dec). */
  months?: number[];
}

const W = 720;
const H = 260;
const PAD_B = 28;
const PAD_T = 12;

export default function UsageChart({ used, solar, months }: Props) {
  const { t, i18n } = useTranslation();
  const ms = months ?? used.map((_, i) => i + 1);
  const fmt = new Intl.DateTimeFormat(i18n.resolvedLanguage === "hi" ? "hi-IN" : "en-IN", { month: "short" });
  const label = (m: number) => fmt.format(new Date(2026, m - 1, 1));
  const max = Math.max(1, ...used, ...solar) * 1.08;
  const n = used.length;
  const group = W / n;
  const bw = Math.min(26, group * 0.36);
  const y = (v: number) => PAD_T + (H - PAD_B - PAD_T) * (1 - v / max);
  const usedTotal = used.reduce((a, b) => a + b, 0);
  const solarTotal = solar.reduce((a, b) => a + b, 0);

  return (
    <figure>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        role="img"
        aria-label={`${t("plan.chartUsed")}: ${num(usedTotal, 0)} kWh. ${t("plan.chartSolar")}: ${num(solarTotal, 0)} kWh.`}
      >
        {[0.25, 0.5, 0.75].map((f) => (
          <line key={f} x1={0} x2={W} y1={y(max * f)} y2={y(max * f)} stroke="#C4C4BD" strokeWidth={1} />
        ))}
        {used.map((u, i) => {
          const x = i * group + group / 2;
          return (
            <g key={i}>
              <rect x={x - bw - 1} y={y(u)} width={bw} height={H - PAD_B - y(u)} fill="#1A1814" />
              <rect
                x={x + 1}
                y={y(solar[i] ?? 0)}
                width={bw}
                height={H - PAD_B - y(solar[i] ?? 0)}
                fill="#F2A900"
                stroke="#1A1814"
                strokeWidth={2}
              />
              <text x={x} y={H - 8} textAnchor="middle" fontSize={13} fill="#4F4B44" fontFamily="Switzer, Hind, sans-serif">
                {label(ms[i])}
              </text>
            </g>
          );
        })}
        <line x1={0} x2={W} y1={H - PAD_B} y2={H - PAD_B} stroke="#1A1814" strokeWidth={2} />
      </svg>
      <figcaption className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-[15px] font-medium">
        <span className="flex items-center gap-2">
          <i aria-hidden className="inline-block size-3.5 border-2 border-ink bg-ink" />
          {t("plan.chartUsed")}
        </span>
        <span className="flex items-center gap-2">
          <i aria-hidden className="inline-block size-3.5 border-2 border-ink bg-sun" />
          {t("plan.chartSolar")}
        </span>
      </figcaption>
      <table className="sr-only">
        <thead>
          <tr>
            <th>{t("fields.month")}</th>
            <th>{t("plan.chartUsed")}</th>
            <th>{t("plan.chartSolar")}</th>
          </tr>
        </thead>
        <tbody>
          {used.map((u, i) => (
            <tr key={i}>
              <td>{label(ms[i])}</td>
              <td>{num(u, 0)}</td>
              <td>{num(solar[i], 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
