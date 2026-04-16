import { test, expect } from '@playwright/test';

test.describe('Admin Panel E2E Tests', () => {

  test.beforeEach(async ({ page }) => {
    // Mock the /api/admin/me endpoint to simulate an logged in admin
    await page.route('**/api/admin/me', async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          id: 1,
          email: 'admin@buddhakorea.com',
          nickname: 'SuperAdmin',
          role: 'admin',
          is_active: true
        }
      });
    });

    // Mock summary API
    await page.route('**/api/admin/summary', async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          users_total: 100,
          users_active: 90,
          users_suspended: 10,
          today_queries_logged_in: 50,
          today_queries_anonymous: 20,
          today_tokens_used: 15000,
          messages_last_24h: 120,
          usage_last_7_days: {}
        }
      });
    });

    // Mock usage stats API
    await page.route('**/api/admin/usage-stats*', async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          total_queries: 500,
          tokens: { total: 1000000 },
          total_cost_usd: 15.5,
          by_day: {}
        }
      });
    });

    // Mock users list
    await page.route('**/api/admin/users*', async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          {
            id: 2,
            email: 'testuser@example.com',
            nickname: 'TestUser',
            role: 'user',
            is_active: true,
            daily_chat_limit: 20,
            last_login: '2025-01-01T00:00:00Z',
            created_at: '2024-01-01T00:00:00Z',
            today_usage: 5
          }
        ]
      });
    });

    // Mock user update (PATCH)
    await page.route('**/api/admin/users/2', async (route) => {
      if (route.request().method() === 'PATCH') {
        const postData = JSON.parse(route.request().postData() || '{}');
        await route.fulfill({
          status: 200,
          json: {
            id: 2,
            email: 'testuser@example.com',
            nickname: 'TestUser',
            role: 'user',
            is_active: postData.is_active !== undefined ? postData.is_active : true,
            daily_chat_limit: postData.daily_chat_limit !== undefined ? postData.daily_chat_limit : 20,
            last_login: '2025-01-01T00:00:00Z',
            created_at: '2024-01-01T00:00:00Z',
            today_usage: 5
          }
        });
      } else {
        await route.continue();
      }
    });

    await page.route('**/api/admin/queries/*', async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          selected_message_id: 101,
          session_uuid: 'session-123',
          user_id: 2,
          user_nickname: 'TestUser',
          user_email: 'testuser@example.com',
          query: {
            id: 101,
            role: 'user',
            content: 'This is a test query',
            created_at: '2025-01-01T12:00:00Z'
          },
          answer: {
            id: 102,
            content: 'This is a traced answer',
            created_at: '2025-01-01T12:00:02Z',
            model_used: 'gemini-2.5-pro',
            provider: 'gemini_vertex',
            response_mode: 'normal',
            tokens_used: 150,
            latency_ms: 1200,
            sources_count: 3,
            sources_json: [{ title: 'Saṃyutta Nikāya', chunk_id: 'sn-1' }],
            trace_json: {
              provider: 'gemini_vertex',
              prompt: { id: 'normal_v1', version: 'v1' },
              retrieval: { mode: 'default', top_k: 3 }
            }
          }
        }
      });
    });

    // Mock query logs
    await page.route('**/api/admin/queries*', async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          {
            id: 101,
            session_uuid: 'session-123',
            user_id: 2,
            user_nickname: 'TestUser',
            user_email: 'testuser@example.com',
            role: 'user',
            content: 'This is a test query',
            model_used: 'gemini-2.5-pro',
            sources_count: 3,
            response_mode: 'normal',
            tokens_used: 150,
            latency_ms: 1200,
            created_at: '2025-01-01T12:00:00Z',
            sources_json: null
          }
        ]
      });
    });

    // Mock audit logs
    await page.route('**/api/admin/audit-logs*', async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          {
            id: 1001,
            admin_user_id: 1,
            admin_email: 'admin@buddhakorea.com',
            action: 'user.update',
            target_type: 'user',
            target_id: '2',
            before_state: { daily_chat_limit: 20 },
            after_state: { daily_chat_limit: 50 },
            context: { source: 'admin_api' },
            created_at: '2025-01-01T12:05:00Z'
          }
        ]
      });
    });
  });

  test('should load admin dashboard and display metrics', async ({ page }) => {
    await page.goto('/admin/');

    // Wait for auth check to finish
    await expect(page.locator('#adminUser')).toHaveText('SuperAdmin (admin)');

    // Verify Dashboard metrics
    await expect(page.locator('#metricUsers')).toHaveText('100');
    await expect(page.locator('#metricQueries')).toHaveText('70'); // 50 logged in + 20 anonymous
    await expect(page.locator('#metricTokens')).toHaveText('15,000');
    await expect(page.locator('#metricMessages')).toHaveText('120');
  });

  test('should allow admin to navigate to users and edit quota', async ({ page }) => {
    await page.goto('/admin/');
    
    // Navigate to Users tab
    await page.click('button[data-section="users"]');
    await expect(page.locator('#section-users')).toHaveClass(/is-active/);

    // Ensure the users table is populated
    await expect(page.locator('#usersTable tbody tr')).toHaveCount(1);
    await expect(page.locator('#usersTable tbody tr').first()).toContainText('testuser@example.com');

    const row = page.locator('#usersTable tbody tr').first();
    const limitInput = row.locator('input[data-field="limit"]');
    const saveButton = row.locator('button[data-action="save-user"]');

    await expect(saveButton).toBeEnabled();
    await limitInput.fill('50');

    const requestPromise = page.waitForRequest((request) => {
      return request.url().includes('/api/admin/users/2') && request.method() === 'PATCH';
    });

    await saveButton.click();
    const request = await requestPromise;
    const payload = request.postDataJSON();
    expect(payload.daily_chat_limit).toBe(50);
  });

  test('should display masked queries in Query Monitor', async ({ page }) => {
    await page.goto('/admin/');
    
    // Navigate to Queries tab
    await page.click('button[data-section="queries"]');
    await expect(page.locator('#section-queries')).toHaveClass(/is-active/);

    // Verify query is displayed
    await expect(page.locator('#queriesTable tbody tr')).toHaveCount(1);
    await expect(page.locator('#queriesTable tbody tr').first()).toContainText('This is a test query');
  });

  test('should open query investigation detail with trace metadata', async ({ page }) => {
    await page.goto('/admin/');

    await page.click('button[data-section="queries"]');
    await expect(page.locator('#section-queries')).toHaveClass(/is-active/);
    await expect(page.locator('#queriesTable tbody tr')).toHaveCount(1);
    await expect(page.locator('button[data-action="view-query-detail"]')).toHaveCount(1);

    const requestPromise = page.waitForRequest((request) => {
      return request.url().includes('/api/admin/queries/101') && request.method() === 'GET';
    });

    await page.click('button[data-action="view-query-detail"]');
    await requestPromise;

    await expect(page.locator('#queryDetailTitle')).toContainText('session-123');
    await expect(page.locator('#queryDetailSummary')).toContainText('gemini_vertex');
    await expect(page.locator('#queryDetailContent')).toContainText('This is a traced answer');
    await expect(page.locator('#queryDetailContent')).toContainText('normal_v1');
    await expect(page.locator('#queryDetailContent')).toContainText('Saṃyutta Nikāya');
  });

  test('should display audit logs', async ({ page }) => {
    await page.goto('/admin/');
    
    // Navigate to Audit Logs tab
    await page.click('button[data-section="audit"]');
    await expect(page.locator('#section-audit')).toHaveClass(/is-active/);

    // Verify audit log is displayed
    await expect(page.locator('#auditTable tbody tr')).toHaveCount(1);
    await expect(page.locator('#auditTable tbody tr').first()).toContainText('user.update');
    await expect(page.locator('#auditTable tbody tr').first()).toContainText('admin@buddhakorea.com');
  });

});

