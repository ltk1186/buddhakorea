// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 2.5. Error state handles connection failures

import { test, expect } from '@playwright/test';

test.describe('Login UI & Session Management', () => {
  test('Error state handles connection failures', async ({ page }) => {
    // 1. Mock API failure for /api/users/me endpoint
    await page.route('**/api/users/me', (route) => {
      route.abort('failed');
    });

    // 2. Open mypage.html
    await page.goto('/mypage.html');
    await page.waitForTimeout(2000);

    // 3. Verify error message displays
    const errorMessage = page.locator(
      '[data-testid="error-message"], .error, .alert-danger, .error-state'
    ).first();
    
    const isErrorVisible = await errorMessage.isVisible().catch(() => false);
    expect(isErrorVisible).toBe(true);

    // Verify error text is user-friendly
    const errorText = await errorMessage.textContent();
    expect(errorText).toBeTruthy();
    expect(errorText).not.toMatch(/undefined|null/i);

    // 4. Verify user can navigate home
    const homeButton = page.locator(
      'button:has-text("홈"), a:has-text("홈"), [data-testid="home-btn"], a[href="/"]'
    ).first();
    
    const isNavAvailable = await homeButton.isVisible().catch(() => false);
    expect(isNavAvailable).toBe(true);

    // 5. Verify page gracefully handles network error
    // Check console for errors
    const consoleMessages: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleMessages.push(msg.text());
      }
    });

    // Wait a bit more
    await page.waitForTimeout(1000);

    // Verify no uncaught errors
    const hasUncaughtErrors = consoleMessages.some(msg =>
      msg.includes('Uncaught') || msg.includes('TypeError')
    );
    expect(hasUncaughtErrors).toBe(false);
  });
});
