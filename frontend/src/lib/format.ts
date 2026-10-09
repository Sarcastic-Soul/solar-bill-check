const inrFmt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const numFmt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 });

/** ₹1,62,500 (Indian grouping, Western digits). */
export const inr = (n: number | null | undefined) => (n == null ? "–" : `₹${inrFmt.format(Math.round(n))}`);

export const num = (n: number | null | undefined, digits = 1) =>
  n == null
    ? "–"
    : digits === 1
      ? numFmt.format(n)
      : new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits }).format(n);

/** ₹5.7 lakh for big amounts. */
export function inrShort(n: number, lang: string) {
  if (Math.abs(n) >= 100000) {
    const lakh = numFmt.format(Math.round(n / 10000) / 10);
    return lang === "hi" ? `₹${lakh} लाख` : `₹${lakh} lakh`;
  }
  return inr(n);
}

/** 2,757 kg -> "2.76" tonnes. */
export const tonnes = (kg: number) => new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(Math.round(kg / 10) / 100);
