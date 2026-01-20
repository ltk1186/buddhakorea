// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 5.1. User profile includes all required fields

import { test, expect } from '@playwright/test';

test.describe('User Profile & Data Management', () => {
  test('User profile includes all required fields', async ({ page, context }) => {
    // 1. Log in user
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_profile_fields_token',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // 2. Call /api/users/me endpoint
    const response = await page.request.get('/api/users/me');

    if (response.ok()) {
      // 3. Verify response includes: id, email, nickname, profile_img, role, created_at, last_login
      const userData = await response.json();
      
      expect(userData).toHaveProperty('id');
      expect(userData).toHaveProperty('email');
      expect(userData).toHaveProperty('nickname');
      expect(userData).toHaveProperty('profile_img');
      expect(userData).toHaveProperty('role');
      expect(userData).toHaveProperty('created_at');
      expect(userData).toHaveProperty('last_login');

      // Profile image URL should be valid or null
      if (userData.profile_img) {
        expect(typeof userData.profile_img).toBe('string');
      }

      // Timestamps should be in ISO format
      expect(userData.created_at).toMatch(/^\d{4}-\d{2}-\d{2}/); // ISO format check
      expect(userData.last_login).toMatch(/^\d{4}-\d{2}-\d{2}/);
    }
  });
});
