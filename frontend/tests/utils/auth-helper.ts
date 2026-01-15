import { Page, expect } from '@playwright/test';

/**
 * 인증 관련 헬퍼 함수들
 */

/**
 * 로그인 모달이 열리는지 확인
 */
export async function openLoginModal(page: Page): Promise<void> {
  // 로그인 버튼 클릭
  await page.click('button:has-text("로그인"), a:has-text("로그인")');

  // 모달이 열릴 때까지 대기
  await expect(page.locator('.login-modal, #login-modal, [data-modal="login"]')).toBeVisible({
    timeout: 5000,
  });
}

/**
 * 로그인 모달 닫기
 */
export async function closeLoginModal(page: Page): Promise<void> {
  // ESC 키 또는 닫기 버튼
  await page.keyboard.press('Escape');

  // 모달이 닫힐 때까지 대기
  await expect(page.locator('.login-modal, #login-modal')).not.toBeVisible({
    timeout: 3000,
  });
}

/**
 * 로그인 상태 확인
 */
export async function isLoggedIn(page: Page): Promise<boolean> {
  // 로그인된 상태의 UI 요소 확인
  const userMenu = page.locator('.user-menu, .user-profile, [data-testid="user-menu"]');
  const logoutBtn = page.locator('button:has-text("로그아웃"), a:has-text("로그아웃")');

  return (await userMenu.isVisible()) || (await logoutBtn.isVisible());
}

/**
 * 로그아웃 상태 확인
 */
export async function isLoggedOut(page: Page): Promise<boolean> {
  const loginBtn = page.locator('button:has-text("로그인"), a:has-text("로그인")');
  return await loginBtn.isVisible();
}

/**
 * 로그아웃 실행
 */
export async function logout(page: Page): Promise<void> {
  const logoutBtn = page.locator('button:has-text("로그아웃"), a:has-text("로그아웃")');

  if (await logoutBtn.isVisible()) {
    await logoutBtn.click();
    // 로그인 버튼이 다시 나타날 때까지 대기
    await expect(
      page.locator('button:has-text("로그인"), a:has-text("로그인")')
    ).toBeVisible({ timeout: 5000 });
  }
}

/**
 * OAuth 로그인 버튼 클릭 (리다이렉트 URL 확인)
 */
export async function clickOAuthLogin(
  page: Page,
  provider: 'google' | 'naver' | 'kakao'
): Promise<string> {
  const selectors: Record<string, string> = {
    google: '[data-provider="google"], .google-login, button:has-text("Google")',
    naver: '[data-provider="naver"], .naver-login, button:has-text("네이버")',
    kakao: '[data-provider="kakao"], .kakao-login, button:has-text("카카오")',
  };

  // 클릭하고 새 페이지/리다이렉트 대기
  const [response] = await Promise.all([
    page.waitForResponse((res) => res.url().includes('oauth') || res.url().includes('login')),
    page.click(selectors[provider]),
  ]);

  return response.url();
}

/**
 * 비로그인 시 보호된 페이지 접근 테스트
 */
export async function testProtectedPageAccess(page: Page, url: string): Promise<boolean> {
  await page.goto(url);

  // 로그인 프롬프트가 나타나는지 확인
  const loginPrompt = page.locator(
    '.login-required, .auth-required, [data-auth="required"]'
  );
  const loginModal = page.locator('.login-modal, #login-modal');

  return (await loginPrompt.isVisible()) || (await loginModal.isVisible());
}
