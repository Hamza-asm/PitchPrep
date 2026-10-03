import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import type { BriefDetail, SellerProfile } from "../src/lib/api";

const id = "00000000-0000-4000-8000-000000000001";
const seller = { offering: "Synthetic maintenance software", ideal_customer: "Synthetic repair businesses" };
const fixture = (): BriefDetail => ({
  id, request: { company_name: "Offline Test Company", target_url: "https://fixture.example/", pasted_text: "", link_confirmed: false },
  status: "completed", progress: [], version: 10, email_edit: null, error_code: null, message: null,
  created_at: "2026-10-03T09:00:00Z", updated_at: "2026-10-03T09:01:00Z",
  result: { company_name: "Offline Test Company", claims: [{ id: "fact", section: "snapshot", text: "This synthetic company repairs equipment.", source_ids: ["page"], verification_status: "verified" }],
    email: { subject: { id: "subject", text: "An introduction", source_ids: [] }, paragraphs: [{ id: "body", text: "This synthetic company repairs equipment. Could we talk?", source_ids: ["page"] }] },
    sources: [{ id: "page", type: "scraped", title: "Synthetic source", url: "https://fixture.example/", excerpt: "This synthetic company repairs equipment.", retrieved_at: "2026-10-03T09:00:00Z" }, { id: "user", type: "user_provided", title: "User-provided details", url: null, excerpt: "Synthetic listing details", retrieved_at: "2026-10-03T09:00:00Z" }],
    limited_data: true, evidence_limitations: ["No additional news was available."], verification: { checked_units: 3, supported_units: 3, removed_units: 0, revision_attempts: 0 },
  },
});

async function mockApi(page: Page, options: { profile?: SellerProfile | null; row?: BriefDetail; failProfile?: boolean; failCreate?: boolean } = {}) {
  let profile = options.profile === undefined ? seller : options.profile;
  let row = options.row ?? fixture();
  let submissions = 0;
  const mutations: { path: string; body: Record<string, unknown>; key?: string }[] = [];
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/")) {
      // Only frontend assets are allowed through. All other hosts are blocked.
      if (url.origin === "http://127.0.0.1:3100") return route.continue();
      return route.abort("blockedbyclient");
    }
    const path = url.pathname;
    const headers = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS" };
    const respond = (json: unknown, status = 200) => route.fulfill({ json, status, headers });
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    if (request.method() !== "GET") mutations.push({ path, body: request.postDataJSON(), key: request.headers()["idempotency-key"] });
    if (path === "/api/seller-profile") {
      if (options.failProfile) return respond({ message: "The saved workspace is temporarily unavailable." }, 503);
      if (request.method() === "PUT") profile = request.postDataJSON();
      return respond(profile);
    }
    if (path === "/api/briefs" && request.method() === "POST") {
      submissions++;
      if (options.failCreate && submissions === 1) return respond({ message: "Temporary connection problem. Your input is kept." }, 503);
      row = { ...row, request: request.postDataJSON() };
      return respond({ id, status: "queued", version: 0 }, 202);
    }
    if (path === "/api/briefs") return respond({ items: options.profile === null ? [] : [{ id, company_name: row.request.company_name, status: row.status, limited_data: !!row.result?.limited_data, created_at: row.created_at }], next_offset: null });
    if (path.endsWith("/stream")) return route.fulfill({ headers, contentType: "text/event-stream", body: `id: ${row.version}\nevent: ${row.status === "running" ? "progress" : "result"}\ndata: ${JSON.stringify(row)}\n\n` });
    if (path === `/api/briefs/${id}`) return respond(row);
    if (path.endsWith("/confirm-link")) { row = fixture(); return respond({ id, status: "queued", version: 11 }, 202); }
    if (path.endsWith("/email/regenerate")) { row = fixture(); row.version = 20; row.result!.email.subject.text = "A fresh introduction"; return respond({ id, status: "queued", version: 19 }, 202); }
    if (path.endsWith("/email")) { const value = request.postDataJSON(); row = { ...row, version: row.version + 1, email_edit: { subject: value.subject, body: value.body } }; return respond(row); }
    if (path.endsWith("/feedback")) return route.fulfill({ status: 204, headers });
    return respond({ message: "No offline fixture for this request." }, 404);
  });
  return mutations;
}

