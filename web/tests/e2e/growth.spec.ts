import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { login, loginAdmin, otherRole } from "./helpers";

const unique = () => `${Date.now().toString(36).toUpperCase()}${Math.floor(Math.random() * 99)}`;

async function adminModalSubmit(page: Page, button: string) {
  const modal = page.getByRole("dialog");
  await modal.getByLabel("Reason").fill("End-to-end check");
  await modal.getByRole("button", { name: button }).click();
}

async function openMeatPieBuy(page: Page) {
  await page.goto("/search?q=Meat%20pie");
  await page.getByRole("link", { name: /Meat pie box/ }).first().click();
  await page.getByRole("button", { name: "Buy now" }).filter({ visible: true }).first().click();
  return page.getByRole("dialog", { name: "Choose how you get it" });
}

test("admin campaign code: buyer sees the discount and the order total drops", async ({ page, browser }) => {
  const code = `CAMP${unique()}`;
  const admin = await otherRole(browser, page, "admin");
  await admin.page.goto("/admin/promos");
  await admin.page.getByRole("button", { name: "New code" }).click();
  await admin.page.getByLabel("Code", { exact: true }).fill(code);
  await admin.page.getByLabel("Percent off").fill("10");
  await adminModalSubmit(admin.page, "Create code");
  await expect(admin.page.getByText(code).filter({ visible: true }).first()).toBeVisible();
  await admin.ctx.close();

  await login(page, "buyer1@example.com");
  const modal = await openMeatPieBuy(page);
  await modal.getByLabel("Promo code (optional)").fill(code);
  await modal.getByRole("button", { name: "Apply" }).click();
  await expect(modal.getByText(/₦300 off/)).toBeVisible(); // 10% of ₦3,000
  await modal.getByLabel(/Seller delivers/).check();
  await expect(modal.getByText("₦3,200")).toBeVisible(); // 3,000 + 500 delivery - 300
  await modal.getByRole("button", { name: "Continue to checkout" }).click();
  await expect(page).toHaveURL(/\/checkout\/CP-O-\d+$/, { timeout: 20_000 });
  await expect(page.locator("dd", { hasText: "₦3,200" })).toBeVisible();
});

test("a wrong promo code explains itself", async ({ page }) => {
  await login(page, "buyer1@example.com");
  const modal = await openMeatPieBuy(page);
  await modal.getByLabel("Promo code (optional)").fill("NOPE123");
  await modal.getByRole("button", { name: "Apply" }).click();
  await expect(modal.getByText("That promo code is not valid.")).toBeVisible();
});

test("seller creates a discount code and can turn it off", async ({ page }) => {
  const code = `SELL${unique()}`;
  await login(page, "seller.verified@example.com");
  await page.goto("/seller/promotions");
  await expect(page.getByRole("heading", { name: "Promotions", level: 1 })).toBeVisible();
  await page.getByLabel("Code", { exact: true }).fill(code);
  await page.getByLabel("Percent", { exact: true }).fill("5");
  await page.getByRole("button", { name: "Create code" }).click();
  const row = page.getByRole("listitem").filter({ hasText: code });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Turn off" }).click();
  await expect(row.getByRole("button", { name: "Turn on" })).toBeVisible();
});

test("plan: admin publishes it, verified seller buys it in test mode", async ({ page, browser }) => {
  const name = `Plan ${unique()}`;
  const admin = await otherRole(browser, page, "admin");
  await admin.page.goto("/admin/plans");
  await admin.page.getByRole("button", { name: "New plan" }).click();
  await admin.page.getByLabel("Name").fill(name);
  await admin.page.getByLabel("Price (₦)").fill("2000");
  await admin.page.getByLabel("Commission (%)").fill("10");
  await admin.page.getByLabel(/Benefits/).fill("Lower commission");
  await adminModalSubmit(admin.page, "Create plan");
  await expect(admin.page.getByText(name).filter({ visible: true }).first()).toBeVisible();
  await admin.ctx.close();

  await login(page, "seller.verified@example.com");
  await page.goto("/seller/promotions");
  const card = page.getByRole("listitem").filter({ hasText: name });
  await card.getByRole("button", { name: "Buy plan" }).click();
  await expect(page).toHaveURL(/\/checkout\/local\?reference=/);
  await page.getByRole("button", { name: "Simulate successful payment" }).click();
  await expect(page).toHaveURL(/\/seller\/promotions/);
  await expect(page.getByText(new RegExp(`You are on ${name}`))).toBeVisible();
  // Leave the shop on the default rate so later tests see the standard 20% commission.
  await page.getByRole("button", { name: "Cancel plan" }).click();
  await expect(page.getByText(new RegExp(`You are on ${name}`))).toHaveCount(0);
});

