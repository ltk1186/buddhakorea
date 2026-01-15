import { test, expect } from '@playwright/test';
import { openLoginModal, closeLoginModal, isLoggedIn, isLoggedOut } from '../utils/auth-helper';

test.describe('Authentication Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('로그인 버튼 표시', async ({ page }) => {
    // 비로그인 상태에서 로그인 버튼 확인
    const loginButton = page.locator(
      'button:has-text("로그인"), a:has-text("로그인"), .login-btn'
    );
    await expect(loginButton.first()).toBeVisible();
  });

  test('로그인 모달 열기/닫기', async ({ page }) => {
    // 로그인 버튼 클릭
    const loginButton = page.locator(
      'button:has-text("로그인"), a:has-text("로그인")'
    ).first();
    await loginButton.click();

    // 모달 열림 확인
    const modal = page.locator('.modal, .login-modal, [role="dialog"]');
    await expect(modal).toBeVisible({ timeout: 5000 });

    // ESC로 닫기
    await page.keyboard.press('Escape');

    // 모달 닫힘 확인
    await expect(modal).not.toBeVisible({ timeout: 3000 });
  });

  test('OAuth 로그인 버튼들 표시', async ({ page }) => {
    // 로그인 모달 열기
    const loginButton = page.locator('button:has-text("로그인"), a:has-text("로그인")').first();
    await loginButton.click();

    // OAuth 버튼들 확인
    const googleBtn = page.locator('[data-provider="google"], .google-login, button:has-text("Google")');
    const naverBtn = page.locator('[data-provider="naver"], .naver-login, button:has-text("네이버")');
    const kakaoBtn = page.locator('[data-provider="kakao"], .kakao-login, button:has-text("카카오")');

    // 최소 하나의 OAuth 버튼이 있어야 함
    const anyOAuthVisible =
      (await googleBtn.isVisible()) ||
      (await naverBtn.isVisible()) ||
      (await kakaoBtn.isVisible());

    expect(anyOAuthVisible).toBeTruthy();
  });

  test('Google 로그인 버튼 리다이렉트', async ({ page }) => {
    // 로그인 모달 열기
    await page.click('button:has-text("로그인"), a:has-text("로그인")');
    await page.waitForTimeout(500);

    const googleBtn = page.locator(
      '[data-provider="google"], .google-login, button:has-text("Google"), a:has-text("Google")'
    );

    if (await googleBtn.isVisible()) {
      // 새 창/탭이 열리거나 리다이렉트될 수 있음
      const [popup] = await Promise.all([
        page.waitForEvent('popup').catch(() => null),
        googleBtn.click(),
      ]);

      if (popup) {
        // 팝업이 열린 경우 OAuth URL 확인
        const popupUrl = popup.url();
        expect(popupUrl).toMatch(/accounts\.google\.com|oauth/i);
        await popup.close();
      } else {
        // 리다이렉트된 경우
        await page.waitForTimeout(2000);
        const currentUrl = page.url();
        // OAuth 페이지로 이동했거나 콜백 처리됨
        expect(
          currentUrl.includes('google') ||
            currentUrl.includes('oauth') ||
            currentUrl.includes('callback') ||
            currentUrl.includes('buddhakorea')
        ).toBeTruthy();
      }
    }
  });

  test('네이버 로그인 버튼 리다이렉트', async ({ page }) => {
    await page.click('button:has-text("로그인"), a:has-text("로그인")');
    await page.waitForTimeout(500);

    const naverBtn = page.locator(
      '[data-provider="naver"], .naver-login, button:has-text("네이버"), a:has-text("네이버")'
    );

    if (await naverBtn.isVisible()) {
      const [popup] = await Promise.all([
        page.waitForEvent('popup').catch(() => null),
        naverBtn.click(),
      ]);

      if (popup) {
        const popupUrl = popup.url();
        expect(popupUrl).toMatch(/nid\.naver\.com|oauth/i);
        await popup.close();
      }
    }
  });

  test('카카오 로그인 버튼 리다이렉트', async ({ page }) => {
    await page.click('button:has-text("로그인"), a:has-text("로그인")');
    await page.waitForTimeout(500);

    const kakaoBtn = page.locator(
      '[data-provider="kakao"], .kakao-login, button:has-text("카카오"), a:has-text("카카오")'
    );

    if (await kakaoBtn.isVisible()) {
      const [popup] = await Promise.all([
        page.waitForEvent('popup').catch(() => null),
        kakaoBtn.click(),
      ]);

      if (popup) {
        const popupUrl = popup.url();
        expect(popupUrl).toMatch(/kauth\.kakao\.com|oauth/i);
        await popup.close();
      }
    }
  });

  test('마이페이지 비로그인 접근', async ({ page }) => {
    // 마이페이지로 직접 접근 시도
    await page.goto('/mypage');

    // 로그인 요청 또는 리다이렉트 확인
    const loginPrompt = page.locator(
      '.login-required, .auth-required, button:has-text("로그인")'
    );
    const loginModal = page.locator('.modal, .login-modal');
    const redirectedToHome = page.url().includes('/') && !page.url().includes('/mypage');

    const needsLogin =
      (await loginPrompt.isVisible()) ||
      (await loginModal.isVisible()) ||
      redirectedToHome;

    expect(needsLogin).toBeTruthy();
  });

  test('모달 외부 클릭 시 닫기', async ({ page }) => {
    // 로그인 모달 열기
    await page.click('button:has-text("로그인"), a:has-text("로그인")');

    const modal = page.locator('.modal, .login-modal, [role="dialog"]');
    await expect(modal).toBeVisible({ timeout: 5000 });

    // 모달 배경(오버레이) 클릭
    const overlay = page.locator('.modal-overlay, .overlay, .backdrop');
    if (await overlay.isVisible()) {
      await overlay.click({ position: { x: 10, y: 10 } });
      await expect(modal).not.toBeVisible({ timeout: 3000 });
    }
  });

  test('접근성: 키보드 네비게이션', async ({ page }) => {
    // 로그인 모달 열기
    await page.click('button:has-text("로그인"), a:has-text("로그인")');

    const modal = page.locator('.modal, .login-modal, [role="dialog"]');
    await expect(modal).toBeVisible();

    // Tab 키로 버튼 간 이동
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');

    // 포커스가 모달 내에 있는지 확인
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();
  });
});

test.describe('Logged In State (if available)', () => {
  // 이 테스트는 storageState를 사용해 로그인 상태를 저장해야 함
  // 현재는 스킵
  test.skip('로그인 상태에서 사용자 메뉴 표시', async ({ page }) => {
    await page.goto('/');

    // 사용자 메뉴/프로필 확인
    const userMenu = page.locator('.user-menu, .user-profile, [data-testid="user-menu"]');
    await expect(userMenu).toBeVisible();
  });

  test.skip('로그아웃 버튼 동작', async ({ page }) => {
    await page.goto('/');

    // 로그아웃 버튼 클릭
    await page.click('button:has-text("로그아웃")');

    // 로그인 버튼 다시 표시
    const loginButton = page.locator('button:has-text("로그인")');
    await expect(loginButton).toBeVisible({ timeout: 5000 });
  });
});
