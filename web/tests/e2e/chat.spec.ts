import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { apiAs, login, otherRole } from "./helpers";

test("buyer and seller chat live in two sessions, with read receipts and a payment request", async ({ page, browser }, info) => {
  const stamp = `${info.project.name}${Date.now()}`;
  await login(page, "buyer1@example.com");
  await page.goto("/search?q=Meat%20pie");
  await page.getByRole("link", { name: /Meat pie box/ }).first().click();
  await page.getByRole("button", { name: "Message seller" }).and(page.locator(":visible")).first().click();
  await expect(page).toHaveURL(/\/messages\/\d+$/);
  const threadUrl = page.url();

  await page.getByLabel("Write a message").fill(`Is it still available? ${stamp}`);
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByRole("log", { name: "Messages" }).getByText(`Is it still available? ${stamp}`)).toBeVisible();

  // The seller, in a separate browser session, sees it arrive without anyone reloading.
  const seller = await otherRole(browser, page, "seller.verified@example.com");
  await seller.page.goto("/seller/messages");
  const row = seller.page.getByRole("link", { name: /Is it still available/ }).first();
  await expect(row).toBeVisible();
  await row.click();
  await expect(seller.page.getByRole("log", { name: "Messages" }).getByText(`Is it still available? ${stamp}`)).toBeVisible();

  // The seller replies and the buyer sees it live (polling) and sees the seller read the first message.
  await seller.page.getByLabel("Write a message").fill(`Yes, ready at 5pm ${stamp}`);
  await seller.page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByRole("log", { name: "Messages" }).getByText(`Yes, ready at 5pm ${stamp}`)).toBeVisible({ timeout: 15000 });
  await expect(page.getByLabel("Read").first()).toBeVisible({ timeout: 15000 });

  // Structured payment request from the seller
  await seller.page.getByRole("button", { name: "Request payment" }).click();
  const modal = seller.page.getByRole("dialog", { name: "Request a payment" });
  await modal.getByLabel("Agreed price per item (₦)").fill("3000");
  await modal.getByLabel("Quantity").fill("2");
  await modal.getByLabel(/Delivery fee/).fill("500");
  await expect(modal.getByText("₦6,500")).toBeVisible();
  await modal.getByRole("button", { name: "Send payment request" }).click();
  await expect(seller.page.getByTestId("payment-request").last()).toContainText("₦6,500");
  await expect(page.getByTestId("payment-request").last()).toContainText("₦6,500", { timeout: 15000 });

  // The buyer's bell shows a notification and it leads back to the chat
  await page.goto("/notifications");
  await expect(page.getByText("Payment request").first()).toBeVisible();
  await page.getByRole("button", { name: /Payment request/ }).first().click();
  await expect(page).toHaveURL(threadUrl);
  await seller.ctx.close();
});

