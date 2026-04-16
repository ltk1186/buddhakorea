"use strict";

const state = {
    adminUser: null,
    canEditUsers: false,
    selectedQueryId: null
};

const elements = {
    authStatus: document.getElementById("authStatus"),
    adminUser: document.getElementById("adminUser"),
    noticeBanner: document.getElementById("noticeBanner"),
    refreshAll: document.getElementById("refreshAll"),
    usageDays: document.getElementById("usageDays"),
    reliabilityDays: document.getElementById("reliabilityDays"),
    userSearch: document.getElementById("userSearch"),
    userStatus: document.getElementById("userStatus"),
    queryRole: document.getElementById("queryRole"),
    querySession: document.getElementById("querySession"),
    queryUserId: document.getElementById("queryUserId"),
    queryDetailPanel: document.getElementById("queryDetailPanel"),
    queryDetailTitle: document.getElementById("queryDetailTitle"),
    queryDetailSummary: document.getElementById("queryDetailSummary"),
    queryDetailEmpty: document.getElementById("queryDetailEmpty"),
    queryDetailContent: document.getElementById("queryDetailContent"),
    adminLoginForm: document.getElementById("adminLoginForm"),
    adminEmail: document.getElementById("adminEmail"),
    adminPassword: document.getElementById("adminPassword"),
    adminLoginStatus: document.getElementById("adminLoginStatus")
};

const sections = Array.from(document.querySelectorAll(".admin-section"));
const navLinks = Array.from(document.querySelectorAll(".nav-link"));

function formatNumber(value) {
    if (value === null || value === undefined) {
        return "-";
    }
    return Number(value).toLocaleString("en-US");
}

function formatCost(value) {
    if (value === null || value === undefined) {
        return "-";
    }
    return `$${Number(value).toFixed(4)}`;
}

function formatPercentage(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return "-";
    }
    return `${Number(value).toFixed(1)}%`;
}

function escapeHtml(value) {
    if (value === null || value === undefined) {
        return "";
    }
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatTimestamp(value) {
    if (!value) {
        return "-";
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        return value;
    }
    return parsed.toLocaleString("en-US", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false
    });
}

function prettyJson(value) {
    if (value === null || value === undefined) {
        return "-";
    }
    return JSON.stringify(value, null, 2);
}

async function apiFetch(path, options = {}) {
    const response = await fetch(path, {
        credentials: "include",
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        },
        ...options
    });
    if (!response.ok) {
        const message = await response.text();
        throw new Error(message || response.statusText);
    }
    return response.json();
}

function setAuthState(isAuthorized) {
    elements.noticeBanner.classList.toggle("is-visible", !isAuthorized);
    elements.authStatus.textContent = isAuthorized ? "Access granted" : "Access denied";
}

function switchSection(sectionId) {
    sections.forEach(section => {
        section.classList.toggle("is-active", section.id === `section-${sectionId}`);
    });
    navLinks.forEach(link => {
        link.classList.toggle("is-active", link.dataset.section === sectionId);
    });
}

async function loadAdminUser() {
    try {
        const data = await apiFetch("/api/admin/me");
        state.adminUser = data;
        state.canEditUsers = ["admin", "ops", "support"].includes(data.role);
        elements.adminUser.textContent = `${data.nickname} (${data.role})`;
        setAuthState(true);
        return true;
    } catch (error) {
        elements.adminUser.textContent = "Not signed in";
        setAuthState(false);
        return false;
    }
}

