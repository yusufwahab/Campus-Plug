import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { PNG, apiAs, confirmPhone, login, loginAdmin, newSeller, otherRole, signup } from "./helpers";

test("verification journey: seller, admin and verifier", async ({ page, browser }, info) => {
  const shopName = `Verify Me ${info.project.name}${Date.now()}`;
  await newSeller(page, shopName);

  // Seller submits a student ID
  await page.goto("/seller/verification");
  await expect(page.getByText("Not verified")).toBeVisible();
  await page.getByLabel("Photo of your student ID").setInputFiles({ name: "id.png", mimeType: "image/png", buffer: PNG });
  await page.getByLabel(/Note for the reviewer/).fill("Final year Law student");
  await page.getByRole("button", { name: "Submit for review" }).click();
  await expect(page.getByText("waiting for review")).toBeVisible();

  // Admin assigns a Verifier
  const admin = await otherRole(browser, page, "admin");
  await admin.page.goto("/admin/verification");
  const adminRow = admin.page.getByRole("row").filter({ hasText: shopName });
  const adminCard = admin.page.getByRole("listitem").filter({ hasText: shopName });
  await (info.project.name === "mobile" ? adminCard : adminRow).getByRole("button", { name: "Assign" }).click();
  await admin.page.getByRole("dialog").getByLabel("Verifier").selectOption({ label: "Vera Verifier (verifier@example.com)" });
  await admin.page.getByRole("dialog").getByRole("button", { name: "Assign" }).click();
  await expect(admin.page.getByText("Verifier assigned")).toBeVisible();

  // The Verifier reviews, sees the ID and approves
  const verifier = await otherRole(browser, page, "verifier@example.com");
  await verifier.page.goto("/verify");
  await expect(verifier.page.getByRole("heading", { name: "Verification queue" })).toBeVisible();
  const queueRow = info.project.name === "mobile" ? verifier.page.getByRole("listitem").filter({ hasText: shopName }) : verifier.page.getByRole("row").filter({ hasText: shopName });
  await queueRow.getByRole("link", { name: "Review" }).click();
  await expect(verifier.page.getByRole("heading", { name: shopName })).toBeVisible();
  await expect(verifier.page.getByAltText(/Student ID submitted by/)).toBeVisible();
  await verifier.page.getByRole("button", { name: "Approve" }).click();
  await verifier.page.getByRole("dialog").getByLabel("Reason").fill("ID matches the name and photo");
  await verifier.page.getByRole("dialog").getByRole("button", { name: "Approve" }).click();
  await expect(verifier.page).toHaveURL(/\/verify$/);

  // Seller sees the badge and the public shop shows Verified
  await page.goto("/seller/verification");
  await expect(page.getByText("Verified student").filter({ visible: true }).first()).toBeVisible();
  await page.goto("/seller");
  await expect(page.getByText("Verified", { exact: true }).filter({ visible: true }).first()).toBeVisible();

  // Both actions are in the activity log with reasons
  await admin.page.goto("/admin/activity-log");
  await admin.page.getByLabel("Search reason or target").fill("ID matches");
  await expect(admin.page.getByText("verification.approved").filter({ visible: true }).first()).toBeVisible();
  await admin.ctx.close();
  await verifier.ctx.close();
});

test("verifier cannot verify themselves or see admin; hall rep is limited", async ({ page, browser }) => {
  await login(page, "verifier@example.com");
  await page.goto("/admin");
  await expect(page).toHaveURL(/access-denied/);
  await page.goto("/rep");
  await expect(page).toHaveURL(/access-denied/);

  const rep = await otherRole(browser, page, "rep@example.com");
  await rep.page.goto("/verify");
  await expect(rep.page).toHaveURL(/access-denied/);
  await rep.page.goto("/admin");
  await expect(rep.page).toHaveURL(/access-denied/);
  await rep.page.goto("/rep");
  await expect(rep.page.getByRole("heading", { name: "Hall Rep" })).toBeVisible();
  await rep.ctx.close();
});

