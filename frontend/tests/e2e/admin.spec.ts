import { expect, test } from "@playwright/test";

test.describe("Admin Panel E2E Tests", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/admin/me", async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          id: 1,
          email: "admin@buddhakorea.com",
          nickname: "SuperAdmin",
          role: "admin",
          is_active: true,
        },
      });
    });

    await page.route("**/api/health", async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          status: "healthy",
          version: "0.1.0",
          chroma_connected: true,
          llm_configured: true,
        },
      });
    });

    await page.route("**/api/admin/summary", async (route) => {
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
          usage_last_7_days: {},
        },
      });
    });

    await page.route("**/api/admin/usage-stats*", async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          total_queries: 500,
          tokens: { total: 1000000 },
          total_cost_usd: 15.5,
          by_day: {},
        },
      });
    });

    await page.route("**/api/admin/observability*", async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          window_days: 7,
          usage_log_available: true,
          total_queries: 120,
          queries_with_latency: 100,
          cache_hit_rate: 25,
          avg_cost_per_query_usd: 0.012345,
          avg_latency_ms: 1800,
          p50_latency_ms: 1400,
          p95_latency_ms: 4200,
          slow_query_threshold_ms: 30000,
          slow_queries: 3,
          answers_last_24h: 12,
          zero_source_answers_24h: 2,
          zero_source_rate_24h: 16.67,
          avg_sources_per_answer_24h: 3.4,
          rate_limited_users_today: 4,
          rate_limited_anonymous_today: 1,
          daily: [
            {
              date: "2026-04-16",
              queries: 20,
              cost_usd: 0.4,
              cached_queries: 5,
              cache_hit_rate: 25,
              avg_latency_ms: 1700,
              p95_latency_ms: 3500,
            },
          ],
        },
      });
    });

    await page.route("**/api/admin/users/2", async (route) => {
      if (route.request().method() === "PATCH") {
        const body = route.request().postDataJSON();
        await route.fulfill({
          status: 200,
          json: {
            id: 2,
            email: "testuser@example.com",
            nickname: "TestUser",
            role: "user",
            is_active: body.is_active,
            daily_chat_limit: body.daily_chat_limit,
            last_login: "2025-01-01T00:00:00Z",
            created_at: "2024-01-01T00:00:00Z",
            today_usage: 5,
          },
        });
        return;
      }

      await route.fulfill({
        status: 200,
        json: {
          user: {
            id: 2,
            email: "testuser@example.com",
            nickname: "TestUser",
            role: "user",
            is_active: true,
            daily_chat_limit: 20,
            last_login: "2025-01-01T00:00:00Z",
            created_at: "2024-01-01T00:00:00Z",
            today_usage: 5,
          },
          social_accounts: [
            {
              id: 8,
              provider: "google",
              provider_user_id: "google-123",
              provider_email: "testuser@example.com",
              token_expires_at: null,
              created_at: "2024-01-01T00:00:00Z",
              last_used_at: "2025-01-01T00:00:00Z",
            },
          ],
          recent_sessions: [
            {
              id: 3,
              session_uuid: "session-123",
              title: "Four Noble Truths",
              summary: "summary",
              is_active: true,
              is_archived: false,
              message_count: 4,
              created_at: "2025-01-01T11:00:00Z",
              last_message_at: "2025-01-01T12:00:00Z",
            },
          ],
          recent_usage: [
            { usage_date: "2026-04-16", chat_count: 5, tokens_used: 1500 },
          ],
          recent_audit: [],
        },
      });
    });

    await page.route("**/api/admin/users*", async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          {
            id: 2,
            email: "testuser@example.com",
            nickname: "TestUser",
            role: "user",
            is_active: true,
            daily_chat_limit: 20,
            last_login: "2025-01-01T00:00:00Z",
            created_at: "2024-01-01T00:00:00Z",
            today_usage: 5,
          },
        ],
      });
    });

    await page.route("**/api/admin/queries/102/review", async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          id: 1,
          message_id: 102,
          status: "resolved",
          reason: "bad_answer",
          note: "Checked",
          created_by_admin_id: 1,
          updated_by_admin_id: 1,
          created_at: "2025-01-01T12:00:00Z",
          updated_at: "2025-01-01T12:10:00Z",
        },
      });
    });

    await page.route("**/api/admin/queries/101", async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          selected_message_id: 101,
          review_target_message_id: 102,
          session_uuid: "session-123",
          session_message_count: 2,
          user_id: 2,
          user_nickname: "TestUser",
          user_email: "testuser@example.com",
          query: {
            id: 101,
            role: "user",
            content: "This is a test query",
            created_at: "2025-01-01T12:00:00Z",
          },
          answer: {
            id: 102,
            content: "This is a traced answer",
            created_at: "2025-01-01T12:00:02Z",
            model_used: "gemini-2.5-pro",
            provider: "gemini_vertex",
            response_mode: "normal",
            tokens_used: 150,
            latency_ms: 1200,
            sources_count: 3,
            sources_json: [{ title: "Saṃyutta Nikāya", chunk_id: "sn-1" }],
            trace_json: {
              provider: "gemini_vertex",
              prompt: { id: "normal_v1", version: "v1" },
              retrieval: { mode: "default", top_k: 3 },
            },
          },
          review: {
            id: 1,
            message_id: 102,
            status: "open",
            reason: "bad_answer",
            note: "Needs follow-up",
            created_by_admin_id: 1,
            updated_by_admin_id: 1,
            created_at: "2025-01-01T12:00:00Z",
            updated_at: "2025-01-01T12:05:00Z",
          },
        },
      });
    });

    await page.route("**/api/admin/queries*", async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          {
            id: 101,
            session_uuid: "session-123",
            user_id: 2,
            user_nickname: "TestUser",
            user_email: "testuser@example.com",
            role: "user",
            content: "This is a test query",
            model_used: "gemini-2.5-pro",
            sources_count: 3,
            response_mode: "normal",
            tokens_used: 150,
            latency_ms: 1200,
            created_at: "2025-01-01T12:00:00Z",
            sources_json: null,
            review_status: "open",
          },
        ],
      });
    });

    await page.route("**/api/admin/sessions/session-123", async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          id: 3,
          session_uuid: "session-123",
          user_id: 2,
          user_nickname: "TestUser",
          user_email: "testuser@example.com",
          title: "Four Noble Truths",
          summary: "summary",
          is_active: true,
          is_archived: false,
          message_count: 2,
          created_at: "2025-01-01T11:00:00Z",
          last_message_at: "2025-01-01T12:00:00Z",
          messages: [
            {
              id: 101,
              role: "user",
              content: "This is a test query",
              created_at: "2025-01-01T12:00:00Z",
              model_used: null,
              response_mode: null,
              provider: null,
              sources_count: 0,
              review_status: null,
            },
            {
              id: 102,
              role: "assistant",
              content: "This is a traced answer",
              created_at: "2025-01-01T12:00:02Z",
              model_used: "gemini-2.5-pro",
              response_mode: "normal",
              provider: "gemini_vertex",
              sources_count: 3,
              review_status: "open",
            },
          ],
        },
      });
    });

    await page.route("**/api/admin/data/tables", async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          {
            name: "users",
            label: "Users",
            description: "Core account records and support controls.",
            searchable_columns: ["email", "nickname", "role"],
          },
          {
            name: "chat_messages",
            label: "Chat Messages",
            description: "Persisted user and assistant messages.",
            searchable_columns: ["role", "content"],
          },
        ],
      });
    });

    await page.route("**/api/admin/data/tables/users/schema", async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          table: {
            name: "users",
            label: "Users",
            description: "Core account records and support controls.",
            searchable_columns: ["email", "nickname", "role"],
          },
          columns: [
            { name: "id", type: "INTEGER", nullable: false, primary_key: true },
            { name: "email", type: "VARCHAR(255)", nullable: true, primary_key: false },
            { name: "nickname", type: "VARCHAR(100)", nullable: false, primary_key: false },
          ],
        },
      });
    });

    await page.route("**/api/admin/data/tables/users/rows*", async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          table: {
            name: "users",
            label: "Users",
            description: "Core account records and support controls.",
            searchable_columns: ["email", "nickname", "role"],
          },
          total: 1,
          limit: 25,
          offset: 0,
          rows: [
            { id: 2, email: "testuser@example.com", nickname: "TestUser", role: "user" },
          ],
        },
      });
    });

    await page.route("**/api/admin/audit-logs*", async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          {
            id: 1001,
            admin_user_id: 1,
            admin_email: "admin@buddhakorea.com",
            action: "user.update",
            target_type: "user",
            target_id: "2",
            before_state: { daily_chat_limit: 20 },
            after_state: { daily_chat_limit: 50 },
            context: { source: "admin_api" },
            created_at: "2025-01-01T12:05:00Z",
          },
        ],
      });
    });
  });

  test("should load admin dashboard and display metrics", async ({ page }) => {
    await page.goto("/admin/");
    await expect(page.locator("#adminUser")).toHaveText("SuperAdmin (admin)");
    await expect(page.locator("#metricUsers")).toHaveText("100");
    await expect(page.locator("#metricQueries")).toHaveText("70");
    await expect(page.locator("#metricTokens")).toHaveText("15,000");
    await expect(page.locator("#metricMessages")).toHaveText("120");
  });

  test("should inspect a user and render identities, sessions, and usage", async ({ page }) => {
    await page.goto("/admin/");
    await page.click('button[data-section="users"]');
    await expect(page.locator("#section-users")).toHaveClass(/is-active/);
    await page.click('button[data-action="inspect-user"]');
    await expect(page.locator("#userDetailTitle")).toContainText("TestUser");
    await expect(page.locator("#userDetailContent")).toContainText("google");
    await expect(page.locator("#userDetailContent")).toContainText("session-123");
    await expect(page.locator("#userDetailContent")).toContainText("2026-04-16");
  });

  test("should open query investigation detail and save review", async ({ page }) => {
    await page.goto("/admin/");
    await page.click('button[data-section="queries"]');
    await expect(page.locator("#queriesTable tbody tr")).toHaveCount(1);

    const reviewRequest = page.waitForRequest((request) => {
      return request.url().includes("/api/admin/queries/102/review") && request.method() === "PATCH";
    });

    await page.click('button[data-action="view-query-detail"]');
    await expect(page.locator("#queryDetailTitle")).toContainText("session-123");
    await expect(page.locator("#queryDetailContent")).toContainText("normal_v1");
    await expect(page.locator("#queryDetailContent")).toContainText("Saṃyutta Nikāya");
    await expect(page.locator("#queryDetailContent")).toContainText("Session Timeline");

    await page.selectOption("#queryReviewEditorStatus", "resolved");
    await page.fill("#queryReviewEditorNote", "Checked");
    await page.click('button[data-action="save-query-review"]');

    const request = await reviewRequest;
    const payload = request.postDataJSON();
    expect(payload.status).toBe("resolved");
    expect(payload.note).toBe("Checked");
  });

  test("should render read-only data explorer", async ({ page }) => {
    await page.goto("/admin/");
    await page.click('button[data-section="data"]');
    await expect(page.locator("#section-data")).toHaveClass(/is-active/);
    await expect(page.locator("#dataTableLabel")).toContainText("Users");
    await expect(page.locator("#dataRowsTable")).toContainText("TestUser");
    await expect(page.locator("#dataDetailContent")).toContainText("email");
  });

  test("should display reliability metrics and audit logs", async ({ page }) => {
    await page.goto("/admin/");
    await page.click('button[data-section="reliability"]');
    await expect(page.locator("#reliabilityP95")).toHaveText("4,200 ms");
    await expect(page.locator("#reliabilityZeroSource")).toHaveText("16.7%");

    await page.click('button[data-section="audit"]');
    await expect(page.locator("#auditTable tbody tr")).toHaveCount(1);
    await expect(page.locator("#auditTable tbody tr").first()).toContainText("user.update");
  });
});