async function loadSummary() {
    const data = await apiFetch("/api/admin/summary");
    document.getElementById("metricUsers").textContent = formatNumber(data.users_total);
    document.getElementById("metricUsersMeta").textContent = `${formatNumber(data.users_active)} active / ${formatNumber(data.users_suspended)} suspended`;
    document.getElementById("metricQueries").textContent = formatNumber(data.today_queries_logged_in + data.today_queries_anonymous);
    document.getElementById("metricQueriesMeta").textContent = `${formatNumber(data.today_queries_logged_in)} logged-in / ${formatNumber(data.today_queries_anonymous)} anonymous`;
    document.getElementById("metricTokens").textContent = formatNumber(data.today_tokens_used);
    document.getElementById("metricMessages").textContent = formatNumber(data.messages_last_24h);
    document.getElementById("metricCost").textContent = formatCost(data.usage_last_7_days.total_cost);

    const tableBody = document.querySelector("#usageByModelTable tbody");
    tableBody.innerHTML = "";
    const byModel = data.usage_last_7_days.by_model || {};
    Object.entries(byModel).forEach(([model, entry]) => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td class="mono">${escapeHtml(model)}</td>
            <td>${formatNumber(entry.queries)}</td>
            <td>${formatNumber(entry.tokens)}</td>
            <td>${formatCost(entry.cost)}</td>
        `;
        tableBody.appendChild(row);
    });
}

async function loadUsage() {
    const days = Number(elements.usageDays.value || 7);
    const data = await apiFetch(`/api/admin/usage-stats?days=${days}`);
    document.getElementById("usageTotalQueries").textContent = formatNumber(data.total_queries);
    document.getElementById("usageTotalTokens").textContent = formatNumber(data.tokens.total);
    document.getElementById("usageTotalCost").textContent = formatCost(data.total_cost_usd);

    const tableBody = document.querySelector("#usageByDayTable tbody");
    tableBody.innerHTML = "";
    Object.entries(data.by_day || {}).forEach(([day, entry]) => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td class="mono">${escapeHtml(day)}</td>
            <td>${formatNumber(entry.queries)}</td>
            <td>${formatNumber(entry.tokens)}</td>
            <td>${formatCost(entry.cost_usd)}</td>
        `;
        tableBody.appendChild(row);
    });
}

