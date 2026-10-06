// Browser smoke test against a running stack (seeded demo data):  node scripts/e2e-smoke.mjs
// Needs Playwright: `npm i -D playwright` (or set PLAYWRIGHT_MODULE / PLAYWRIGHT_CHROMIUM to existing installs).
import { mkdirSync } from "node:fs";
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
mkdirSync("shots", { recursive: true });
const base = "http://localhost:3000";
const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM || undefined, args: ["--no-sandbox"] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const errs = [];
page.on("pageerror", (e) => errs.push(`[pageerror] ${e.message}`));
page.on("response", (r) => { if (r.status() >= 400 && r.url().includes("/api/") && !r.url().includes("/auth/refresh")) errs.push(`[http ${r.status()}] ${r.url()}`); });
const step = (s) => console.log("•", s);
await page.goto(base + "/login");
await page.fill('input[type=email]', "owner@acme-demo.example"); await page.fill('input[type=password]', "Demo@12345");
await page.click('button:has-text("Sign in")'); await page.waitForURL(/dashboard/);
step("logged in");

// Ask IntelliCRM drawer
await page.click('button:has-text("Ask IntelliCRM")');
await page.click('button:has-text("Which customers need attention today?")');
await page.waitForSelector("text=need attention");
await page.screenshot({ path: "shots/flow-ask.png" });
step("ask drawer ok: " + (await page.locator('aside[aria-label="Ask IntelliCRM"]').innerText()).split("\n").slice(1, 5).join(" | "));
await page.keyboard.press("Escape"); await page.click('button[aria-label="Close"]').catch(() => {});

// Global search
await page.goto(base + "/dashboard");
await page.fill("#global-search", "acme");
await page.waitForSelector("text=Acme Industries");
step("search ok");

// Create a lead via UI with validation
await page.goto(base + "/leads");
await page.click('button:has-text("Add Lead")');
await page.click('button:has-text("Create lead")');
await page.waitForSelector("text=Name is required");
step("validation shown");

await page.getByLabel("Name").first().fill("UI Test Lead");
await page.locator('input[type=email]').last().fill("ui@lead.example");
await page.click('button:has-text("Create lead")');
await page.waitForSelector("text=Lead created");
await page.fill('input[aria-label="Search leads"]', "UI Test Lead");
await page.waitForSelector("tbody tr:has-text('UI Test Lead')");
await page.click("tbody tr:has-text('UI Test Lead')");
await page.waitForSelector("text=Lead score");
await page.waitForSelector("text=Recommended action");
await page.screenshot({ path: "shots/flow-lead360.png" });
step("lead created + Lead 360 with explanation");

// Customer 360 AI tab
await page.goto(base + "/customers"); await page.click("tbody tr:has-text('Acme Industries')");
await page.click('button[role=tab]:has-text("AI Insights")');
await page.waitForSelector("text=Churn probability");
await page.screenshot({ path: "shots/flow-customer360.png" });
step("customer 360 AI tab ok");

// Invoice payment flow
await page.goto(base + "/invoices"); await page.click("tbody tr:has-text('Overdue')");
await page.click('button:has-text("Record payment")');
await page.click('button:has-text("Record payment") >> nth=-1');
await page.waitForSelector("text=Payment recorded");
step("payment recorded via UI");
await page.screenshot({ path: "shots/flow-invoice.png" });

// Mobile
const m = await browser.newContext({ viewport: { width: 390, height: 844 } });
const mp = await m.newPage();
await mp.goto(base + "/login"); await mp.fill('input[type=email]', "owner@acme-demo.example"); await mp.fill('input[type=password]', "Demo@12345");
await mp.click('button:has-text("Sign in")'); await mp.waitForURL(/dashboard/); await mp.waitForTimeout(1200);
await mp.screenshot({ path: "shots/mobile-dashboard.png" });
await mp.click('button[aria-label="Open menu"]'); await mp.waitForTimeout(300);
await mp.screenshot({ path: "shots/mobile-menu.png" });
const overflow = await mp.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
step("mobile horizontal overflow: " + overflow);
console.log(errs.length ? errs.join("\n") : "no page errors / http errors");
await browser.close();
