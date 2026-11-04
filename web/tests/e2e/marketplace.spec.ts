import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { PNG, login, newSeller } from "./helpers";

test("seller publishes a listing and a guest finds it with correct metadata", async ({ page, browser }, info) => {
  const stamp = `${info.project.name}${Date.now()}`;
  const shopName = `Bake House ${stamp}`;
  const title = `Zobo drink ${stamp}`;
  await newSeller(page, shopName);

  await expect(page.getByRole("heading", { name: "Seller overview" })).toBeVisible();
  await expect(page.getByText("Add your first listing")).toBeVisible();

  await page.goto("/seller/listings/new");
  await page.getByLabel("Title").fill(title);
  await page.getByLabel("Category").selectOption({ label: "Food" });
  await page.getByLabel("Description").fill("Chilled hibiscus drink. Pickup at the hall.");
  await page.getByLabel("Price (₦)", { exact: true }).fill("1500");
  await expect(page.getByText("You receive")).toBeVisible();
  await expect(page.getByText("₦1,200")).toBeVisible(); // 20% commission on ₦1,500
  await page.locator('input[type="file"]').setInputFiles({ name: "zobo.png", mimeType: "image/png", buffer: PNG });
  await expect(page.getByAltText("New photo 1")).toBeVisible();
  await page.getByRole("button", { name: "Publish" }).click();
  await expect(page).toHaveURL(/\/seller\/listings$/);
  await expect(page.getByText(title)).toBeVisible();
  const href = await page.getByRole("link", { name: title }).getAttribute("href");
  expect(href).toMatch(/^\/listing\/CP-P-\d+$/);

  // A guest in a fresh browser context has no session.
  const guestCtx = await browser.newContext({ viewport: page.viewportSize() ?? undefined });
  const guest = await guestCtx.newPage();
  await guest.goto(`/search?q=${encodeURIComponent(stamp)}`);
  await expect(guest.getByRole("link", { name: new RegExp(title) }).first()).toBeVisible();
  await guest.getByRole("link", { name: new RegExp(title) }).first().click();
  await expect(guest.getByRole("heading", { name: title })).toBeVisible();
  await expect(guest.getByText(shopName).first()).toBeVisible();
  await expect(guest.getByText("₦1,500").first()).toBeVisible();

  // Server-rendered metadata for WhatsApp previews and search engines.
  const meta = (name: string, attr = "property") => guest.locator(`meta[${attr}="${name}"]`).getAttribute("content");
  await expect(guest).toHaveTitle(new RegExp(`${title}.*₦1,500`));
  expect(await meta("og:title")).toContain(title);
  expect(await meta("og:image")).toMatch(/uploads\/.+\.jpg$/);
  expect(await meta("og:description")).toContain(shopName);
  const ld = JSON.parse((await guest.locator('script[type="application/ld+json"]').innerText()) as string);
  expect(ld.offers.price).toBe("1500.00");
  expect(ld.offers.priceCurrency).toBe("NGN");

  // The same metadata is in the raw HTML (not added by client JavaScript).
  const raw = await (await guest.request.get(guest.url())).text();
  expect(raw).toContain(`og:title`);
  expect(raw).toContain(title);

  await guest.getByRole("link", { name: shopName }).first().click();
  await expect(guest.getByRole("heading", { name: shopName })).toBeVisible();
  await expect(guest.getByRole("link", { name: new RegExp(title) })).toBeVisible();
  await guestCtx.close();
});

test("guest must sign in to save and is taken to login", async ({ page }) => {
  await page.goto("/search?q=jollof");
  await page.getByRole("link", { name: /Jollof rice/ }).first().click();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("dialog", { name: "Sign in to continue" })).toBeVisible();
  await page.getByRole("dialog").getByRole("link", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/login\?next=/);
});

test("signed-in buyer saves and sees the item under Saved", async ({ page }) => {
  await login(page, "buyer1@example.com");
  await page.goto("/search?q=Meat%20pie");
  await page.getByRole("link", { name: /Meat pie box/ }).first().click();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("button", { name: "Saved" })).toBeVisible();
  await page.goto("/saved");
  await expect(page.getByRole("link", { name: /Meat pie box/ })).toBeVisible();
  await page.goto("/search?q=Meat%20pie");
  await page.getByRole("link", { name: /Meat pie box/ }).first().click();
  await page.getByRole("button", { name: "Saved" }).click();
  await expect(page.getByRole("button", { name: "Save", exact: true })).toBeVisible();
});