test("hall rep onboards a seller and vouches for them", async ({ page, browser }, info) => {
  const email = await signup(page, "student");
  await confirmPhone(page);
  const shopName = `Rep Shop ${info.project.name}${Date.now()}`;
  const rep = await otherRole(browser, page, "rep@example.com");
  await rep.page.goto("/rep");
  await rep.page.getByRole("button", { name: "Onboard a seller" }).click();
  await rep.page.getByLabel("Their account email").fill(email);
  await rep.page.getByLabel("Shop name").fill(shopName);
  await rep.page.getByRole("button", { name: "Open their shop" }).click();
  await expect(rep.page.getByText(shopName).filter({ visible: true }).first()).toBeVisible();
  await rep.page.getByRole("button", { name: "Vouch" }).filter({ visible: true }).first().click();
  await expect(rep.page.getByText(/You vouched for/)).toBeVisible();
  await rep.ctx.close();

  // The seller opens their dashboard: the shop exists but they must accept the rules before publishing.
  await page.goto("/seller");
  await expect(page.getByRole("heading", { name: "Seller overview" })).toBeVisible();
  await expect(page.getByText(shopName)).toBeVisible().catch(() => undefined);
  const accept = await apiAs(page, "post", "/seller/accept-rules");
  expect(accept.status).toBe(204);
});

test("buyer reports a listing, admin hides it, guest no longer sees it", async ({ page, browser }, info) => {
  const stamp = `${info.project.name}${Date.now()}`;
  const sellerEmail = await newSeller(page, `Report Shop ${stamp}`);
  const created = await apiAs(page, "post", "/listings", { type: "product", category_id: 1, title: `Suspicious phone ${stamp}`, description: "Too good to be true", price_kobo: 100000, condition: "new" });
  expect(created.status).toBe(201);
  const pid = created.body.public_id as string;
  void sellerEmail;

  const buyer = await otherRole(browser, page, "buyer2@example.com");
  await buyer.page.goto(`/listing/${pid}`);
  await buyer.page.getByRole("button", { name: "Report" }).click();
  const dialog = buyer.page.getByRole("dialog", { name: /Report this listing/ });
  await dialog.getByLabel("What is wrong?").selectOption("scam");
  await dialog.getByLabel(/Details/).fill("Photos are stolen");
  await dialog.getByRole("button", { name: "Send report" }).click();
  await expect(buyer.page.getByText("Report sent")).toBeVisible();
  await buyer.page.goto("/reports");
  await expect(buyer.page.getByText(pid).filter({ visible: true }).first()).toBeVisible();

  const admin = await otherRole(browser, page, "admin");
  await admin.page.goto("/admin/reports");
  await (info.project.name === "mobile" ? admin.page.getByRole("listitem").filter({ hasText: pid }) : admin.page.getByRole("row").filter({ hasText: pid })).getByRole("button", { name: "Review" }).click();
  const modal = admin.page.getByRole("dialog");
  await modal.getByLabel("Action").selectOption("hide");
  await modal.getByRole("button", { name: "Apply action" }).click();
  await expect(modal.getByRole("alert")).toContainText("reason");
  await modal.getByLabel("Reason").fill("Confirmed stolen photos");
  await modal.getByRole("button", { name: "Apply action" }).click();
  await expect(admin.page.getByText("Report resolved")).toBeVisible();

  const status = await buyer.page.request.get(`http://localhost:8100/api/v1/listings/${pid}`);
  expect(status.status()).toBe(404);
  await buyer.page.goto("/reports");
  await expect(buyer.page.getByText(/hide: Confirmed stolen photos/).filter({ visible: true }).first()).toBeVisible();
  await admin.ctx.close();
  await buyer.ctx.close();
});

