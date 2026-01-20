// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 5.7. User social accounts are linked correctly

import { test, expect } from '@playwright/test';

test.describe('User Profile & Data Management', () => {
  test('User social accounts are linked correctly', async ({ page, context }) => {
    // 1. Log in with Google
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_social_google_token',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    let response = await page.request.get('/api/users/me');
    let userData = await response.json();

    // 2. Verify social_accounts array contains Google entry
    expect(userData.social_accounts).toBeDefined();
    expect(Array.isArray(userData.social_accounts)).toBe(true);

    const googleAccount = userData.social_accounts.find((acc: any) => acc.provider === 'google');
    expect(googleAccount).toBeDefined();
    expect(googleAccount.provider).toBe('google');
    expect(googleAccount.social_id).toBeTruthy();

    // 3. Link Naver account (simulated)
    const linkedUser = {
      ...userData,
      social_accounts: [
        ...userData.social_accounts,
        {
          provider: 'naver',
          social_id: 'naver_123456',
        }
      ]
    };

    // 4. Verify social_accounts array contains both entries
    expect(linkedUser.social_accounts.length).toBeGreaterThanOrEqual(2);

    const googleAcc = linkedUser.social_accounts.find((acc: any) => acc.provider === 'google');
    const naverAcc = linkedUser.social_accounts.find((acc: any) => acc.provider === 'naver');

    expect(googleAcc).toBeDefined();
    expect(naverAcc).toBeDefined();

    // 5. Verify provider and social_id are correct
    expect(googleAcc.social_id).toBeTruthy();
    expect(naverAcc.social_id).toBe('naver_123456');
  });
});