test.describe('Admin Panel RBAC UI Tests', () => {

  test('should hide edit controls for analyst role', async ({ page }) => {
    // Mock the /api/admin/me endpoint to simulate an analyst
    await page.route('**/api/admin/me', async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          id: 3,
          email: 'analyst@buddhakorea.com',
          nickname: 'Analyst',
          role: 'analyst',
          is_active: true
        }
      });
    });

    await page.route('**/api/admin/summary', async (route) => {
      await route.fulfill({ status: 200, json: { usage_last_7_days: {} } });
    });
    
    await page.route('**/api/admin/usage-stats*', async (route) => {
      await route.fulfill({ status: 200, json: { tokens: {} } });
    });

    await page.route('**/api/admin/queries*', async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });

    await page.route('**/api/admin/audit-logs*', async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });

    await page.route('**/api/admin/users*', async (route) => {
        await route.fulfill({
          status: 200,
          json: [
            {
              id: 2,
              email: 'testuser@example.com',
              nickname: 'TestUser',
              role: 'user',
              is_active: true,
              daily_chat_limit: 20,
              last_login: '2025-01-01T00:00:00Z',
              created_at: '2024-01-01T00:00:00Z',
              today_usage: 5
            }
          ]
        });
      });

    await page.goto('/admin/');
    await expect(page.locator('#adminUser')).toHaveText('Analyst (analyst)');

    await page.click('button[data-section="users"]');
    
    // Ensure the users table is populated
    await expect(page.locator('#usersTable tbody tr')).toHaveCount(1);
    
    // Verify save control is disabled for analyst
    const saveButton = page.locator('#usersTable tbody tr').first().locator('button[data-action="save-user"]');
    await expect(saveButton).toBeDisabled();
  });

});