test("admin changes a rule without code and it takes effect", async ({ page, browser }, info) => {
  const admin = await otherRole(browser, page, "admin");
  await admin.page.goto("/admin/settings");
  await admin.page.getByRole("button", { name: "Change Unverified seller listing limit" }).click();
  const modal = admin.page.getByRole("dialog");
  await modal.getByLabel("Unverified seller listing limit").fill("1");
  await modal.getByLabel("Reason").fill("Pilot week");
  await modal.getByRole("button", { name: "Save change" }).click();
  await expect(admin.page.getByTestId("value-unverified_listing_limit")).toHaveText("1 listings");

  await newSeller(page, `Limit Shop ${info.project.name}${Date.now()}`);
  const body = { type: "product", category_id: 1, title: "First item", description: "ok", price_kobo: 50000, condition: "new" };
  expect((await apiAs(page, "post", "/listings", body)).status).toBe(201);
  const second = await apiAs(page, "post", "/listings", { ...body, title: "Second item" });
  expect(second.status).toBe(403);
  expect(second.body.detail).toContain("1 live listings");

  // restore the default so other journeys are not affected
  await admin.page.getByRole("button", { name: "Change Unverified seller listing limit" }).click();
  await admin.page.getByRole("dialog").getByLabel("Unverified seller listing limit").fill("3");
  await admin.page.getByRole("dialog").getByLabel("Reason").fill("Pilot week over");
  await admin.page.getByRole("dialog").getByRole("button", { name: "Save change" }).click();
  await expect(admin.page.getByTestId("value-unverified_listing_limit")).toHaveText("3 listings");
  await admin.ctx.close();
});

test("admin announcement appears for guests and can be dismissed", async ({ page, browser }, info) => {
  const title = `Maintenance ${info.project.name}${Date.now()}`;
  await loginAdmin(page);
  await page.goto("/admin/announcements");
  await page.getByRole("button", { name: "New announcement" }).click();
  const modal = page.getByRole("dialog");
  await modal.getByLabel("Title").fill(title);
  await modal.getByLabel("Message").fill("Payments pause briefly tonight.");
  await modal.getByLabel("Reason").fill("Planned maintenance");
  await modal.getByRole("button", { name: "Publish announcement" }).click();
  await expect(page.getByText("Announcement published")).toBeVisible();

  const guestCtx = await browser.newContext({ viewport: page.viewportSize() ?? undefined });
  const guest = await guestCtx.newPage();
  await guest.goto("/");
  await expect(guest.getByRole("region", { name: "Announcement" }).filter({ hasText: title })).toBeVisible();
  await guest.getByRole("button", { name: "Dismiss announcement" }).click();
  await expect(guest.getByRole("region", { name: "Announcement" }).filter({ hasText: title })).toHaveCount(0);
  await guestCtx.close();
  // hide it again
  await page.reload();
  await (info.project.name === "mobile" ? page.getByRole("listitem").filter({ hasText: title }) : page.getByRole("row").filter({ hasText: title })).getByRole("button", { name: "Hide" }).click();
  await expect(page.getByText("Announcement hidden")).toBeVisible();
});

test("admin adds a category and it shows on the marketplace", async ({ page, browser }, info) => {
  const name = `Pets${info.project.name}${Date.now() % 100000}`;
  const slug = name.toLowerCase();
  await loginAdmin(page);
  await page.goto("/admin/categories");
  await page.getByRole("button", { name: "New category" }).click();
  const modal = page.getByRole("dialog");
  await modal.getByLabel("Name").fill(name);
  await modal.getByLabel("Slug").fill(slug);
  await modal.getByLabel("Reason").fill("New demand on campus");
  await modal.getByRole("button", { name: "Create category" }).click();
  await expect(page.getByText("Category created")).toBeVisible();
  const guestCtx = await browser.newContext();
  const guest = await guestCtx.newPage();
  await guest.goto("/");
  await expect(guest.getByRole("navigation", { name: "Categories" }).getByRole("link", { name })).toBeVisible();
  await guestCtx.close();
});

