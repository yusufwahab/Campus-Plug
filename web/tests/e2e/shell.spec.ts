import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const noHorizontalScroll = async (page: import("@playwright/test").Page) => {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
};

for (const path of ["/", "/design", "/seller", "/admin", "/offline", "/access-denied", "/does-not-exist"]) {
  test(`no horizontal scroll: ${path}`, async ({ page }) => {
    await page.goto(path);
    await noHorizontalScroll(page);
  });
}

test("public navigation adapts to the viewport", async ({ page }, info) => {
  await page.goto("/");
  const bottom = page.getByRole("navigation", { name: "Mobile" });
  const main = page.getByRole("navigation", { name: "Main" });
  if (info.project.name === "mobile") {
    await expect(bottom).toBeVisible();
    await expect(main).toBeHidden();
    await expect(bottom.getByRole("link")).toHaveCount(5);
  } else {
    await expect(bottom).toBeHidden();
    await expect(main).toBeVisible();
    await expect(main.getByRole("link", { name: "Requests" })).toBeVisible();
  }
});

test("seller dashboard: bottom bar on mobile, rail/sidebar otherwise", async ({ page }, info) => {
  await page.goto("/seller");
  if (info.project.name === "mobile") {
    await expect(page.getByRole("navigation", { name: "Seller mobile" })).toBeVisible();
    await page.getByRole("button", { name: "More" }).click();
    await expect(page.getByRole("dialog").getByRole("link", { name: "Shop Settings" })).toBeVisible();
  } else {
    await expect(page.getByRole("navigation", { name: "Seller navigation" }).filter({ visible: true }).getByRole("link", { name: "Back to Marketplace" })).toBeVisible();
  }
});

test("modal closes with Escape and the close button, and returns focus", async ({ page }) => {
  await page.goto("/design");
  const opener = page.getByRole("button", { name: "Open modal" });
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "Example modal" });
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(opener).toBeFocused();
  await opener.click();
  await dialog.getByRole("button", { name: "Close" }).click();
  await expect(dialog).toBeHidden();
});

test("modal protects unsaved data", async ({ page }) => {
  await page.goto("/design");
  await page.getByRole("button", { name: "Open modal" }).click();
  const dialog = page.getByRole("dialog", { name: "Example modal" });
  await dialog.getByLabel("Note").fill("draft");
  await page.keyboard.press("Escape");
  await expect(dialog.getByText("Discard your changes?")).toBeVisible();
  await dialog.getByRole("button", { name: "Keep editing" }).click();
  await expect(dialog.getByLabel("Note")).toHaveValue("draft");
});

for (const path of ["/", "/design", "/offline", "/access-denied"]) {
  test(`accessibility: ${path}`, async ({ page }) => {
    await page.goto(path);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    expect(results.violations).toEqual([]);
  });
}

test("manifest is served", async ({ request }) => {
  const res = await request.get("/manifest.webmanifest");
  expect(res.ok()).toBeTruthy();
  const json = await res.json();
  expect(json.display).toBe("standalone");
  expect(json.icons.length).toBeGreaterThanOrEqual(3);
});