test("home shows every category and listing sections", async ({ page }) => {
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Categories" });
  for (const name of ["Food", "Fashion", "Beauty", "Gadgets", "Services", "Accessories", "Academic", "Others"]) {
    await expect(nav.getByRole("link", { name })).toBeVisible();
  }
  await expect(page.getByRole("heading", { name: "New listings" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Popular" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Near you" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Plug Me/ })).toBeVisible();
  await nav.getByRole("link", { name: "Gadgets" }).click();
  await expect(page).toHaveURL(/categories\/gadgets/);
  await expect(page.getByRole("link", { name: /Redmi Note 11/ })).toBeVisible();
});

test("location selector sets the hall and Near you uses it", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /UNILAG|All of campus/ }).first().click();
  await page.getByRole("dialog").getByRole("button", { name: "Madam Tinubu Hall (MTH)" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  const nearYou = page.getByRole("region").filter({ has: page.getByRole("heading", { name: "Near you" }) });
  await expect(nearYou.getByRole("link").first()).toBeVisible();
});

test("search filters narrow results and empty search offers Ask campus", async ({ page }) => {
  await page.goto("/search");
  await expect(page.getByRole("heading", { name: "Browse everything" })).toBeVisible();
  await page.goto("/search?category=services&type=service");
  await expect(page.getByRole("link", { name: /Laundry and ironing/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Jollof rice/ })).toHaveCount(0);
  await page.goto("/search?q=zzzxqwvv");
  await expect(page.getByRole("link", { name: "Ask campus for this" })).toBeVisible();
});

test("filters modal works on small screens", async ({ page }, info) => {
  test.skip(info.project.name === "desktop", "Filters are a sidebar on desktop");
  await page.goto("/search");
  await page.getByRole("button", { name: /^Filters/ }).click();
  const dialog = page.getByRole("dialog", { name: "Filters" });
  await dialog.getByLabel("Type").selectOption("service");
  await dialog.getByRole("button", { name: "Apply filters" }).click();
  await expect(page).toHaveURL(/type=service/);
  await expect(page.getByRole("link", { name: /Hair braiding/ })).toBeVisible();
});

test("static pages render and contact form submits", async ({ page }) => {
  for (const [path, heading] of [["/how-it-works", "How Campus Plug works"], ["/sell", "Sell on Campus Plug"], ["/help", "Help centre"], ["/terms", "Terms of use"], ["/privacy", "Privacy policy"], ["/seller-rules", "Seller rules"]] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
  }
  await page.goto("/contact");
  await page.getByLabel("Your name").fill("Ada Obi");
  await page.getByLabel("Email").fill("ada@example.com");
  await page.getByRole("textbox", { name: "Message" }).fill("My order has not arrived yet, please help.");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByRole("status").filter({ hasText: "message is with our team" })).toBeVisible();
});

test("sitemap and robots are served", async ({ request }) => {
  const sitemap = await (await request.get("/sitemap.xml")).text();
  expect(sitemap).toContain("/listing/CP-");
  expect(sitemap).toContain("/categories/food");
  expect(await (await request.get("/robots.txt")).text()).toContain("Disallow: /admin");
});

test("shop share dialog copies a link", async ({ page }) => {
  await page.goto("/shop/kemis-corner");
  await page.getByRole("button", { name: "Share shop" }).click();
  await expect(page.getByTestId("share-url")).toContainText("/shop/kemis-corner");
  await expect(page.getByRole("link", { name: "Share on WhatsApp" })).toHaveAttribute("href", /wa\.me/);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
});

for (const path of ["/", "/search", "/shop/kemis-corner", "/categories/food", "/help", "/contact"]) {
  test(`accessibility: ${path}`, async ({ page }) => {
    await page.goto(path);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    expect(results.violations).toEqual([]);
  });
}

test("accessibility: listing page and seller listing form", async ({ page }) => {
  await page.goto("/search?q=Jollof");
  await page.getByRole("link", { name: /Jollof rice/ }).first().click();
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
  await login(page, "seller.verified@example.com", "/seller/listings/new");
  await expect(page.getByRole("heading", { name: "New listing" })).toBeVisible();
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
});

test("no horizontal scroll on marketplace pages", async ({ page }) => {
  for (const path of ["/", "/search", "/categories/food", "/shop/kemis-corner", "/help"]) {
    await page.goto(path);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  }
  await page.goto("/search?q=Jollof");
  await page.getByRole("link", { name: /Jollof rice/ }).first().click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
});
