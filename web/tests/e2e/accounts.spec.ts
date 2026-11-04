import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { loginAdmin, login, signup } from "./helpers";

test("guest is sent to sign in and returned afterwards", async ({ page }) => {
  await page.goto("/account");
  await expect(page).toHaveURL(/\/login\?next=%2Faccount/);
  await login(page, "buyer1@example.com", "/account");
  await expect(page.getByRole("heading", { name: "Account", exact: true })).toBeVisible();
});

test("wrong password shows an inline error", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("buyer1@example.com");
  await page.getByLabel("Password", { exact: true }).fill("not-the-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "incorrect" })).toBeVisible();
});

test("signup, email confirmation, onboarding and sign out", async ({ page }) => {
  await signup(page, "newbie");
  await expect(page.getByRole("heading", { name: "Confirm your email" })).toBeVisible();
  await page.getByRole("button", { name: "Send a new code" }).click();
  const code = await page.getByTestId("dev-code").innerText();
  await page.getByLabel("6-digit code").fill(code);
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByRole("heading", { name: "Set up your campus" })).toBeVisible();
  await page.getByLabel("Where are you?").selectOption({ label: "Madam Tinubu Hall (MTH)" });
  await page.getByRole("button", { name: "Food" }).click();
  await page.getByRole("button", { name: "Finish" }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/account");
  await expect(page.getByText("Email confirmed")).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/account");
  await expect(page).toHaveURL(/\/login/);
});

test("password reset journey", async ({ page }) => {
  const email = await signup(page, "resetme");
  await page.goto("/forgot-password");
  await page.getByLabel("Email").fill(email);
  await page.getByRole("button", { name: "Send reset link" }).click();
  await page.getByRole("link", { name: "open the reset link" }).click();
  await page.getByLabel("New password", { exact: true }).fill("a-brand-new-pass");
  await page.getByRole("button", { name: "Update password" }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("a-brand-new-pass");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/$/);
});

test("each role is blocked from other areas", async ({ page }) => {
  await login(page, "buyer1@example.com");
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/admin");
  await expect(page).toHaveURL(/access-denied/);
  await page.goto("/seller");
  await expect(page).toHaveURL(/access-denied/);
});

test("admin needs two-step sign-in", async ({ page }) => {
  await loginAdmin(page);
  await expect(page).toHaveURL(/\/admin/);
  await expect(page.getByRole("heading", { name: "Admin overview" })).toBeVisible();
});

test("admin password alone does not open the admin area", async ({ page }) => {
  await login(page, "admin2@example.com");
  await expect(page.getByRole("heading", { name: "Two-step sign-in" })).toBeVisible();
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/login/);
});

for (const path of ["/login", "/signup", "/forgot-password"]) {
  test(`accessibility: ${path}`, async ({ page }) => {
    await page.goto(path);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    expect(results.violations).toEqual([]);
  });
}

test("password fields can be shown and hidden", async ({ page }) => {
  for (const path of ["/login", "/signup"]) {
    await page.goto(path);
    const field = page.getByLabel("Password", { exact: true });
    await field.fill("my-secret-pass");
    await expect(field).toHaveAttribute("type", "password"); // hidden by default
    await page.getByRole("button", { name: "Show password" }).click();
    await expect(field).toHaveAttribute("type", "text");
    await expect(page.getByRole("button", { name: "Hide password" })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Hide password" }).click();
    await expect(field).toHaveAttribute("type", "password");
    await expect(field).toHaveValue("my-secret-pass"); // toggling never clears what was typed
  }
});
