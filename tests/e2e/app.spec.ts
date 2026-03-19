import { test, expect } from "@playwright/test";

test.describe("DB Analyzer v7 — E2E", () => {
  test("home page loads and shows app title", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("text=Analyzer").first()).toBeVisible({ timeout: 15_000 });
  });

  test("navigation: main nav links work", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("text=Analyzer").first()).toBeVisible({ timeout: 15_000 });

    const nav = page.getByRole("navigation").first();
    await expect(nav).toBeVisible();

    await page.getByRole("link", { name: /dashboard/i }).first().click();
    await expect(page).toHaveURL(/\/(|\?)/);

    await page.getByRole("link", { name: /query/i }).first().click();
    await expect(page).toHaveURL(/\/query/);

    await page.getByRole("link", { name: /health/i }).first().click();
    await expect(page).toHaveURL(/\/health/);

    await page.getByRole("link", { name: /sandbox/i }).first().click();
    await expect(page).toHaveURL(/\/sandbox/);

    await page.getByRole("link", { name: /chat/i }).first().click();
    await expect(page).toHaveURL(/\/chat/);

    await page.getByRole("link", { name: /simulation/i }).first().click();
    await expect(page).toHaveURL(/\/simulation/);
  });

  test("health page shows content or empty state", async ({ page }) => {
    await page.goto("/health");
    await expect(page.getByRole("heading", { name: /health/i }).first()).toBeVisible({ timeout: 10_000 });
  });

  test("sandbox page has query input and run", async ({ page }) => {
    await page.goto("/sandbox");
    await expect(page.getByRole("textbox", { name: /query|sql/i }).or(page.locator("textarea")).first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: /run|execute/i }).first()).toBeVisible();
  });

  test("chat page has input and send", async ({ page }) => {
    await page.goto("/chat");
    await expect(page.getByRole("textbox", { name: /message|ask/i }).or(page.getByPlaceholder(/ask|message/i)).first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: /send/i }).first()).toBeVisible();
  });

  test("simulation page has type selector and run", async ({ page }) => {
    await page.goto("/simulation");
    await expect(page.getByText(/simulation type|partition|growth/i).first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: /run simulation/i }).first()).toBeVisible();
  });

  test("API health via app is reachable", async ({ request }) => {
    const baseURL = process.env.BASE_URL || "http://localhost:3000";
    const res = await request.get(`${baseURL}/health/live`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("status", "ok");
  });
});