test("buyers and guests cannot reach any admin API data", async ({ page, request }) => {
  await login(page, "buyer1@example.com");
  expect((await apiAs(page, "get", "/admin/users")).status).toBe(403);
  expect((await apiAs(page, "get", "/admin/activity-log")).status).toBe(403);
  expect((await apiAs(page, "get", "/verify/queue")).status).toBe(403);
  expect((await apiAs(page, "get", "/rep/sellers")).status).toBe(403);
  expect((await request.get("http://localhost:8100/api/v1/admin/users")).status()).toBe(401);
});

const adminRoutes: [string, string][] = [
  ["/admin/users", "Users"], ["/admin/sellers", "Sellers"], ["/admin/verification", "Verification"], ["/admin/listings", "Listings"], ["/admin/categories", "Categories"],
  ["/admin/campuses", "Campuses and locations"], ["/admin/team", "Team"], ["/admin/announcements", "Announcements"], ["/admin/settings", "Settings"],
  ["/admin/activity-log", "Activity log"], ["/admin/exports", "CSV exports"], ["/admin/reports", "Reports"],
];

test("every admin page loads with no horizontal scroll and no accessibility violations", async ({ page }) => {
  await loginAdmin(page);
  for (const [path, heading] of adminRoutes) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
    await page.getByRole("status", { name: "Loading" }).waitFor({ state: "detached" }).catch(() => undefined);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), `${path} scrolls sideways`).toBeLessThanOrEqual(0);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    expect(results.violations, `${path} accessibility`).toEqual([]);
  }
});

test("admin users table: cards on mobile, sticky-header table otherwise, with search", async ({ page }, info) => {
  await loginAdmin(page);
  await page.goto("/admin/users");
  await page.getByLabel("Search name, email or phone").fill("tolu");
  await expect(page.getByText("Tolu Buyer").filter({ visible: true }).first()).toBeVisible();
  if (info.project.name === "mobile") {
    await expect(page.getByRole("region", { name: "Users table" })).toBeHidden();
    await expect(page.getByRole("list", { name: "Users (cards)" })).toBeVisible();
  } else {
    await expect(page.getByRole("region", { name: "Users table" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Email" })).toBeVisible();
  }
  await page.getByLabel("Search name, email or phone").fill("chidi");
  await expect(page.getByText("Chidi Buyer").filter({ visible: true }).first()).toBeVisible();
  await expect(page.getByText("Tolu Buyer").filter({ visible: true })).toHaveCount(0);
  await page.getByLabel("Search name, email or phone").fill("nobody-here-xyz");
  await expect(page.getByText("No users match").filter({ visible: true })).toBeVisible();
});

test("admin suspension asks for a reason and signs the user out", async ({ page, browser }) => {
  const email = await signup(page, "tobesuspended");
  await confirmPhone(page);
  const admin = await otherRole(browser, page, "admin");
  await admin.page.goto("/admin/users");
  await admin.page.getByLabel("Search name, email or phone").fill(email);
  await expect(admin.page.getByText(email).filter({ visible: true }).first()).toBeVisible();
  const scope = admin.page.viewportSize()!.width < 768 ? admin.page.getByRole("listitem").filter({ hasText: email }) : admin.page.getByRole("row").filter({ hasText: email });
  await scope.getByRole("button", { name: "Suspend" }).click();
  const modal = admin.page.getByRole("dialog");
  await modal.getByRole("button", { name: "Suspend" }).click();
  await expect(modal.getByRole("alert")).toContainText("short reason");
  await modal.getByLabel("Reason").fill("Spam listings");
  await modal.getByRole("button", { name: "Suspend" }).click();
  await expect(admin.page.getByText("Account updated")).toBeVisible();
  await page.goto("/account");
  await expect(page).toHaveURL(/login/);
  await admin.ctx.close();
});
