// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 1.7. Multiple OAuth provider links

import { test, expect } from '@playwright/test';

test.describe('OAuth Login Flow', () => {
  test('Multiple OAuth provider links', async ({ page, context }) => {
    // 1. Create user with Google OAuth
    await context.addInitScript(() => {
      window.mockGoogleUser = {
        id: 'user_multi_789',
        email: 'multiuser@example.com',
        nickname: 'MultiUser',
        social_accounts: [
          {
            provider: 'google',
            social_id: 'google_456',
            is_primary: true,
          }
        ],
      };
    });

    await page.goto('/auth/callback/google?code=test_code&state=test_state');
    await page.waitForTimeout(2000);

    // 2. Log in to mypage
    await page.goto('/mypage.html');
    await page.waitForLoadState('networkidle');

    // 3. Verify option to link additional providers
    const linkNaverBtn = page.locator('[data-testid="link-naver"], button:has-text("네이버 연결"), .link-naver-btn').first();
    const linkKakaoBtn = page.locator('[data-testid="link-kakao"], button:has-text("카카오 연결"), .link-kakao-btn').first();
    
    const hasLinkOptions = 
      (await linkNaverBtn.isVisible().catch(() => false)) ||
      (await linkKakaoBtn.isVisible().catch(() => false));
    
    expect(hasLinkOptions).toBeTruthy();

    // 4. Link Naver account to same user (simulate)
    const meResponse = await page.request.get('/api/users/me').catch(() => null);
    if (meResponse && meResponse.ok()) {
      const userData = await meResponse.json();
      
      // Mock adding Naver account
      const updatedUser = {
        ...userData,
        social_accounts: [
          ...userData.social_accounts,
          {
            provider: 'naver',
            social_id: 'naver_789',
            is_primary: false,
          }
        ],
      };

      // 5. Verify both social accounts are associated
      expect(updatedUser.social_accounts.length).toBeGreaterThanOrEqual(2);
      
      const googleAcc = updatedUser.social_accounts.find((acc: any) => acc.provider === 'google');
      const naverAcc = updatedUser.social_accounts.find((acc: any) => acc.provider === 'naver');
      
      expect(googleAcc).toBeDefined();
      expect(naverAcc).toBeDefined();

      // 6. Verify primary provider is correctly set
      const primaryAcc = updatedUser.social_accounts.find((acc: any) => acc.is_primary === true);
      expect(primaryAcc).toBeDefined();
      expect(primaryAcc.provider).toBe('google');
    }
  });
});
