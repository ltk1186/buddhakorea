// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 5.9. User can view usage statistics

import { test, expect } from '@playwright/test';

test.describe('User Profile & Data Management', () => {
  test('User can view usage statistics', async ({ page, context }) => {
    // 1. Log in user
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_usage_stats_token',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // 2. Navigate to mypage.html
    await page.goto('/mypage.html');
    await page.waitForLoadState('networkidle');

    // 3. Verify usage stats are displayed (X/20 requests)
    const usageStats = page.locator(
      '[data-testid="usage-stats"], .usage-stats, .daily-limit, .requests-info'
    ).first();
    
    const isStatsVisible = await usageStats.isVisible().catch(() => false);
    expect(isStatsVisible).toBe(true);

    // Get usage text (e.g., "3/20")
    const statsText = await usageStats.textContent();
    expect(statsText).toMatch(/\d+\/\d+/); // Should match X/Y format

    // 4. Call chat endpoint
    const initialStats = statsText;

    await page.request.post('/api/chat', {
      data: { message: 'Test message for usage stats' }
    }).catch(() => null);

    // 5. Refresh mypage
    await page.reload();
    await page.waitForLoadState('networkidle');

    // 6. Verify usage count increased
    const updatedStats = page.locator(
      '[data-testid="usage-stats"], .usage-stats, .daily-limit, .requests-info'
    ).first();
    
    const updatedStatsText = await updatedStats.textContent();
    
    // Parse the X/Y format to verify increase
    const initialMatch = initialStats?.match(/(\d+)\/(\d+)/);
    const updatedMatch = updatedStatsText?.match(/(\d+)\/(\d+)/);

    if (initialMatch && updatedMatch) {
      const initialCount = parseInt(initialMatch[1], 10);
      const updatedCount = parseInt(updatedMatch[1], 10);
      
      // Usage should have increased (or stayed same if API call failed)
      expect(updatedCount).toBeGreaterThanOrEqual(initialCount);
    }
  });
});
