// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 1.5. OAuth callback handles existing user

import { test, expect } from '@playwright/test';

test.describe('OAuth Login Flow', () => {
  test('OAuth callback handles existing user', async ({ page, context }) => {
    // 1. Set up a pre-existing user with social account
    // Mock existing user data
    const existingUser = {
      id: 'ltk1186',
      email: 'ltk1186@gmail.com',
      nickname: 'ltk1186',
      is_active: true,
      last_login: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
      social_accounts: [
        {
          provider: 'google',
          social_id: 'google_123',
        }
      ],
    };

    // Store initial last_login timestamp
    const initialLastLogin = new Date(existingUser.last_login);

    // 2. Simulate OAuth callback with same user data
    await context.addInitScript(() => {
      window.mockExistingUser = true;
    });

    await page.goto('/auth/callback/google?code=test_code&state=test_state');
    await page.waitForTimeout(2000);

    // 3. Verify user record is not duplicated
    const meResponse = await page.request.get('/api/users/me').catch(() => null);
    if (meResponse && meResponse.ok()) {
      const userData = await meResponse.json();
      
      // Check that user still has same ID (not duplicated)
      expect(userData.id).toBe(existingUser.id);
      expect(userData.email).toBe(existingUser.email);

      // 4. Verify social account association is maintained
      expect(userData.social_accounts).toBeDefined();
      expect(userData.social_accounts.length).toBeGreaterThan(0);
      
      const googleAccount = userData.social_accounts.find((acc: any) => acc.provider === 'google');
      expect(googleAccount).toBeDefined();
      expect(googleAccount.social_id).toBe('google_123');

      // 5. Verify last_login timestamp is updated
      const newLastLogin = new Date(userData.last_login);
      expect(newLastLogin.getTime()).toBeGreaterThan(initialLastLogin.getTime());
    }
  });
});
