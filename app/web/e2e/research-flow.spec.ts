import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("ai4s_onboarding_done", "1");
  });
});

test("课题新建与任务看板", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("AI4S 科研助手")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("tab", { name: "课题" }).click();
  await page.getByRole("button", { name: "+ 新建" }).click();
  await page.getByPlaceholder("课题名称（必填）").fill("E2E 测试课题");
  await page.getByRole("button", { name: "创建课题" }).click();

  await page.getByRole("tab", { name: "任务" }).click();
  await page.getByRole("button", { name: "+ 任务" }).click();
  await page.getByPlaceholder("任务标题（必填）").fill("E2E 测试任务");
  await page.getByRole("button", { name: "添加任务" }).click();

  await expect(page.getByText("E2E 测试任务")).toBeVisible();
});

test("导出 DOCX 下载", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "科研工作台", exact: true })).toBeVisible({
    timeout: 30_000,
  });

  const sessionId = await page.evaluate(() => localStorage.getItem("ai4s_session_id"));
  expect(sessionId).toBeTruthy();
  await page.request.post("/v1/memory/structured", {
    data: {
      session_id: sessionId,
      kind: "note",
      title: "E2E 导出条目",
      body: "用于 Playwright 导出测试。",
    },
  });

  await page.getByRole("tab", { name: "产出" }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 Word (.docx)" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.docx$/i);
});

test("文献 arXiv 导入入口可见", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("tab", { name: "文献" }).click();
  await expect(page.getByPlaceholder("arXiv ID（如 2301.00001）")).toBeVisible();
  await expect(page.getByRole("button", { name: "PDF / Word" })).toBeVisible();
});
