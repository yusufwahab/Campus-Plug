import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { login, loginAdmin, otherRole } from "./helpers";

/** Buyer opens a listing from Kemi's Corner (verified, has payout details) and starts checkout. */
async function buyMeatPie(page: Page, opts: { delivery?: boolean } = {}) {
  await page.goto("/search?q=Meat%20pie");
  await page.getByRole("link", { name: /Meat pie box/ }).first().click();
  await page.getByRole("button", { name: "Buy now" }).filter({ visible: true }).first().click();
  const modal = page.getByRole("dialog", { name: "Choose how you get it" });
  if (opts.delivery) await modal.getByLabel(/Seller delivers/).check();
  await modal.getByRole("button", { name: "Continue to checkout" }).click();
  await expect(page).toHaveURL(/\/checkout\/CP-O-\d+$/);
  return page.url().split("/").pop()!;
}

async function payInTestMode(page: Page, total: string) {
  await page.getByRole("button", { name: `Pay ${total}` }).click();
  await page.getByRole("dialog").getByRole("button", { name: `Pay ${total}` }).click();
  await expect(page).toHaveURL(/\/checkout\/local\?reference=/);
  await expect(page.getByText("Test mode: no real money")).toBeVisible();
  await page.getByRole("button", { name: "Simulate successful payment" }).click();
  await expect(page.getByRole("heading", { name: "Payment received" })).toBeVisible();
}

async function sellerFlow(seller: Page, orderId: string, stages: string[]) {
  await seller.goto(`/seller/orders/${orderId}`);
  await seller.getByRole("button", { name: "Accept order" }).click();
  for (const stage of stages) {
    await seller.getByRole("button", { name: stage }).click();
    await expect(seller.getByText("Order updated").first()).toBeVisible();
  }
}