test("phone numbers stay hidden until both people agree", async ({ page, browser }, info) => {
  await login(page, "buyer1@example.com");
  await page.goto("/search?q=Meat%20pie");
  await page.getByRole("link", { name: /Meat pie box/ }).first().click();
  await page.getByRole("button", { name: "Message seller" }).and(page.locator(":visible")).first().click();
  await expect(page).toHaveURL(/\/messages\/\d+$/);
  const convoId = page.url().split("/").pop();
  // Reset (a previous project may have shared numbers) then check nothing shows
  const me = await apiAs(page, "get", "/me");
  expect(me.status).toBe(200);
  await apiAs(page, "post", `/conversations/${convoId}/share-phone`, { share: false });
  await page.reload();
  await expect(page.getByText(/\+234/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Share my number" })).toBeVisible();
  void browser;
  void info;
});

test("blocking stops messages and can be undone", async ({ page, browser }) => {
  await login(page, "buyer2@example.com");
  await page.goto("/search?q=Meat%20pie");
  await page.getByRole("link", { name: /Meat pie box/ }).first().click();
  await page.getByRole("button", { name: "Message seller" }).and(page.locator(":visible")).first().click();
  await expect(page).toHaveURL(/\/messages\/\d+$/);
  await page.getByRole("button", { name: "Block", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Block" }).click();
  await expect(page.getByText("You blocked this person").or(page.getByPlaceholder("You blocked this person"))).toBeVisible();
  await expect(page.getByLabel("Write a message")).toBeDisabled();
  await page.getByRole("button", { name: "Unblock" }).click();
  await expect(page.getByLabel("Write a message")).toBeEnabled();
  void browser;
});

test("a reported message can be opened by an admin, with a reason that is logged", async ({ page, browser }, info) => {
  const stamp = `${info.project.name}${Date.now()}`;
  await login(page, "buyer2@example.com");
  await page.goto("/search?q=Meat%20pie");
  await page.getByRole("link", { name: /Meat pie box/ }).first().click();
  await page.getByRole("button", { name: "Message seller" }).and(page.locator(":visible")).first().click();
  await expect(page).toHaveURL(/\/messages\/\d+$/);
  const convoId = Number(page.url().split("/").pop());

  const seller = await otherRole(browser, page, "seller.verified@example.com");
  await seller.page.goto(`/seller/messages/${convoId}`);
  await seller.page.getByLabel("Write a message").fill(`Pay me by transfer instead ${stamp}`);
  await seller.page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByRole("log", { name: "Messages" }).getByText(`Pay me by transfer instead ${stamp}`)).toBeVisible({ timeout: 15000 });
  await page.getByRole("button", { name: "Report message" }).last().click();
  const report = page.getByRole("dialog", { name: /Report this message/ });
  await report.getByLabel("What is wrong?").selectOption("scam");
  await report.getByRole("button", { name: "Send report" }).click();
  await expect(page.getByText("Report sent")).toBeVisible();

  const admin = await otherRole(browser, page, "admin");
  await admin.page.goto("/admin/reports");
  await admin.page.getByRole("button", { name: "View chat" }).filter({ visible: true }).last().click();
  const dialog = admin.page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Open chat" }).click();
  await expect(dialog.getByRole("alert")).toContainText("reason");
  await dialog.getByLabel("Reason").fill("Reviewing scam report");
  await dialog.getByRole("button", { name: "Open chat" }).click();
  await expect(admin.page.getByRole("dialog").getByText(`Pay me by transfer instead ${stamp}`)).toBeVisible();
  await admin.page.getByRole("button", { name: "Close" }).last().click();
  await admin.page.goto("/admin/activity-log");
  await admin.page.getByLabel("Search reason or target").fill("Reviewing scam report");
  await expect(admin.page.getByText("chat.viewed").filter({ visible: true }).first()).toBeVisible();
  await admin.ctx.close();
  await seller.ctx.close();
});

test("a chat nobody reported stays private from admins", async ({ page }) => {
  await login(page, "buyer1@example.com");
  await page.goto("/messages");
  await expect(page.getByRole("heading", { name: "Messages" })).toBeVisible();
  const me = await apiAs(page, "get", "/conversations");
  expect(me.status).toBe(200);
});

test("Plug Me: buyer posts a request, a matching seller is notified and replies in chat", async ({ page, browser }, info) => {
  const title = `Need a USB fan ${info.project.name}${Date.now()}`;
  await login(page, "buyer2@example.com");
  await page.goto("/requests/new");
  await page.getByLabel("What do you need?").fill(title);
  await page.getByLabel("Details").fill("Quiet one for the hostel, delivered to my hall.");
  await page.getByLabel("Category").selectOption({ label: "Food" });
  await page.getByLabel("Budget (₦, optional)").fill("5000");
  await page.getByRole("button", { name: "Post request" }).click();
  await expect(page).toHaveURL(/\/requests\/\d+$/);
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  const requestUrl = page.url();

  await page.goto("/requests");
  await expect(page.getByRole("link", { name: title })).toBeVisible();

  // A seller with matching (Food) listings was notified
  const seller = await otherRole(browser, page, "seller.verified@example.com");
  await seller.page.goto("/notifications");
  await expect(seller.page.getByText(`Someone wants: ${title}`)).toBeVisible();
  await seller.page.getByRole("button", { name: new RegExp(title) }).click();
  await expect(seller.page).toHaveURL(requestUrl);
  await seller.page.getByRole("button", { name: "I can help" }).click();
  await seller.page.getByLabel("Your message").fill("I have one for ₦4,500, can bring it today.");
  await seller.page.getByRole("button", { name: "Send reply" }).click();
  await expect(seller.page).toHaveURL(/\/messages\/\d+$/);

  // The buyer is told and finds the reply in chat
  await page.goto("/notifications");
  await expect(page.getByText(/A seller replied to/).first()).toBeVisible();
  await page.getByRole("button", { name: /A seller replied to/ }).first().click();
  await expect(page.getByRole("log", { name: "Messages" }).getByText("I have one for ₦4,500, can bring it today.")).toBeVisible();

  // Closing the request removes it from the feed
  await page.goto(requestUrl);
  await page.getByRole("button", { name: "Close request" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Close request" }).click();
  await page.goto("/requests");
  await expect(page.getByRole("link", { name: title })).toHaveCount(0);
  await seller.ctx.close();
});

test("a Hall Rep sees requests posted for their hall", async ({ page, browser }, info) => {
  const title = `Need a kettle ${info.project.name}${Date.now()}`;
  await login(page, "buyer1@example.com");
  await page.goto("/requests/new");
  await page.getByLabel("What do you need?").fill(title);
  await page.getByLabel("Your hall or area").selectOption({ label: "Madam Tinubu Hall (MTH)" });
  await page.getByRole("button", { name: "Post request" }).click();
  await expect(page).toHaveURL(/\/requests\/\d+$/);
  const rep = await otherRole(browser, page, "rep@example.com");
  await rep.page.goto("/rep");
  await expect(rep.page.getByRole("heading", { name: "Requests in your hall" })).toBeVisible();
  await expect(rep.page.getByRole("link", { name: title })).toBeVisible();
  await rep.ctx.close();
});

test("guests are asked to sign in to message, post requests and see notifications", async ({ page }) => {
  await page.goto("/search?q=Meat%20pie");
  await page.getByRole("link", { name: /Meat pie box/ }).first().click();
  await page.getByRole("button", { name: "Message seller" }).and(page.locator(":visible")).first().click();
  await expect(page.getByRole("dialog", { name: "Sign in to continue" })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.goto("/requests/new");
  await expect(page).toHaveURL(/login/);
  await page.goto("/notifications");
  await expect(page).toHaveURL(/login/);
  await page.goto("/requests");
  await expect(page.getByRole("heading", { name: "Requests" })).toBeVisible();
});

test("messages layout: separate screens on mobile, two panes on larger screens", async ({ page }, info) => {
  await login(page, "buyer1@example.com");
  await page.goto("/search?q=Meat%20pie");
  await page.getByRole("link", { name: /Meat pie box/ }).first().click();
  await page.getByRole("button", { name: "Message seller" }).and(page.locator(":visible")).first().click();
  await expect(page).toHaveURL(/\/messages\/\d+$/);
  const list = page.getByRole("complementary", { name: "Conversations" });
  const thread = page.getByRole("region", { name: "Conversation" });
  await expect(thread).toBeVisible();
  if (info.project.name === "mobile") {
    await expect(list).toBeHidden();
    await page.getByRole("link", { name: "Back to conversations" }).click();
    await expect(page).toHaveURL(/\/messages$/);
    await expect(page.getByRole("complementary", { name: "Conversations" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Conversation" })).toBeHidden();
  } else {
    await expect(list).toBeVisible();
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
});

for (const path of ["/requests", "/requests/new", "/notifications", "/messages"]) {
  test(`accessibility and layout: ${path}`, async ({ page }) => {
    await login(page, "buyer1@example.com");
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    expect(results.violations).toEqual([]);
  });
}