async function loadReliability() {
    const days = Number(elements.reliabilityDays?.value || 7);
    const [health, data] = await Promise.all([
        apiFetch("/api/health"),
        apiFetch(`/api/admin/observability?days=${days}`)
    ]);

    document.getElementById("reliabilityHealth").textContent = health.status || "-";
    document.getElementById("reliabilityHealthMeta").textContent = `Chroma ${health.chroma_connected ? "connected" : "disconnected"} / LLM ${health.llm_configured ? "configured" : "missing"}`;
    document.getElementById("reliabilityP95").textContent = data.p95_latency_ms ? `${formatNumber(data.p95_latency_ms)} ms` : "-";
    document.getElementById("reliabilityLatencyMeta").textContent = `P50 ${data.p50_latency_ms ? `${formatNumber(data.p50_latency_ms)} ms` : "-"} / Avg ${data.avg_latency_ms ? `${formatNumber(data.avg_latency_ms)} ms` : "-"}`;
    document.getElementById("reliabilityCacheRate").textContent = formatPercentage(data.cache_hit_rate);
    document.getElementById("reliabilityCacheMeta").textContent = `${formatNumber(data.total_queries)} queries / ${formatNumber(data.queries_with_latency)} with latency`;
    document.getElementById("reliabilityZeroSource").textContent = formatPercentage(data.zero_source_rate_24h);
    document.getElementById("reliabilitySourceMeta").textContent = `${formatNumber(data.zero_source_answers_24h)} zero-source of ${formatNumber(data.answers_last_24h)} answers`;
    document.getElementById("reliabilitySlowQueries").textContent = formatNumber(data.slow_queries);
    document.getElementById("reliabilitySlowMeta").textContent = `Threshold ${formatNumber(data.slow_query_threshold_ms)} ms`;
    document.getElementById("reliabilityRateLimits").textContent = formatNumber(data.rate_limited_users_today + data.rate_limited_anonymous_today);
    document.getElementById("reliabilityRateLimitMeta").textContent = `${formatNumber(data.rate_limited_users_today)} users / ${formatNumber(data.rate_limited_anonymous_today)} anonymous`;

    const tbody = document.querySelector("#reliabilityDailyTable tbody");
    tbody.innerHTML = "";

    (data.daily || []).forEach(entry => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td class="mono">${escapeHtml(entry.date)}</td>
            <td>${formatNumber(entry.queries)}</td>
            <td>${formatCost(entry.cost_usd)}</td>
            <td>${formatNumber(entry.cached_queries)}</td>
            <td>${formatPercentage(entry.cache_hit_rate)}</td>
            <td>${entry.avg_latency_ms ? `${formatNumber(entry.avg_latency_ms)} ms` : "-"}</td>
            <td>${entry.p95_latency_ms ? `${formatNumber(entry.p95_latency_ms)} ms` : "-"}</td>
        `;
        tbody.appendChild(row);
    });
}

async function loadUsers() {
    const params = new URLSearchParams();
    const search = elements.userSearch.value.trim();
    const status = elements.userStatus.value;
    if (search) {
        params.append("search", search);
    }
    if (status) {
        params.append("status", status);
    }
    const data = await apiFetch(`/api/admin/users?${params.toString()}`);
    const tbody = document.querySelector("#usersTable tbody");
    tbody.innerHTML = "";

    data.forEach(user => {
        const row = document.createElement("tr");
        const statusLabel = user.is_active ? "Active" : "Suspended";
        row.innerHTML = `
            <td class="mono">${user.id}</td>
            <td>${escapeHtml(user.nickname)}</td>
            <td>${escapeHtml(user.email || "-")}</td>
            <td>${escapeHtml(user.role)}</td>
            <td><span class="pill ${user.is_active ? "is-active" : "is-suspended"}">${statusLabel}</span></td>
            <td>
                <input type="number" min="0" max="1000" value="${user.daily_chat_limit}" data-field="limit">
            </td>
            <td>${formatNumber(user.today_usage)}</td>
            <td>
                <label class="field-inline">
                    <input type="checkbox" data-field="active" ${user.is_active ? "checked" : ""}>
                    Active
                </label>
                <button class="ghost-button" data-action="save-user" data-user-id="${user.id}">
                    Save
                </button>
            </td>
        `;
        if (!state.canEditUsers) {
            row.querySelector('[data-action="save-user"]').disabled = true;
        }
        tbody.appendChild(row);
    });
}

async function loadQueries() {
    const params = new URLSearchParams();
    const role = elements.queryRole.value;
    const session = elements.querySession.value.trim();
    const userId = elements.queryUserId.value.trim();
    if (role) {
        params.append("role", role);
    }
    if (session) {
        params.append("session_uuid", session);
    }
    if (userId) {
        params.append("user_id", userId);
    }
    const data = await apiFetch(`/api/admin/queries?${params.toString()}`);
    const tbody = document.querySelector("#queriesTable tbody");
    tbody.innerHTML = "";

    data.forEach(entry => {
        const row = document.createElement("tr");
        row.dataset.messageId = String(entry.id);
        if (state.selectedQueryId === entry.id) {
            row.classList.add("is-selected");
        }
        row.innerHTML = `
            <td class="mono">${escapeHtml(entry.created_at)}</td>
            <td>${escapeHtml(entry.role)}</td>
            <td class="mono">${escapeHtml(entry.session_uuid || "-")}</td>
            <td>${escapeHtml(entry.user_nickname || "-")}<br><span class="muted">${escapeHtml(entry.user_email || "-")}</span></td>
            <td>${escapeHtml(entry.content)}</td>
            <td class="mono">${escapeHtml(entry.model_used || "-")}</td>
            <td>${formatNumber(entry.sources_count)}</td>
            <td><button class="ghost-button" data-action="view-query-detail" data-message-id="${entry.id}">Inspect</button></td>
        `;
        tbody.appendChild(row);
    });
}

function setSelectedQueryRow(messageId) {
    document.querySelectorAll("#queriesTable tbody tr").forEach(row => {
        row.classList.toggle("is-selected", row.dataset.messageId === String(messageId));
    });
}

function closeQueryDetail() {
    state.selectedQueryId = null;
    if (elements.queryDetailPanel) {
        elements.queryDetailPanel.classList.remove("is-open");
    }
    if (elements.queryDetailTitle) {
        elements.queryDetailTitle.textContent = "Investigation Detail";
    }
    if (elements.queryDetailSummary) {
        elements.queryDetailSummary.textContent = "Select a query or answer row to inspect trace metadata.";
    }
    if (elements.queryDetailEmpty) {
        elements.queryDetailEmpty.hidden = false;
    }
    if (elements.queryDetailContent) {
        elements.queryDetailContent.hidden = true;
        elements.queryDetailContent.innerHTML = "";
    }
    setSelectedQueryRow(null);
}

function renderQueryDetail(data) {
    if (!elements.queryDetailPanel || !elements.queryDetailContent || !elements.queryDetailEmpty) {
        return;
    }

    const answer = data.answer || {};
    const query = data.query || {};

    elements.queryDetailPanel.classList.add("is-open");
    elements.queryDetailTitle.textContent = `Session ${data.session_uuid || "-"}`;
    elements.queryDetailSummary.textContent = `Selected message ${data.selected_message_id} • provider ${answer.provider || "-"}`;
    elements.queryDetailEmpty.hidden = true;
    elements.queryDetailContent.hidden = false;
    elements.queryDetailContent.innerHTML = `
        <div class="detail-meta-grid">
            <div class="detail-meta-item">
                <span class="detail-label">User</span>
                <span>${escapeHtml(data.user_nickname || "-")}</span>
                <span class="muted">${escapeHtml(data.user_email || "-")}</span>
            </div>
            <div class="detail-meta-item">
                <span class="detail-label">Model</span>
                <span class="mono">${escapeHtml(answer.model_used || "-")}</span>
            </div>
            <div class="detail-meta-item">
                <span class="detail-label">Provider</span>
                <span class="mono">${escapeHtml(answer.provider || "-")}</span>
            </div>
            <div class="detail-meta-item">
                <span class="detail-label">Response Mode</span>
                <span>${escapeHtml(answer.response_mode || "-")}</span>
            </div>
            <div class="detail-meta-item">
                <span class="detail-label">Latency</span>
                <span>${formatNumber(answer.latency_ms)} ms</span>
            </div>
            <div class="detail-meta-item">
                <span class="detail-label">Tokens</span>
                <span>${formatNumber(answer.tokens_used)}</span>
            </div>
            <div class="detail-meta-item">
                <span class="detail-label">Sources</span>
                <span>${formatNumber(answer.sources_count)}</span>
            </div>
            <div class="detail-meta-item">
                <span class="detail-label">Answer Time</span>
                <span class="mono">${escapeHtml(formatTimestamp(answer.created_at))}</span>
            </div>
        </div>
        <div class="detail-section">
            <h4>Query</h4>
            <div class="detail-block">
                <div class="detail-block-meta mono">${escapeHtml(formatTimestamp(query.created_at))}</div>
                <pre class="detail-pre">${escapeHtml(query.content || "-")}</pre>
            </div>
        </div>
        <div class="detail-section">
            <h4>Answer</h4>
            <div class="detail-block">
                <pre class="detail-pre">${escapeHtml(answer.content || "-")}</pre>
            </div>
        </div>
        <div class="detail-section">
            <h4>Trace</h4>
            <div class="detail-block">
                <pre class="detail-pre detail-json">${escapeHtml(prettyJson(answer.trace_json))}</pre>
            </div>
        </div>
        <div class="detail-section">
            <h4>Sources</h4>
            <div class="detail-block">
                <pre class="detail-pre detail-json">${escapeHtml(prettyJson(answer.sources_json))}</pre>
            </div>
        </div>
    `;
}

async function loadQueryDetail(messageId) {
    state.selectedQueryId = Number(messageId);
    setSelectedQueryRow(messageId);
    if (elements.queryDetailPanel) {
        elements.queryDetailPanel.classList.add("is-open");
    }
    if (elements.queryDetailTitle) {
        elements.queryDetailTitle.textContent = "Loading detail...";
    }
    if (elements.queryDetailSummary) {
        elements.queryDetailSummary.textContent = `Fetching investigation detail for message ${messageId}`;
    }
    if (elements.queryDetailEmpty) {
        elements.queryDetailEmpty.hidden = false;
        elements.queryDetailEmpty.textContent = "Loading...";
    }
    if (elements.queryDetailContent) {
        elements.queryDetailContent.hidden = true;
        elements.queryDetailContent.innerHTML = "";
    }

    try {
        const data = await apiFetch(`/api/admin/queries/${messageId}`);
        renderQueryDetail(data);
        setSelectedQueryRow(messageId);
    } catch (error) {
        if (elements.queryDetailTitle) {
            elements.queryDetailTitle.textContent = "Investigation Detail";
        }
        if (elements.queryDetailSummary) {
            elements.queryDetailSummary.textContent = "Failed to load query detail.";
        }
        if (elements.queryDetailEmpty) {
            elements.queryDetailEmpty.hidden = false;
            elements.queryDetailEmpty.textContent = "Failed to load detail.";
        }
        if (elements.queryDetailContent) {
            elements.queryDetailContent.hidden = true;
            elements.queryDetailContent.innerHTML = "";
        }
    }
}

async function loadAudit() {
    const data = await apiFetch("/api/admin/audit-logs");
    const tbody = document.querySelector("#auditTable tbody");
    tbody.innerHTML = "";

    data.forEach(entry => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td class="mono">${escapeHtml(entry.created_at)}</td>
            <td>${escapeHtml(entry.admin_email || "-")}</td>
            <td class="mono">${escapeHtml(entry.action)}</td>
            <td>${escapeHtml(entry.target_type)} ${escapeHtml(entry.target_id || "")}</td>
            <td class="mono">${escapeHtml(JSON.stringify(entry.before_state || {}))}</td>
            <td class="mono">${escapeHtml(JSON.stringify(entry.after_state || {}))}</td>
        `;
        tbody.appendChild(row);
    });
}

