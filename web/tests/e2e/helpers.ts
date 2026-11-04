import { createHmac } from "node:crypto";
import type { Page } from "@playwright/test";

export const PASSWORD = "Passw0rd!test";
export const ADMIN_TOTP_SECRET = "JBSWY3DPEHPK3PXP";
export const API = "http://localhost:8100/api/v1";

function base32Decode(input: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const c of input.replace(/=+$/, "")) bits += alphabet.indexOf(c).toString(2).padStart(5, "0");
  const bytes: number[] = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(bytes);
}

/** RFC 6238 TOTP (SHA-1, 30s, 6 digits), matching pyotp. */
export function totp(secret: string, now = Date.now()): string {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(now / 30000)));
  const hmac = createHmac("sha1", base32Decode(secret)).update(counter).digest();
  const offset = hmac[hmac.length - 1] & 0xf;
  const code = ((hmac.readUInt32BE(offset) & 0x7fffffff) % 1_000_000).toString().padStart(6, "0");
  return code;
}

export async function login(page: Page, email: string, next?: string) {
  await page.goto(next ? `/login?next=${encodeURIComponent(next)}` : "/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  // Wait for the session to be stored: either we leave /login, or the admin two-step prompt appears.
  await Promise.race([
    page.waitForURL((u) => !u.pathname.startsWith("/login")),
    page.getByRole("heading", { name: "Two-step sign-in" }).waitFor(),
  ]);
}

export async function loginAdmin(page: Page, email = "admin1@example.com") {
  await login(page, email);
  await page.getByLabel("6-digit code").fill(totp(ADMIN_TOTP_SECRET));
  await page.getByRole("button", { name: "Verify and sign in" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"));
}

/** Create an account through the real signup UI with a unique email. */
export async function signup(page: Page, label: string) {
  const email = `${label}.${Date.now()}.${Math.floor(Math.random() * 1e6)}@example.com`;
  await page.goto("/signup");
  await page.getByLabel("Full name").fill("Test " + label);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Phone number").fill("08031234567");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL(/verify-phone/);
  return email;
}

export const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==", "base64");

/** Confirms the phone number through the real UI after signup. */
export async function confirmPhone(page: Page) {
  await page.getByRole("button", { name: "Send code" }).click();
  await page.getByLabel("6-digit code").fill(await page.getByTestId("dev-code").innerText());
  await page.getByRole("button", { name: "Confirm" }).click();
  await page.waitForURL(/onboarding/);
}

/** A brand new seller through the real UI: signup, phone, shop. */
export async function newSeller(page: Page, shopName: string) {
  const email = await signup(page, "seller");
  await confirmPhone(page);
  await page.goto("/seller/start");
  await page.getByLabel("Shop name").fill(shopName);
  await page.getByLabel("About your shop").fill("Fresh bakes for UNILAG.");
  await page.getByLabel("Your hall or area").selectOption({ label: "Madam Tinubu Hall (MTH)" });
  await page.getByLabel(/I have read and accept/).check();
  await page.getByRole("button", { name: "Open shop" }).click();
  await page.waitForURL(/\/seller$/);
  return email;
}

/** Calls the API as the user signed in on this page (token comes from the page's storage). */
export async function apiAs(page: Page, method: "post" | "get" | "patch" | "put", path: string, data?: unknown) {
  const token = await page.evaluate(() => window.localStorage.getItem("cp_token"));
  const res = await page.request[method](`${API}${path}`, { data, headers: { Authorization: `Bearer ${token}` } });
  return { status: res.status(), body: await res.json().catch(() => null) };
}

export async function otherRole(browser: import("@playwright/test").Browser, page: Page, email: string | "admin") {
  const ctx = await browser.newContext({ viewport: page.viewportSize() ?? undefined });
  const p = await ctx.newPage();
  if (email === "admin") await loginAdmin(p);
  else await login(p, email);
  return { ctx, page: p };
}
