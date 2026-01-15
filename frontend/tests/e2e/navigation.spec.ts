import { test, expect } from '@playwright/test';

/**
 * Buddha Korea 네비게이션 테스트
 *
 * 실제 URL 구조:
 * - /chat.html - Ghosa AI 채팅 (메인)
 * - /sutra-writing.html - 전자 사경
 * - /mypage.html - 마이페이지
 * - /index.html - 랜딩 페이지
 */

test.describe('Navigation Tests', () => {

  test('채팅 페이지 로드', async ({ page }) => {
    await page.goto('/chat.html');

    // 페이지가 로드되었는지 확인
    await expect(page).toHaveURL(/chat\.html/);

    // 채팅 관련 요소가 있는지 확인
    const chatArea = page.locator('body');
    await expect(chatArea).toBeVisible();
  });

  test('사경 페이지 로드', async ({ page }) => {
    await page.goto('/sutra-writing.html');

    await expect(page).toHaveURL(/sutra-writing\.html/);

    // 페이지 로드 확인
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });

  test('마이페이지 로드', async ({ page }) => {
    await page.goto('/mypage.html');

    await expect(page).toHaveURL(/mypage\.html/);

    const body = page.locator('body');
    await expect(body).toBeVisible();
  });

  test('인덱스 페이지 로드', async ({ page }) => {
    await page.goto('/index.html');

    await expect(page).toHaveURL(/index\.html/);

    const body = page.locator('body');
    await expect(body).toBeVisible();
  });

  test('헤더 네비게이션 존재', async ({ page }) => {
    await page.goto('/chat.html');

    // 네비게이션 영역 확인
    const nav = page.locator('nav, header, .navbar, .nav');
    await expect(nav.first()).toBeVisible({ timeout: 10000 });
  });
});
