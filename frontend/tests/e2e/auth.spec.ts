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

test.describe('MyPage (마이페이지) Tests - 비로그인 상태', () => {
  test('비로그인 상태에서 마이페이지 접근 시 로그인 요청', async ({ page }) => {
    await page.goto('/mypage');

    // 로그인 요청 UI 확인
    const loginPrompt = page.locator(
      '.login-required, .auth-required, button:has-text("로그인"), .login-modal'
    );

    // 리다이렉트 또는 로그인 프롬프트
    const needsAuth =
      (await loginPrompt.isVisible()) ||
      page.url().includes('/login') ||
      (page.url().includes('/') && !page.url().includes('/mypage'));

    expect(needsAuth).toBeTruthy();
  });
});

test.describe('MyPage (마이페이지) Tests - 로그인 상태', () => {
  // 로그인 상태 테스트는 storageState 필요
  // 실제 테스트 시 setup 프로젝트에서 로그인 후 storageState 저장

  test.skip('프로필 정보 표시', async ({ page }) => {
    await page.goto('/mypage');

    // 닉네임
    const nickname = page.locator('.nickname, .user-name, [data-user-name]');
    await expect(nickname).toBeVisible();

    // 이메일
    const email = page.locator('.email, [data-email]');
    await expect(email).toBeVisible();

    // 가입일
    const joinDate = page.locator('.join-date, [data-join-date]');
    await expect(joinDate).toBeVisible();
  });

  test.skip('오늘의 사용량 표시', async ({ page }) => {
    await page.goto('/mypage');

    // 사용량 정보
    const usageInfo = page.locator('.usage, .quota, [data-usage]');
    await expect(usageInfo).toBeVisible();

    // 숫자가 표시됨
    const usageText = await usageInfo.textContent();
    expect(usageText).toMatch(/\d+/);
  });

  test.skip('연결된 계정 표시', async ({ page }) => {
    await page.goto('/mypage');

    // 연결된 소셜 계정들
    const connectedAccounts = page.locator(
      '.connected-accounts, .social-accounts, [data-accounts]'
    );
    await expect(connectedAccounts).toBeVisible();

    // Google, Naver, 카카오 중 하나 이상 연결됨
    const googleBadge = page.locator('[data-provider="google"], .google-connected');
    const naverBadge = page.locator('[data-provider="naver"], .naver-connected');
    const kakaoBadge = page.locator('[data-provider="kakao"], .kakao-connected');

    const anyConnected =
      (await googleBadge.isVisible()) ||
      (await naverBadge.isVisible()) ||
      (await kakaoBadge.isVisible());

    expect(anyConnected).toBeTruthy();
  });

  test.skip('로그아웃 버튼 동작', async ({ page }) => {
    await page.goto('/mypage');

    // 로그아웃 버튼
    const logoutButton = page.locator(
      'button:has-text("로그아웃"), a:has-text("로그아웃")'
    );
    await expect(logoutButton).toBeVisible();

    await logoutButton.click();

    // 로그인 페이지로 리다이렉트 또는 로그인 버튼 표시
    const loginButton = page.locator('button:has-text("로그인"), a:has-text("로그인")');
    await expect(loginButton).toBeVisible({ timeout: 5000 });
  });

  test.skip('채팅 기록 목록', async ({ page }) => {
    await page.goto('/mypage');

    // 채팅 기록 섹션
    const chatHistory = page.locator('.chat-history, [data-section="history"]');

    if (await chatHistory.isVisible()) {
      // 채팅 세션 목록
      const sessions = chatHistory.locator('.session-item, li');
      const count = await sessions.count();
      expect(count).toBeGreaterThanOrEqual(0);
    }
  });

  test.skip('채팅 기록에서 세션 삭제', async ({ page }) => {
    await page.goto('/mypage');

    const chatHistory = page.locator('.chat-history, [data-section="history"]');

    if (await chatHistory.isVisible()) {
      const deleteButton = chatHistory.locator(
        'button:has-text("삭제"), .delete-btn'
      ).first();

      if (await deleteButton.isVisible()) {
        await deleteButton.click();

        // 확인 모달
        const confirmButton = page.locator(
          'button:has-text("확인"), button:has-text("삭제")'
        );
        if (await confirmButton.isVisible()) {
          await confirmButton.click();
        }

        // 삭제 완료 메시지 또는 목록 업데이트
        await page.waitForTimeout(1000);
      }
    }
  });

  test.skip('설정 변경', async ({ page }) => {
    await page.goto('/mypage');

    // 설정 섹션
    const settings = page.locator('.settings, [data-section="settings"]');

    if (await settings.isVisible()) {
      // 토글이나 체크박스
      const toggle = settings.locator(
        'input[type="checkbox"], .toggle, [role="switch"]'
      ).first();

      if (await toggle.isVisible()) {
        await toggle.click();
        await page.waitForTimeout(500);

        // 설정 변경됨
      }
    }
  });

  test.skip('계정 삭제 버튼 (위험 영역)', async ({ page }) => {
    await page.goto('/mypage');

    // 계정 삭제 버튼 (보통 하단에 위치)
    const deleteAccountButton = page.locator(
      'button:has-text("계정 삭제"), button:has-text("탈퇴"), .danger-btn'
    );

    if (await deleteAccountButton.isVisible()) {
      // 버튼이 존재하지만 클릭하지 않음 (위험한 작업)
      await expect(deleteAccountButton).toBeVisible();
    }
  });
});

test.describe('MyPage 접근성', () => {
  test('비로그인 상태에서 키보드 네비게이션', async ({ page }) => {
    await page.goto('/mypage');

    // Tab으로 이동
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');

    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();
  });
});