async function handleUserSave(button) {
    const row = button.closest("tr");
    if (!row) {
        return;
    }
    const userId = button.dataset.userId;
    const limitInput = row.querySelector('[data-field="limit"]');
    const activeInput = row.querySelector('[data-field="active"]');
    const payload = {
        daily_chat_limit: Number(limitInput.value),
        is_active: activeInput.checked
    };

    try {
        button.disabled = true;
        await apiFetch(`/api/admin/users/${userId}`, {
            method: "PATCH",
            body: JSON.stringify(payload)
        });
        await loadUsers();
    } catch (error) {
        alert("Failed to update user. Check permissions.");
    } finally {
        button.disabled = false;
    }
}

function bindEvents() {
    navLinks.forEach(link => {
        link.addEventListener("click", () => {
            switchSection(link.dataset.section);
        });
    });

    document.body.addEventListener("click", event => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
            return;
        }
        const action = target.dataset.action;
        if (action === "refresh-dashboard") {
            loadSummary();
        }
        if (action === "refresh-usage") {
            loadUsage();
        }
        if (action === "refresh-reliability") {
            loadReliability();
        }
        if (action === "refresh-users") {
            loadUsers();
        }
        if (action === "refresh-queries") {
            loadQueries();
        }
        if (action === "view-query-detail") {
            loadQueryDetail(target.dataset.messageId);
        }
        if (action === "close-query-detail") {
            closeQueryDetail();
        }
        if (action === "refresh-audit") {
            loadAudit();
        }
        if (action === "save-user") {
            handleUserSave(target);
        }
    });

    elements.refreshAll.addEventListener("click", async () => {
        await Promise.all([loadSummary(), loadUsage(), loadReliability(), loadUsers(), loadQueries(), loadAudit()]);
    });

    if (elements.adminLoginForm) {
        elements.adminLoginForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (!elements.adminEmail || !elements.adminPassword) {
                return;
            }
            const payload = {
                email: elements.adminEmail.value.trim(),
                password: elements.adminPassword.value
            };
            if (!payload.email || !payload.password) {
                return;
            }
            elements.adminLoginStatus.textContent = "Signing in...";
            try {
                await apiFetch("/api/admin/login", {
                    method: "POST",
                    body: JSON.stringify(payload)
                });
                elements.adminLoginStatus.textContent = "Login successful. Loading...";
                await bootstrap();
            } catch (error) {
                elements.adminLoginStatus.textContent = "Login failed. Check credentials.";
            }
        });
    }
}

async function bootstrap() {
    bindEvents();
    const ok = await loadAdminUser();
    if (!ok) {
        return;
    }
    await loadSummary();
    await loadUsage();
    await loadReliability();
    await loadUsers();
    await loadQueries();
    await loadAudit();
}

bootstrap();