test("landing is decorative, responsive and accessible", async ({ page }, testInfo) => {
  const mutations = await mockApi(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Walk into every pitch prepared.");
  await expect(page.locator("main input, main textarea, main select, main form")).toHaveCount(0);
  await expect(page.locator(".hero .button")).toHaveCount(1);
  await expect(page.locator(".hero .button")).toHaveAttribute("href", "/app");
  await page.screenshot({ path: testInfo.outputPath("landing-desktop.png"), fullPage: true });
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
  await page.setViewportSize({ width: 360, height: 800 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.getByRole("button", { name: "Open navigation" })).toBeVisible();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("navigation", { name: "Mobile navigation" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Open navigation" })).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await page.locator(".tile-position").first().evaluate((el) => getComputedStyle(el).animationName)).toBe("none");
  await page.screenshot({ path: testInfo.outputPath("landing-mobile.png"), fullPage: true });
  expect(mutations).toHaveLength(0);
});

test("seller setup and generation retain input and reuse submission key on retry", async ({ page }) => {
  const mutations = await mockApi(page, { profile: null, failCreate: true });
  await page.goto("/app");
  await page.getByLabel("What do you sell?").fill(seller.offering);
  await page.getByLabel("Who is your ideal customer?").fill(seller.ideal_customer);
  await page.getByRole("button", { name: "Save seller profile" }).click();
  await page.getByLabel("Company name").fill("Offline Test Company");
  await page.getByLabel("Website or social link").fill("https://fixture.example/");
  await page.getByLabel("A little more context").fill("Synthetic pasted details");
  await page.getByRole("button", { name: "Prepare my brief" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Your input is kept");
  await expect(page.getByLabel("Company name")).toHaveValue("Offline Test Company");
  await page.getByRole("button", { name: "Prepare my brief" }).click();
  await expect(page).toHaveURL(`/app/${id}`);
  await expect(page.getByRole("heading", { name: "Company snapshot" })).toBeVisible();
  const submissions = mutations.filter((m) => m.path === "/api/briefs");
  expect(submissions).toHaveLength(2);
  expect(submissions[0].key).toBe(submissions[1].key);
  expect(submissions[0].body.link_confirmed).toBe(false);
});

test("brief sources, edits, regeneration, feedback and mobile layout", async ({ page, context }, testInfo) => {
  const mutations = await mockApi(page);
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/app/${id}`);
  await expect(page.getByText("Limited data", { exact: true })).toBeVisible();
  await expect(page.locator(".claim .source-chip")).toHaveAttribute("href", "https://fixture.example/");
  await expect(page.locator(".claim .badge")).toContainText("Verified");
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("brief-desktop.png"), fullPage: true });
  await page.getByLabel("Subject", { exact: true }).fill("My revised subject");
  await expect(page.getByRole("button", { name: "Regenerate", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Save edits" }).click();
  await expect(page.getByText("Your saved edit.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Copy email" }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain("My revised subject");
  await page.getByRole("button", { name: "Useful", exact: true }).click();
  await page.getByLabel("Anything to add?").fill("Synthetic test feedback");
  await page.getByRole("button", { name: "Save feedback" }).click();
  await expect(page.getByText("Thanks. Your feedback is saved.")).toBeVisible();
  await page.getByLabel("Email tone").selectOption("concise");
  await page.getByRole("button", { name: "Regenerate", exact: true }).click();
  await expect(page.getByLabel("Subject", { exact: true })).toHaveValue("A fresh introduction");
  expect(mutations.some((m) => m.path.endsWith("regenerate") && m.body.tone === "concise")).toBe(true);
  await page.setViewportSize({ width: 360, height: 800 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("brief-mobile.png"), fullPage: true });
});

test("mismatched link only continues after an explicit confirmation", async ({ page }) => {
  const row = fixture(); row.status = "needs_confirmation"; row.result = null; row.message = "The link does not appear to match. Confirm it before continuing.";
  const mutations = await mockApi(page, { row });
  await page.goto(`/app/${id}`);
  await expect(page.getByText("Is this the right company link?")).toBeVisible();
  expect(mutations).toHaveLength(0);
  await page.getByRole("button", { name: "Yes, continue with this link" }).click();
  await expect(page.getByRole("heading", { name: "Company snapshot" })).toBeVisible();
  expect(mutations[0].body).toEqual({ confirmed: true, expected_version: 10 });
});

test("running state announces actual stages without percentages", async ({ page }, testInfo) => {
  const row = fixture(); row.status = "running"; row.result = null; row.progress = [{ stage: "parsing", status: "complete", revision_attempt: 0 }, { stage: "collecting", status: "active", revision_attempt: 0 }];
  await mockApi(page, { row }); await page.goto(`/app/${id}`);
  await expect(page.getByText("Collecting in progress.")).toBeVisible();
  await expect(page.locator(".step[data-state='active']")).toHaveCount(1);
  await page.screenshot({ path: testInfo.outputPath("progress.png"), fullPage: true });
});

test("connection failure has a recovery action", async ({ page }) => {
  await mockApi(page, { failProfile: true }); await page.goto("/app");
  await expect(page.getByRole("heading", { name: "Let’s get you connected." })).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again", exact: true })).toBeVisible();
});

test("new brief stays usable at 360px and 200 percent text", async ({ page }, testInfo) => {
  await mockApi(page); await page.setViewportSize({ width: 360, height: 800 }); await page.goto("/app");
  await expect(page.getByLabel("Company name")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("input-mobile.png"), fullPage: true });
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
  await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
