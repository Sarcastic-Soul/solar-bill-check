// End-to-end flow test against a running site and the live API.
// BASE=https://main.d2y09rdd9synq1.amplifyapp.com npm run e2e   (or run `npm run preview` first for local)
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const HERE = dirname(fileURLToPath(import.meta.url));
const BASE = process.env.BASE || "http://localhost:4173";
const SHOTS = process.env.SHOTS || resolve(HERE, "../shots");
const BILLS = resolve(HERE, "../../eval/bills");
const only = process.argv[2];
const browser = await chromium.launch({ channel: "chrome" });
const results = [];
const errors = [];

async function ctx(width, lang = "en-US") {
  const c = await browser.newContext({ viewport: { width, height: width < 500 ? 844 : 900 }, locale: lang, deviceScaleFactor: 1 });
  const p = await c.newPage();
  p.on("console", (m) => m.type() === "error" && errors.push(`${p.url()} ${m.text()}`));
  p.on("pageerror", (e) => errors.push(`${p.url()} PAGEERROR ${e.message}`));
  return { c, p };
}
async function overflow(p, name) {
  const o = await p.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  if (o[0] > o[1]) errors.push(`${name}: horizontal overflow ${o[0]} > ${o[1]}`);
}
async function shot(p, name, full = true) {
  await p.waitForTimeout(400);
  await overflow(p, name);
  await p.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: full });
}
async function step(name, fn) {
  if (only && !name.startsWith(only)) return;
  const t0 = Date.now();
  try {
    await fn();
    results.push(`PASS ${name} (${((Date.now() - t0) / 1000).toFixed(1)}s)`);
  } catch (e) {
    results.push(`FAIL ${name}: ${e.message.split("\n")[0]}`);
  }
}
async function answer(p) {
  for (const q of ["Do you own the roof?", "same as on your bank", "solar subsidy for this house"]) {
    const fs = p.locator("fieldset", { hasText: q });
    await fs.getByRole("button", { name: q.includes("subsidy") ? "No" : "Yes", exact: true }).click();
  }
}
let planUrl = null;

await step("home", async () => {
  for (const w of [1440, 390]) {
    const { c, p } = await ctx(w);
    await p.goto(BASE);
    await p.waitForLoadState("networkidle");
    await shot(p, `home-${w}`);
    await shot(p, `home-${w}-fold`, false);
    await c.close();
  }
});

await step("delhi", async () => {
  const { c, p } = await ctx(1440);
  await p.goto(BASE);
  await p.getByTestId("file-input").setInputFiles(`${BILLS}/delhi-brpl-hindi-clean-01/bill.png`);
  await p.waitForURL("**/reading");
  await p.waitForTimeout(1500);
  await shot(p, "reading-1440", false);
  await p.waitForURL("**/check", { timeout: 90000 });
  await shot(p, "check-delhi-1440");
  await p.locator("#pin").fill("110075");
  await answer(p);
  await p.getByRole("button", { name: "See my solar plan" }).click();
  await p.waitForURL("**/plan/*", { timeout: 60000 });
  await p.getByRole("heading", { level: 1 }).waitFor();
  planUrl = p.url();
  await shot(p, "plan-delhi-1440");
  await shot(p, "plan-delhi-1440-fold", false);
  // listen
  const speakRes = p.waitForResponse((r) => r.url().endsWith("/speak"), { timeout: 30000 });
  await p.getByRole("button", { name: "Listen" }).click();
  const sr = await speakRes;
  if (sr.status() !== 200) throw new Error(`speak ${sr.status()}`);
  // chat
  await p.getByRole("button", { name: "Ask a question" }).click();
  await p.getByRole("dialog").waitFor();
  await p.getByRole("button", { name: "Can I get a loan?" }).click();
  await p.waitForResponse((r) => r.url().endsWith("/chat"), { timeout: 90000 });
  await p.waitForTimeout(600);
  await shot(p, "chat-1440", false);
  await c.close();
  console.log("planUrl", planUrl);
});

await step("share-hi", async () => {
  const url = planUrl ?? `${BASE}/plan/vViU9XBJBJnN5aYL`;
  for (const w of [390, 1440]) {
    const { c, p } = await ctx(w);
    await p.goto(url);
    await p.getByRole("heading", { level: 1 }).waitFor({ timeout: 30000 });
    if (w === 390) await shot(p, "plan-share-390");
    await p.getByRole("button", { name: "हिन्दी" }).click();
    await p.waitForTimeout(800);
    await shot(p, `plan-hi-${w}`);
    await c.close();
  }
});

await step("msedcl-photo", async () => {
  const { c, p } = await ctx(390);
  await p.goto(BASE);
  await p.getByTestId("file-input").setInputFiles(`${BILLS}/msedcl-marathi-devanagari-01-photo/bill.jpg`);
  await p.waitForURL("**/check", { timeout: 90000 });
  await shot(p, "check-msedcl-390");
  const groups = p.getByRole("radiogroup");
  const n = await groups.count();
  for (let i = 0; i < n; i++) await groups.nth(i).getByRole("radio").first().click();
  await p.locator("#pin").fill("411001");
  await answer(p);
  await p.getByRole("button", { name: "See my solar plan" }).click();
  await p.waitForURL("**/plan/*", { timeout: 60000 });
  await p.getByRole("heading", { level: 1 }).waitFor();
  await shot(p, "plan-msedcl-390");
  console.log("msedcl disagreement groups", n, p.url());
  await c.close();
});

await step("water-bill", async () => {
  const { c, p } = await ctx(390);
  await p.goto(BASE);
  await p.getByTestId("file-input").setInputFiles(`${BILLS}/nonbill-water-bill-01/bill.png`);
  await p.getByRole("alert").waitFor({ timeout: 90000 });
  const txt = await p.getByRole("alert").innerText();
  if (!/electricity bill/i.test(txt)) throw new Error("unexpected alert: " + txt);
  await shot(p, "error-waterbill-390", false);
  await c.close();
});

await step("manual", async () => {
  const { c, p } = await ctx(390);
  await p.goto(`${BASE}/manual`);
  await p.getByRole("button", { name: "See my solar plan" }).click();
  await shot(p, "manual-errors-390", false);
  await p.locator("#state").selectOption("Karnataka");
  await p.locator("#units").fill("320");
  await p.locator("#pincode").fill("560001");
  await p.getByRole("button", { name: "See my solar plan" }).click();
  await p.waitForURL("**/plan/*", { timeout: 60000 });
  await p.getByRole("heading", { level: 1 }).waitFor();
  await shot(p, "plan-manual-390");
  await c.close();
});

await step("notfound", async () => {
  const { c, p } = await ctx(390);
  await p.goto(`${BASE}/plan/doesNotExist12345`);
  await p.getByRole("alert").waitFor({ timeout: 30000 });
  await shot(p, "plan-expired-390", false);
  await c.close();
});

await browser.close();
console.log(results.join("\n"));
console.log("ERRORS:\n" + (errors.join("\n") || "none"));