test("complete order: discover, buy, pay, deliver, confirm, payout and receipt", async ({ page, browser }) => {
  await login(page, "buyer1@example.com");
  const orderId = await buyMeatPie(page, { delivery: true });
  await expect(page.locator("dd", { hasText: "₦3,500" })).toBeVisible(); // ₦3,000 item + ₦500 delivery
  await expect(page.getByText(/commission/i)).toHaveCount(0); // buyers never see the platform's commission
  await payInTestMode(page, "₦3,500");

  // Receipt for the buyer with the order ID
  const receipt = page.getByLabel("Receipt");
  await expect(receipt).toContainText(orderId);
  await expect(receipt).toContainText("₦3,500");
  await expect(receipt).not.toContainText(/commission/i);

  // Seller sees the new paid order with their earnings after commission (20% of ₦3,000)
  const seller = await otherRole(browser, page, "seller.verified@example.com");
  await seller.page.goto("/seller/orders");
  await expect(seller.page.getByText(orderId).first()).toBeVisible();
  await sellerFlow(seller.page, orderId, ["Mark preparing", "Ready or out for delivery", "Mark delivered"]);
  await expect(seller.page.getByText("Campus Plug commission (20%)")).toBeVisible();
  await expect(seller.page.getByText("-₦600").first()).toBeVisible();
  await expect(seller.page.getByText("₦2,900").first()).toBeVisible(); // 3,000 - 600 + 500 delivery

  // Buyer confirms delivery; the payout job then pays the seller
  await page.goto(`/orders/${orderId}`);
  await expect(page.getByRole("heading", { name: "Meat pie box (6)" })).toBeVisible();
  await page.getByRole("button", { name: "I received it" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Yes, I received it" }).click();
  await expect(page.getByText("Delivery confirmed")).toBeVisible();
  await expect(page.getByText("Confirmed").first()).toBeVisible();
  await expect(async () => {
    await seller.page.reload();
    await expect(seller.page.getByText("Paid out").first()).toBeVisible({ timeout: 2000 });
  }).toPass({ timeout: 40000 });

  await seller.page.goto("/seller/earnings");
  await expect(seller.page.getByRole("heading", { name: "Earnings" })).toBeVisible();
  await expect(seller.page.getByText("Paid out").first()).toBeVisible();
  await expect(seller.page.getByRole("link", { name: orderId })).toBeVisible();
  await seller.ctx.close();
});

test("buyer cancels a paid order before the seller accepts and is refunded", async ({ page, browser }) => {
  await login(page, "buyer2@example.com");
  const orderId = await buyMeatPie(page);
  await payInTestMode(page, "₦3,000");
  await page.goto(`/orders/${orderId}`);
  await page.getByRole("button", { name: "Cancel order" }).click();
  const modal = page.getByRole("dialog");
  await expect(modal).toContainText("refunded in full");
  await modal.getByLabel(/Reason/).fill("Changed my mind");
  await modal.getByRole("button", { name: "Cancel order" }).click();
  await expect(page.getByText("Cancelled").first()).toBeVisible();
  const seller = await otherRole(browser, page, "seller.verified@example.com");
  await seller.page.goto(`/seller/orders/${orderId}`);
  await expect(seller.page.getByText("Cancelled").first()).toBeVisible();
  await expect(seller.page.getByRole("button", { name: "Accept order" })).toHaveCount(0);
  await seller.ctx.close();
});

test("seller declines a paid order and the buyer is refunded", async ({ page, browser }) => {
  await login(page, "buyer2@example.com");
  const orderId = await buyMeatPie(page);
  await payInTestMode(page, "₦3,000");
  const seller = await otherRole(browser, page, "seller.verified@example.com");
  await seller.page.goto(`/seller/orders/${orderId}`);
  await seller.page.getByRole("button", { name: "Decline" }).click();
  await seller.page.getByRole("dialog").getByLabel(/Reason/).fill("Sold out today");
  await seller.page.getByRole("dialog").getByRole("button", { name: "Decline order" }).click();
  await expect(seller.page.getByText("Cancelled").first()).toBeVisible();
  await page.goto(`/orders/${orderId}`);
  await expect(page.getByText("Cancelled").first()).toBeVisible();
  await expect(page.getByText("Sold out today").first()).toBeVisible();
  await seller.ctx.close();
});

test("dispute: buyer reports, seller responds, admin partly refunds and both are told", async ({ page, browser }) => {
  await login(page, "buyer1@example.com");
  const orderId = await buyMeatPie(page);
  await payInTestMode(page, "₦3,000");
  const seller = await otherRole(browser, page, "seller.verified@example.com");
  await sellerFlow(seller.page, orderId, ["Mark preparing", "Ready or out for delivery", "Mark delivered"]);

  await page.goto(`/orders/${orderId}`);
  await page.getByRole("link", { name: "Report a problem" }).click();
  await page.getByLabel("What went wrong?").selectOption("not_as_described");
  await page.getByLabel("What happened?").fill("Only five pies in the box instead of six.");
  await page.getByRole("button", { name: "Report problem" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Report problem" }).click();
  await expect(page).toHaveURL(new RegExp(`/orders/${orderId}$`));
  await expect(page.getByText(/Dispute CP-D-\d+/)).toBeVisible();
  await expect(page.getByRole("button", { name: "I received it" })).toHaveCount(0);

  await seller.page.goto(`/seller/orders/${orderId}`);
  await seller.page.getByRole("button", { name: "Respond with your side" }).click();
  await seller.page.getByLabel("Your side of the story").fill("I packed six, one may have been taken at handover.");
  await seller.page.getByRole("button", { name: "Send response" }).click();
  await expect(seller.page.getByText("Your response was sent")).toBeVisible();

  const admin = await otherRole(browser, page, "admin");
  await admin.page.goto("/admin/disputes");
  const row = admin.page.viewportSize()!.width < 768 ? admin.page.getByRole("listitem").filter({ hasText: orderId }) : admin.page.getByRole("row").filter({ hasText: orderId });
  await row.getByRole("button", { name: "Decide" }).click();
  const modal = admin.page.getByRole("dialog");
  await modal.getByLabel("Decision").selectOption("partial_refund");
  await modal.getByLabel(/Refund amount/).fill("500");
  await modal.getByLabel("Reason").fill("One pie missing, refund its share");
  await modal.getByRole("button", { name: "Record decision" }).click();
  await expect(admin.page.getByText("Decision recorded")).toBeVisible();

  // Both people see the outcome
  await page.reload();
  await expect(page.getByText(/partial refund/i).first()).toBeVisible();
  await expect(page.getByText(/₦500 refunded/)).toBeVisible();
  await seller.page.reload();
  await expect(seller.page.getByText(/partial refund/i).first()).toBeVisible();
  // commission 20% of ₦3,000 = ₦600; ₦500 refunded returns ₦100 of it -> seller gets 3,000 - 500 - 500 = ₦2,000
  await expect(seller.page.getByText("₦2,000").first()).toBeVisible();
  await page.goto("/notifications");
  await expect(page.getByText(/Dispute CP-D-\d+ resolved/).first()).toBeVisible();
  await admin.ctx.close();
  await seller.ctx.close();
});

test("buyer opens checkout from a seller's payment request in chat", async ({ page, browser }) => {
  await login(page, "buyer2@example.com");
  await page.goto("/search?q=Meat%20pie");
  await page.getByRole("link", { name: /Meat pie box/ }).first().click();
  await page.getByRole("button", { name: "Message seller" }).filter({ visible: true }).first().click();
  await expect(page).toHaveURL(/\/messages\/\d+$/);
  const convo = page.url().split("/").pop();
  const seller = await otherRole(browser, page, "seller.verified@example.com");
  await seller.page.goto(`/seller/messages/${convo}`);
  await seller.page.getByRole("button", { name: "Request payment" }).click();
  const modal = seller.page.getByRole("dialog", { name: "Request a payment" });
  await modal.getByLabel("Agreed price per item (₦)").fill("2500");
  await modal.getByLabel("Quantity").fill("2");
  await modal.getByRole("button", { name: "Send payment request" }).click();
  await expect(page.getByTestId("payment-request").last()).toContainText("₦5,000", { timeout: 15000 });
  await page.getByTestId("payment-request").last().getByRole("button", { name: "Pay ₦5,000" }).click();
  await expect(page).toHaveURL(/\/checkout\/CP-O-\d+$/);
  await expect(page.getByText("₦5,000").first()).toBeVisible();
  await payInTestMode(page, "₦5,000");
  await seller.ctx.close();
});

test("cash deals are recorded by both people and marked Not protected", async ({ page, browser }) => {
  await login(page, "buyer1@example.com");
  await page.goto("/search?q=Beaded%20bracelet");
  await page.getByRole("link", { name: /Beaded bracelet/ }).first().click();
  await page.getByRole("button", { name: "Message seller" }).filter({ visible: true }).first().click();
  await expect(page).toHaveURL(/\/messages\/\d+$/);
  await page.getByRole("button", { name: "Record cash deal" }).click();
  const modal = page.getByRole("dialog", { name: "Record a cash deal" });
  await expect(modal).toContainText("Not protected");
  await modal.getByRole("button", { name: "Record deal" }).click();
  await expect(page).toHaveURL(/\/orders\/CP-O-\d+$/);
  const orderId = page.url().split("/").pop()!;
  await expect(page.getByText("Not protected").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Report a problem" })).toHaveCount(0);

  const seller = await otherRole(browser, page, "seller.verified@example.com");
  await seller.page.goto(`/seller/orders/${orderId}`);
  await expect(seller.page.getByText("Not protected").first()).toBeVisible();
  await seller.page.getByRole("button", { name: "Confirm cash deal" }).click();
  await seller.page.getByRole("dialog").getByRole("button", { name: "Confirm deal" }).click();
  await expect(seller.page.getByText("Confirmed").first()).toBeVisible();
  await seller.ctx.close();
});

test("unverified sellers cannot take in-app payments: buyers are told how to proceed", async ({ page }) => {
  await login(page, "buyer1@example.com");
  await page.goto("/search?q=Jollof");
  await page.getByRole("link", { name: /Jollof rice/ }).first().click();
  await expect(page.getByText(/not verified yet, so in-app payment is off/).filter({ visible: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Buy now" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Message seller" }).filter({ visible: true }).first()).toBeVisible();
});

test("guests are asked to sign in to buy", async ({ page }) => {
  await page.goto("/search?q=Meat%20pie");
  await page.getByRole("link", { name: /Meat pie box/ }).first().click();
  await page.getByRole("button", { name: "Buy now" }).filter({ visible: true }).first().click();
  await expect(page.getByRole("dialog", { name: "Sign in to continue" })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.goto("/orders");
  await expect(page).toHaveURL(/login/);
});

test("account deletion is blocked while an order is open", async ({ page }) => {
  await login(page, "buyer2@example.com");
  const orderId = await buyMeatPie(page);
  await payInTestMode(page, "₦3,000");
  await page.goto("/account");
  await page.getByRole("button", { name: "Delete account" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete account" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "open order" })).toBeVisible();
  void orderId;
});

const adminFinance: [string, string][] = [
  ["/admin/orders", "Orders"],
  ["/admin/payments", "Payments"],
  ["/admin/payouts", "Payouts"],
  ["/admin/commission", "Commission and revenue"],
  ["/admin/disputes", "Disputes"],
];

test("admin finance pages load, have no horizontal scroll and pass accessibility checks", async ({ page }) => {
  await loginAdmin(page);
  for (const [path, heading] of adminFinance) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
    await page.getByRole("status", { name: "Loading" }).waitFor({ state: "detached" }).catch(() => undefined);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), `${path} scrolls sideways`).toBeLessThanOrEqual(0);
    expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations, `${path} a11y`).toEqual([]);
  }
});

test("admin finds an order by its ID and sees the frozen commission", async ({ page, browser }) => {
  await login(page, "buyer1@example.com");
  const orderId = await buyMeatPie(page);
  await payInTestMode(page, "₦3,000");
  const admin = await otherRole(browser, page, "admin");
  await admin.page.goto("/admin/orders");
  await admin.page.getByLabel(/Search order ID/).fill(orderId);
  await expect(admin.page.getByText(orderId).filter({ visible: true }).first()).toBeVisible();
  await admin.page.getByRole("link", { name: orderId }).filter({ visible: true }).first().click();
  await expect(admin.page.getByRole("heading", { name: orderId })).toBeVisible();
  await expect(admin.page.getByText(/Commission \(20%, frozen on this order\)/)).toBeVisible();
  await expect(admin.page.getByText("₦600").first()).toBeVisible();
  await admin.ctx.close();
});

for (const path of ["/orders", "/seller/earnings", "/seller/orders"]) {
  test(`layout and accessibility: ${path}`, async ({ page }) => {
    await login(page, path.startsWith("/seller") ? "seller.verified@example.com" : "buyer1@example.com");
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.getByRole("status", { name: "Loading" }).waitFor({ state: "detached" }).catch(() => undefined);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
    expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
  });
}