test("boost: seller pays, admin approves, listing shows Sponsored in search", async ({ page, browser }) => {
  await login(page, "seller.verified@example.com");
  await page.goto("/seller/promotions");
  await page.getByLabel("Listing", { exact: true }).selectOption({ label: "Meat pie box (6)" });
  await page.getByRole("button", { name: "Pay for boost" }).click();
  await expect(page).toHaveURL(/\/checkout\/local\?reference=/);
  await page.getByRole("button", { name: "Simulate successful payment" }).click();
  await expect(page).toHaveURL(/\/seller\/promotions/);
  await expect(page.getByText("Waiting for approval").first()).toBeVisible();

  const admin = await otherRole(browser, page, "admin");
  await admin.page.goto("/admin/sponsored");
  await admin.page.getByRole("button", { name: "Approve" }).filter({ visible: true }).first().click();
  await adminModalSubmit(admin.page, "Approve");
  await expect(admin.page.getByText("Boost updated").first()).toBeVisible();
  await admin.ctx.close();

  await page.goto("/search?q=Meat%20pie");
  await expect(page.getByText("Sponsored").first()).toBeVisible();
});

test("review: buyer rates a completed order, seller replies, the shop page shows both", async ({ page, browser }) => {
  await login(page, "buyer1@example.com");
  const modal = await openMeatPieBuy(page);
  await modal.getByRole("button", { name: "Continue to checkout" }).click();
  await expect(page).toHaveURL(/\/checkout\/CP-O-\d+$/, { timeout: 20_000 });
  const orderId = page.url().split("/").pop()!;
  await page.getByRole("button", { name: /^Pay ₦/ }).click();
  await page.getByRole("dialog").getByRole("button", { name: /^Pay ₦/ }).click();
  await page.getByRole("button", { name: "Simulate successful payment" }).click();
  await expect(page.getByRole("heading", { name: "Payment received" })).toBeVisible();

  const seller = await otherRole(browser, page, "seller.verified@example.com");
  await seller.page.goto(`/seller/orders/${orderId}`);
  await seller.page.getByRole("button", { name: "Accept order" }).click();
  for (const stage of ["Mark preparing", "Ready or out for delivery", "Mark delivered"]) {
    await seller.page.getByRole("button", { name: stage }).click();
    await expect(seller.page.getByText("Order updated").first()).toBeVisible();
  }

  await page.goto(`/orders/${orderId}`);
  await page.getByRole("button", { name: "I received it" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Yes, I received it" }).click();
  await expect(page.getByText("Delivery confirmed")).toBeVisible();
  await page.getByRole("link", { name: "Leave a review" }).click();
  await page.getByText("5★").click();
  await page.getByLabel("Comment (optional)").fill("Warm and tasty, arrived on time.");
  await page.getByRole("button", { name: "Send review" }).click();
  await expect(page).toHaveURL(new RegExp(`/orders/${orderId}$`));
  await expect(page.getByRole("link", { name: "Leave a review" })).toHaveCount(0);

  await seller.page.goto("/seller/reviews");
  const item = seller.page.getByRole("listitem").filter({ hasText: "Warm and tasty" });
  await item.getByLabel("Reply publicly").fill("Thank you, see you again!");
  await item.getByRole("button", { name: "Send reply" }).click();
  // "Your reply:" only appears once the reply is saved (the typed text alone also sits in the textarea).
  await expect(item.getByText("Your reply:")).toBeVisible();
  await seller.ctx.close();

  await page.goto("/shop/kemis-corner");
  await page.getByRole("tab", { name: "Reviews" }).click();
  await expect(page.getByText("Warm and tasty, arrived on time.")).toBeVisible();
  await expect(page.getByText("Thank you, see you again!")).toBeVisible();
});

test("analytics: admin overview and seller analytics load", async ({ page, browser }) => {
  const admin = await otherRole(browser, page, "admin");
  await admin.page.goto("/admin");
  await expect(admin.page.getByRole("heading", { name: "Marketplace activity" })).toBeVisible();
  await expect(admin.page.getByText("Listing views")).toBeVisible();
  await admin.ctx.close();
  await login(page, "seller.verified@example.com");
  await page.goto("/seller/analytics");
  await expect(page.getByRole("heading", { name: "Analytics", level: 1 })).toBeVisible();
  await expect(page.getByText("Confirmed deals")).toBeVisible();
});

test("new pages have no horizontal scroll and no accessibility violations", async ({ page }) => {
  await login(page, "seller.verified@example.com");
  for (const [path, heading] of [["/seller/promotions", "Promotions"], ["/seller/reviews", "Reviews"], ["/seller/analytics", "Analytics"]] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
    await page.getByRole("status", { name: "Loading" }).waitFor({ state: "detached" }).catch(() => undefined);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), `${path} scrolls sideways`).toBeLessThanOrEqual(0);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    expect(results.violations, `${path} accessibility`).toEqual([]);
  }
});

test("admin promo, plan and sponsored pages have no horizontal scroll and no accessibility violations", async ({ page }) => {
  await loginAdmin(page);
  for (const [path, heading] of [["/admin/promos", "Promo codes"], ["/admin/plans", "Plans"], ["/admin/sponsored", "Sponsored placements"]] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
    await page.getByRole("status", { name: "Loading" }).waitFor({ state: "detached" }).catch(() => undefined);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), `${path} scrolls sideways`).toBeLessThanOrEqual(0);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    expect(results.violations, `${path} accessibility`).toEqual([]);
  }
});
