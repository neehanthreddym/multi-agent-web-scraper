import { expect, test } from "@playwright/test";

test("create a job, reload the UI, and inspect persisted source evidence", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Create a job" })).toBeVisible();
  await expect(page.getByLabel("Catalog preset").locator("option")).toHaveCount(10);
  const response = page.waitForResponse((result) => result.url().endsWith("/api/jobs") && result.request().method() === "POST");
  await page.getByRole("button", { name: "Create job", exact: true }).click();
  const created = await response;
  expect(created.status()).toBe(202);
  const job = await created.json();
  await expect(page.getByTestId("selected-job-id")).toHaveText(job.id);
  await expect.poll(() => page.evaluate(() => localStorage.getItem("catalog-selected-job"))).toBe(job.id);
  await page.reload();
  await expect(page.getByTestId("selected-job-id")).toHaveText(job.id);
  await expect(page.getByTestId("job-progress")).toHaveText("Extraction completed. Results saved.");
  const results = page.getByRole("region", { name: "Saved results" });
  await expect(results.getByRole("cell", { name: "Studio Desk Lamp", exact: true })).toBeVisible();
  await expect(results.getByRole("cell", { name: "49.90", exact: true })).toBeVisible();
  await results.getByRole("button", { name: "Inspect evidence" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Field", { exact: true }).selectOption("product_name");
  await expect(dialog.getByTestId("evidence-value")).toHaveText("Studio Desk Lamp");
  await dialog.getByLabel("Field", { exact: true }).selectOption("current_price");
  await expect(dialog.getByTestId("evidence-value")).toHaveText("49.90");
  await dialog.getByText("Saved page (text)", { exact: true }).click();
  await expect(dialog.getByTestId("snapshot-text")).toContainText('<script type="application/ld+json">');
  expect(await page.locator('script[type="application/ld+json"]').count()).toBe(0);
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(results.getByRole("button", { name: "Inspect evidence" })).toBeFocused();
});

for (const example of [
  { preset: "graph-monitor", name: "Focus Monitor", field: "availability", value: "out_of_stock", reason: null },
  { preset: "ambiguous-currency-mug", name: "Travel Mug", field: "currency", value: "Unavailable", reason: "unsupported value" },
  { preset: "missing-offer-shelf", name: "Wall Shelf", field: "current_price", value: "Unavailable", reason: "missing offer" },
]) {
  test(`selected fixture ${example.preset} retains results and field evidence`, async ({ page }) => {
    await page.goto("/");
    const presets = page.getByLabel("Catalog preset");
    await expect(presets.locator("option")).toHaveCount(10);
    await presets.selectOption(example.preset);
    const submitted = page.waitForResponse((response) => response.url().endsWith("/api/jobs") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Create job", exact: true }).click();
    const response = await submitted;
    expect(response.status()).toBe(202);
    const job = await response.json();
    expect(job.configuration.seed_url).toBe(`http://fixture:8080/products/${example.preset}.html`);
    await expect(page.getByTestId("selected-job-id")).toHaveText(job.id);
    await expect(page.getByTestId("job-progress")).toHaveText("Extraction completed. Results saved.");
    await page.reload();
    await expect(page.getByTestId("selected-job-id")).toHaveText(job.id);
    const results = page.getByRole("region", { name: "Saved results" });
    await expect(results.getByRole("cell", { name: example.name, exact: true })).toBeVisible();
    await results.getByRole("button", { name: "Inspect evidence" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Field", { exact: true }).selectOption(example.field);
    await expect(dialog.getByTestId("evidence-value")).toHaveText(example.value);
    if (example.reason) await expect(dialog.getByText(`Reason: ${example.reason}`, { exact: true })).toBeVisible();
    if (example.preset === "missing-offer-shelf") await expect(dialog.getByText(/Missing source key: offers/)).toBeVisible();
    await dialog.getByText("Saved page (text)", { exact: true }).click();
    await expect(dialog.getByTestId("snapshot-text")).toContainText(example.name);
    await page.keyboard.press("Escape");
    await expect(results.getByRole("button", { name: "Inspect evidence" })).toBeFocused();
  });
}