test.describe("Admin Panel RBAC UI Tests", () => {
  test("should hide write controls for analyst role", async ({ page }) => {
    await page.route("**/api/admin/me", async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          id: 3,
          email: "analyst@buddhakorea.com",
          nickname: "Analyst",
          role: "analyst",
          is_active: true,
        },
      });
    });

    await page.route("**/api/health", async (route) => {
      await route.fulfill({
        status: 200,
        json: { status: "healthy", chroma_connected: true, llm_configured: true },
      });
    });

    await page.route("**/api/admin/summary", async (route) => {
      await route.fulfill({ status: 200, json: { usage_last_7_days: {} } });
    });

    await page.route("**/api/admin/usage-stats*", async (route) => {
      await route.fulfill({ status: 200, json: { tokens: {}, by_day: {}, total_queries: 0, total_cost_usd: 0 } });
    });

    await page.route("**/api/admin/observability*", async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          window_days: 7,
          usage_log_available: false,
          total_queries: 0,
          queries_with_latency: 0,
          cache_hit_rate: 0,
          avg_cost_per_query_usd: 0,
          avg_latency_ms: null,
          p50_latency_ms: null,
          p95_latency_ms: null,
          slow_query_threshold_ms: 30000,
          slow_queries: 0,
          answers_last_24h: 0,
          zero_source_answers_24h: 0,
          zero_source_rate_24h: 0,
          avg_sources_per_answer_24h: 0,
          rate_limited_users_today: 0,
          rate_limited_anonymous_today: 0,
          daily: [],
        },
      });
    });

    await page.route("**/api/admin/users*", async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          {
            id: 2,
            email: "te***@example.com",
            nickname: "TestUser",
            role: "user",
            is_active: true,
            daily_chat_limit: 20,
            last_login: "2025-01-01T00:00:00Z",
            created_at: "2024-01-01T00:00:00Z",
            today_usage: 5,
          },
        ],
      });
    });

    await page.route("**/api/admin/queries*", async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });

    await page.route("**/api/admin/data/tables", async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });

    await page.route("**/api/admin/audit-logs*", async (route) => {
      await route.fulfill({ status: 403, body: "forbidden" });
    });

    await page.goto("/admin/");
    await expect(page.locator("#adminUser")).toHaveText("Analyst (analyst)");
    await page.click('button[data-section="users"]');
    const row = page.locator("#usersTable tbody tr").first();
    await expect(row.locator('button[data-action="save-user"]')).toBeDisabled();
    await expect(row.locator('input[data-field="limit"]')).toBeDisabled();
  });
});
