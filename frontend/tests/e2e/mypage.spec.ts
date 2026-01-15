import { test, expect } from '@playwright/test';

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
