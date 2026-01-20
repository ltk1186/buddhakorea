// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 2.3. Loading state displays correctly

import { test, expect } from '@playwright/test';

test.describe('Login UI & Session Management', () => {
  test('Loading state displays correctly', async ({ page }) => {
    // Intercept the /api/users/me call to simulate a slow response
    await page.route('**/api/users/me', async (route) => {
      // Wait before responding to show loading state
      await new Promise(resolve => setTimeout(resolve, 2000));
      await route.continue();
    });

    // 1. Open mypage.html
    await page.goto('/mypage.html');

    // 2. Observe initial loading state
    const loadingSpinner = page.locator(
      '[data-testid="loading-spinner"], .spinner, .loading, .sk-circle'
    ).first();
    
    const isLoadingVisible = await loadingSpinner.isVisible({ timeout: 3000 }).catch(() => false);
    expect(isLoadingVisible).toBe(true);

    // 3. Wait for user data to load
    await page.waitForLoadState('networkidle');

    // 4. Verify loading spinner disappears
    await expect(loadingSpinner).not.toBeVisible({ timeout: 5000 });

    // 5. Verify content is displayed
    const profileSection = page.locator(
      '[data-testid="profile-section"], .profile, .user-profile, .content'
    ).first();
    
    const isContentVisible = await profileSection.isVisible().catch(() => false);
    expect(isContentVisible).toBe(true);
  });
});
