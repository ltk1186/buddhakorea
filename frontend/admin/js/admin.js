"use strict";

const state = {
    adminUser: null,
    canEditUsers: false,
    canReviewQueries: false,
    canViewAudit: false,
    selectedQueryId: null,
    selectedUserId: null,
    selectedDataTable: null,
    eventsBound: false
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
    userDetailPanel: document.getElementById("userDetailPanel"),
    userDetailTitle: document.getElementById("userDetailTitle"),
    userDetailSummary: document.getElementById("userDetailSummary"),
    userDetailEmpty: document.getElementById("userDetailEmpty"),
    userDetailContent: document.getElementById("userDetailContent"),
    queryRole: document.getElementById("queryRole"),
    querySession: document.getElementById("querySession"),
    queryUserId: document.getElementById("queryUserId"),
    queryReviewStatus: document.getElementById("queryReviewStatus"),
    queryDetailPanel: document.getElementById("queryDetailPanel"),
    queryDetailTitle: document.getElementById("queryDetailTitle"),
    queryDetailSummary: document.getElementById("queryDetailSummary"),
    queryDetailEmpty: document.getElementById("queryDetailEmpty"),
    queryDetailContent: document.getElementById("queryDetailContent"),
    dataTableSelect: document.getElementById("dataTableSelect"),
    dataSearch: document.getElementById("dataSearch"),
    dataTableLabel: document.getElementById("dataTableLabel"),
    dataRowsMeta: document.getElementById("dataRowsMeta"),
    dataDetailTitle: document.getElementById("dataDetailTitle"),
    dataDetailSummary: document.getElementById("dataDetailSummary"),
    dataDetailContent: document.getElementById("dataDetailContent"),
    adminLoginForm: document.getElementById("adminLoginForm"),
    adminEmail: document.getElementById("adminEmail"),
    adminPassword: document.getElementById("adminPassword"),
    adminLoginStatus: document.getElementById("adminLoginStatus")
};

const sections = Array.from(document.querySelectorAll(".admin-section"));
const navLinks = Array.from(document.querySelectorAll(".nav-link"));

function formatNumber(value) {
    if (value === null || value === undefined || value === "") {
        return "-";
    }
    return Number(value).toLocaleString("en-US");
}

function formatCost(value) {
    if (value === null || value === undefined || value === "") {
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

function prettyJson(value) {
    if (value === null || value === undefined) {
        return "-";
    }
    return JSON.stringify(value, null, 2);
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

function reviewPill(status) {
    if (!status) {
        return '<span class="pill">Unreviewed</span>';
    }
    const modifier = status === "resolved" ? "is-active" : status === "ignored" ? "is-muted" : "is-warning";
    return `<span class="pill ${modifier}">${escapeHtml(status)}</span>`;
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

function openDetail(panel, titleEl, summaryEl, emptyEl, contentEl, title, summary) {
    if (panel) {
        panel.classList.add("is-open");
    }
    if (titleEl) {
        titleEl.textContent = title;
    }
    if (summaryEl) {
        summaryEl.textContent = summary;
    }
    if (emptyEl) {
        emptyEl.hidden = false;
        emptyEl.textContent = "Loading...";
    }
    if (contentEl) {
        contentEl.hidden = true;
        contentEl.innerHTML = "";
    }
}

function closeUserDetail() {
    state.selectedUserId = null;
    if (elements.userDetailPanel) {
        elements.userDetailPanel.classList.remove("is-open");
    }
    elements.userDetailTitle.textContent = "User Detail";
    elements.userDetailSummary.textContent = "Select a user to inspect identities, sessions, usage, and audit history.";
    elements.userDetailEmpty.hidden = false;
    elements.userDetailEmpty.textContent = "No user selected.";
    elements.userDetailContent.hidden = true;
    elements.userDetailContent.innerHTML = "";
    document.querySelectorAll("#usersTable tbody tr").forEach(row => row.classList.remove("is-selected"));
}

function closeQueryDetail() {
    state.selectedQueryId = null;
    if (elements.queryDetailPanel) {
        elements.queryDetailPanel.classList.remove("is-open");
    }
    elements.queryDetailTitle.textContent = "Investigation Detail";
    elements.queryDetailSummary.textContent = "Select a query or answer row to inspect trace metadata.";
    elements.queryDetailEmpty.hidden = false;
    elements.queryDetailEmpty.textContent = "No query selected.";
    elements.queryDetailContent.hidden = true;
    elements.queryDetailContent.innerHTML = "";
    setSelectedQueryRow(null);
}

async function loadAdminUser() {
    try {
        const data = await apiFetch("/api/admin/me");
        state.adminUser = data;
        state.canEditUsers = ["admin", "ops", "support"].includes(data.role);
        state.canReviewQueries = ["admin", "ops", "support"].includes(data.role);
        state.canViewAudit = ["admin", "ops"].includes(data.role);
        elements.adminUser.textContent = `${data.nickname} (${data.role})`;
        const auditNav = document.querySelector('button[data-section="audit"]');
        if (auditNav) {
            auditNav.hidden = !state.canViewAudit;
        }
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
    const hasLatencyMetrics = Boolean(data.latency_metrics_available);
    const hasCacheMetrics = Boolean(data.cache_metrics_available);
    const hasCostMetrics = Boolean(data.cost_metrics_available);
    const costLabel = hasCostMetrics
        ? `${data.cost_metrics_estimated ? "Estimated" : "Measured"} avg cost/query ${formatCost(data.avg_cost_per_query_usd || 0)}`
        : "Cost sample unavailable";

    document.getElementById("reliabilityHealth").textContent = health.status || "-";
    document.getElementById("reliabilityHealthMeta").textContent = `Chroma ${health.chroma_connected ? "connected" : "disconnected"} / LLM ${health.llm_configured ? "configured" : "missing"} / Source ${data.metrics_source || "-"}`;
    document.getElementById("reliabilityP95").textContent = hasLatencyMetrics && data.p95_latency_ms ? `${formatNumber(data.p95_latency_ms)} ms` : "-";
    document.getElementById("reliabilityLatencyMeta").textContent = hasLatencyMetrics
        ? `P50 ${data.p50_latency_ms ? `${formatNumber(data.p50_latency_ms)} ms` : "-"} / Avg ${data.avg_latency_ms ? `${formatNumber(data.avg_latency_ms)} ms` : "-"} / Sample ${formatNumber(data.queries_with_latency)} answers`
        : "Latency sample unavailable";
    document.getElementById("reliabilityCacheRate").textContent = hasCacheMetrics && data.cache_hit_rate !== null ? formatPercentage(data.cache_hit_rate) : "-";
    document.getElementById("reliabilityCacheMeta").textContent = hasCacheMetrics
        ? `${formatNumber(data.cache_queries_sample)} log queries / ${costLabel}`
        : `Cache sample unavailable / ${costLabel}`;
    document.getElementById("reliabilityZeroSource").textContent = formatPercentage(data.zero_source_rate_24h);
    document.getElementById("reliabilitySourceMeta").textContent = `${formatNumber(data.zero_source_answers_24h)} zero-source of ${formatNumber(data.answers_last_24h)} answers`;
    document.getElementById("reliabilitySlowQueries").textContent = hasLatencyMetrics ? formatNumber(data.slow_queries) : "-";
    document.getElementById("reliabilitySlowMeta").textContent = hasLatencyMetrics ? `Threshold ${formatNumber(data.slow_query_threshold_ms)} ms` : "Latency sample unavailable";
    document.getElementById("reliabilityRateLimits").textContent = formatNumber(data.rate_limited_users_today + data.rate_limited_anonymous_today);
    document.getElementById("reliabilityRateLimitMeta").textContent = `${formatNumber(data.rate_limited_users_today)} users / ${formatNumber(data.rate_limited_anonymous_today)} anonymous`;

    const tbody = document.querySelector("#reliabilityDailyTable tbody");
    tbody.innerHTML = "";
    (data.daily || []).forEach(entry => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td class="mono">${escapeHtml(entry.date)}</td>
            <td>${formatNumber(entry.queries)}</td>
            <td>${entry.cost_usd !== null && entry.cost_usd !== undefined ? formatCost(entry.cost_usd) : "-"}</td>
            <td>${entry.cached_queries !== null && entry.cached_queries !== undefined ? formatNumber(entry.cached_queries) : "-"}</td>
            <td>${entry.cache_hit_rate !== null && entry.cache_hit_rate !== undefined ? formatPercentage(entry.cache_hit_rate) : "-"}</td>
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
        row.dataset.userId = String(user.id);
        if (state.selectedUserId === user.id) {
            row.classList.add("is-selected");
        }
        row.innerHTML = `
            <td class="mono">${user.id}</td>
            <td>${escapeHtml(user.nickname)}</td>
            <td>${escapeHtml(user.email || "-")}</td>
            <td>${escapeHtml(user.role)}</td>
            <td><span class="pill ${user.is_active ? "is-active" : "is-suspended"}">${user.is_active ? "Active" : "Suspended"}</span></td>
            <td><input type="number" min="0" max="1000" value="${user.daily_chat_limit}" data-field="limit"></td>
            <td>${formatNumber(user.today_usage)}</td>
            <td>
                <div class="button-row">
                    <button class="ghost-button" data-action="inspect-user" data-user-id="${user.id}">Inspect</button>
                    <label class="field-inline">
                        <input type="checkbox" data-field="active" ${user.is_active ? "checked" : ""}>
                        Active
                    </label>
                    <button class="ghost-button" data-action="save-user" data-user-id="${user.id}">Save</button>
                </div>
            </td>
        `;
        if (!state.canEditUsers) {
            row.querySelector('[data-action="save-user"]').disabled = true;
            row.querySelector('[data-field="active"]').disabled = true;
            row.querySelector('[data-field="limit"]').disabled = true;
        }
        tbody.appendChild(row);
    });
}

function setSelectedUserRow(userId) {
    document.querySelectorAll("#usersTable tbody tr").forEach(row => {
        row.classList.toggle("is-selected", row.dataset.userId === String(userId));
    });
}

function renderUserDetail(data) {
    elements.userDetailPanel.classList.add("is-open");
    elements.userDetailTitle.textContent = `${data.user.nickname} (#${data.user.id})`;
    elements.userDetailSummary.textContent = `${data.user.role} • ${data.user.is_active ? "active" : "suspended"} • limit ${data.user.daily_chat_limit}`;
    elements.userDetailEmpty.hidden = true;
    elements.userDetailContent.hidden = false;

    const identities = (data.social_accounts || []).map(identity => `
        <tr>
            <td>${escapeHtml(identity.provider)}</td>
            <td class="mono">${escapeHtml(identity.provider_user_id)}</td>
            <td>${escapeHtml(identity.provider_email || "-")}</td>
            <td class="mono">${escapeHtml(formatTimestamp(identity.last_used_at))}</td>
        </tr>
    `).join("");

    const sessions = (data.recent_sessions || []).map(session => `
        <tr>
            <td><button class="link-button" data-action="inspect-session" data-session-uuid="${escapeHtml(session.session_uuid)}">${escapeHtml(session.session_uuid)}</button></td>
            <td>${escapeHtml(session.title || "-")}</td>
            <td>${formatNumber(session.message_count)}</td>
            <td class="mono">${escapeHtml(formatTimestamp(session.last_message_at))}</td>
        </tr>
    `).join("");

    const usage = (data.recent_usage || []).map(entry => `
        <tr>
            <td class="mono">${escapeHtml(entry.usage_date)}</td>
            <td>${formatNumber(entry.chat_count)}</td>
            <td>${formatNumber(entry.tokens_used)}</td>
        </tr>
    `).join("");

    const audit = (data.recent_audit || []).map(entry => `
        <tr>
            <td class="mono">${escapeHtml(formatTimestamp(entry.created_at))}</td>
            <td>${escapeHtml(entry.admin_email || "-")}</td>
            <td>${escapeHtml(entry.action)}</td>
        </tr>
    `).join("");

    elements.userDetailContent.innerHTML = `
        <div class="detail-meta-grid">
            <div class="detail-meta-item"><span class="detail-label">Email</span><span>${escapeHtml(data.user.email || "-")}</span></div>
            <div class="detail-meta-item"><span class="detail-label">Today Usage</span><span>${formatNumber(data.user.today_usage)}</span></div>
            <div class="detail-meta-item"><span class="detail-label">Last Login</span><span class="mono">${escapeHtml(formatTimestamp(data.user.last_login))}</span></div>
            <div class="detail-meta-item"><span class="detail-label">Created</span><span class="mono">${escapeHtml(formatTimestamp(data.user.created_at))}</span></div>
        </div>
        <div class="detail-section">
            <h4>Linked Identities</h4>
            <div class="table-scroll"><table class="data-table compact-table"><thead><tr><th>Provider</th><th>User ID</th><th>Email</th><th>Last Used</th></tr></thead><tbody>${identities || '<tr><td colspan="4" class="muted">No linked identities.</td></tr>'}</tbody></table></div>
        </div>
        <div class="detail-section">
            <h4>Recent Sessions</h4>
            <div class="table-scroll"><table class="data-table compact-table"><thead><tr><th>Session</th><th>Title</th><th>Messages</th><th>Last Message</th></tr></thead><tbody>${sessions || '<tr><td colspan="4" class="muted">No recent sessions.</td></tr>'}</tbody></table></div>
        </div>
        <div class="detail-section">
            <h4>Usage (14d)</h4>
            <div class="table-scroll"><table class="data-table compact-table"><thead><tr><th>Date</th><th>Chats</th><th>Tokens</th></tr></thead><tbody>${usage || '<tr><td colspan="3" class="muted">No usage rows.</td></tr>'}</tbody></table></div>
        </div>
        <div class="detail-section">
            <h4>Recent Audit</h4>
            <div class="table-scroll"><table class="data-table compact-table"><thead><tr><th>Time</th><th>Admin</th><th>Action</th></tr></thead><tbody>${audit || '<tr><td colspan="3" class="muted">No audit rows.</td></tr>'}</tbody></table></div>
        </div>
    `;
}

async function loadUserDetail(userId) {
    state.selectedUserId = Number(userId);
    setSelectedUserRow(userId);
    openDetail(elements.userDetailPanel, elements.userDetailTitle, elements.userDetailSummary, elements.userDetailEmpty, elements.userDetailContent, "Loading user...", `Fetching user ${userId}`);
    try {
        const data = await apiFetch(`/api/admin/users/${userId}`);
        renderUserDetail(data);
        setSelectedUserRow(userId);
    } catch (error) {
        elements.userDetailTitle.textContent = "User Detail";
        elements.userDetailSummary.textContent = "Failed to load user detail.";
        elements.userDetailEmpty.hidden = false;
        elements.userDetailEmpty.textContent = "Failed to load detail.";
        elements.userDetailContent.hidden = true;
        elements.userDetailContent.innerHTML = "";
    }
}

async function loadQueries() {
    const params = new URLSearchParams();
    const role = elements.queryRole.value;
    const session = elements.querySession.value.trim();
    const userId = elements.queryUserId.value.trim();
    const reviewStatus = elements.queryReviewStatus.value;
    if (role) {
        params.append("role", role);
    }
    if (session) {
        params.append("session_uuid", session);
    }
    if (userId) {
        params.append("user_id", userId);
    }
    if (reviewStatus) {
        params.append("review_status", reviewStatus);
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
            <td class="mono">${escapeHtml(formatTimestamp(entry.created_at))}</td>
            <td>${escapeHtml(entry.role)}</td>
            <td class="mono">${escapeHtml(entry.session_uuid || "-")}</td>
            <td>${escapeHtml(entry.user_nickname || "-")}<br><span class="muted">${escapeHtml(entry.user_email || "-")}</span></td>
            <td>${escapeHtml(entry.content)}</td>
            <td class="mono">${escapeHtml(entry.model_used || "-")}</td>
            <td>${formatNumber(entry.sources_count)}</td>
            <td>${reviewPill(entry.review_status)}</td>
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

function renderSessionTimeline(session) {
    if (!session) {
        return '<div class="muted">No session timeline.</div>';
    }
    const rows = (session.messages || []).map(message => `
        <tr>
            <td class="mono">${escapeHtml(formatTimestamp(message.created_at))}</td>
            <td>${escapeHtml(message.role)}</td>
            <td>${escapeHtml(message.content)}</td>
            <td class="mono">${escapeHtml(message.provider || "-")}</td>
            <td>${reviewPill(message.review_status)}</td>
        </tr>
    `).join("");
    return `
        <div class="detail-block">
            <div class="detail-block-meta mono">${escapeHtml(session.session_uuid)} • ${formatNumber(session.message_count)} messages</div>
            <div class="table-scroll">
                <table class="data-table compact-table">
                    <thead>
                        <tr><th>Time</th><th>Role</th><th>Content</th><th>Provider</th><th>Review</th></tr>
                    </thead>
                    <tbody>${rows || '<tr><td colspan="5" class="muted">No session messages.</td></tr>'}</tbody>
                </table>
            </div>
        </div>
    `;
}

function renderReviewEditor(detail) {
    const review = detail.review || {};
    const targetId = detail.review_target_message_id;
    const disabled = state.canReviewQueries ? "" : "disabled";
    return `
        <div class="detail-block">
            <div class="detail-form-grid">
                <label>
                    <span class="detail-label">Status</span>
                    <select id="queryReviewEditorStatus" ${disabled}>
                        <option value="open" ${review.status === "open" ? "selected" : ""}>Open</option>
                        <option value="resolved" ${review.status === "resolved" ? "selected" : ""}>Resolved</option>
                        <option value="ignored" ${review.status === "ignored" ? "selected" : ""}>Ignored</option>
                    </select>
                </label>
                <label>
                    <span class="detail-label">Reason</span>
                    <select id="queryReviewEditorReason" ${disabled}>
                        <option value="">None</option>
                        <option value="bad_answer" ${review.reason === "bad_answer" ? "selected" : ""}>bad_answer</option>
                        <option value="hallucination" ${review.reason === "hallucination" ? "selected" : ""}>hallucination</option>
                        <option value="missing_source" ${review.reason === "missing_source" ? "selected" : ""}>missing_source</option>
                        <option value="bad_source" ${review.reason === "bad_source" ? "selected" : ""}>bad_source</option>
                        <option value="abuse" ${review.reason === "abuse" ? "selected" : ""}>abuse</option>
                        <option value="other" ${review.reason === "other" ? "selected" : ""}>other</option>
                    </select>
                </label>
                <label class="detail-span-2">
                    <span class="detail-label">Note</span>
                    <textarea id="queryReviewEditorNote" rows="4" ${disabled}>${escapeHtml(review.note || "")}</textarea>
                </label>
            </div>
            <div class="button-row top-gap">
                <button class="primary-button" data-action="save-query-review" data-message-id="${targetId}" ${disabled}>Save Review</button>
                <span class="muted">Target message ${escapeHtml(String(targetId || "-"))}</span>
            </div>
        </div>
    `;
}

function renderQueryDetail(detail, sessionDetail) {
    const answer = detail.answer || {};
    const query = detail.query || {};

    elements.queryDetailPanel.classList.add("is-open");
    elements.queryDetailTitle.textContent = `Session ${detail.session_uuid || "-"}`;
    elements.queryDetailSummary.textContent = `Selected message ${detail.selected_message_id} • provider ${answer.provider || "-"} • review target ${detail.review_target_message_id || "-"}`;
    elements.queryDetailEmpty.hidden = true;
    elements.queryDetailContent.hidden = false;
    elements.queryDetailContent.innerHTML = `
        <div class="detail-meta-grid">
            <div class="detail-meta-item">
                <span class="detail-label">User</span>
                <span>${escapeHtml(detail.user_nickname || "-")}</span>
                <span class="muted">${escapeHtml(detail.user_email || "-")}</span>
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
                <span class="detail-label">Review</span>
                <span>${detail.review ? reviewPill(detail.review.status) : reviewPill(null)}</span>
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
            <h4>Review</h4>
            ${renderReviewEditor(detail)}
        </div>
        <div class="detail-section">
            <h4>Session Timeline</h4>
            ${renderSessionTimeline(sessionDetail)}
        </div>
        <div class="detail-section">
            <h4>Trace</h4>
            <div class="detail-block"><pre class="detail-pre detail-json">${escapeHtml(prettyJson(answer.trace_json))}</pre></div>
        </div>
        <div class="detail-section">
            <h4>Sources</h4>
            <div class="detail-block"><pre class="detail-pre detail-json">${escapeHtml(prettyJson(answer.sources_json))}</pre></div>
        </div>
    `;
}

async function loadQueryDetail(messageId) {
    state.selectedQueryId = Number(messageId);
    setSelectedQueryRow(messageId);
    openDetail(elements.queryDetailPanel, elements.queryDetailTitle, elements.queryDetailSummary, elements.queryDetailEmpty, elements.queryDetailContent, "Loading detail...", `Fetching investigation detail for message ${messageId}`);

    try {
        const detail = await apiFetch(`/api/admin/queries/${messageId}`);
        let sessionDetail = null;
        if (detail.session_uuid) {
            sessionDetail = await apiFetch(`/api/admin/sessions/${detail.session_uuid}`);
        }
        renderQueryDetail(detail, sessionDetail);
        setSelectedQueryRow(messageId);
    } catch (error) {
        elements.queryDetailTitle.textContent = "Investigation Detail";
        elements.queryDetailSummary.textContent = "Failed to load query detail.";
        elements.queryDetailEmpty.hidden = false;
        elements.queryDetailEmpty.textContent = "Failed to load detail.";
        elements.queryDetailContent.hidden = true;
        elements.queryDetailContent.innerHTML = "";
    }
}

async function saveQueryReview(messageId) {
    const statusEl = document.getElementById("queryReviewEditorStatus");
    const reasonEl = document.getElementById("queryReviewEditorReason");
    const noteEl = document.getElementById("queryReviewEditorNote");
    if (!statusEl || !reasonEl || !noteEl) {
        return;
    }
    await apiFetch(`/api/admin/queries/${messageId}/review`, {
        method: "PATCH",
        body: JSON.stringify({
            status: statusEl.value,
            reason: reasonEl.value || null,
            note: noteEl.value.trim() || null
        })
    });
    await Promise.all([loadQueries(), loadQueryDetail(state.selectedQueryId || messageId), loadAudit()]);
}

async function loadAudit() {
    const data = await apiFetch("/api/admin/audit-logs");
    const tbody = document.querySelector("#auditTable tbody");
    tbody.innerHTML = "";
    data.forEach(entry => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td class="mono">${escapeHtml(formatTimestamp(entry.created_at))}</td>
            <td>${escapeHtml(entry.admin_email || "-")}</td>
            <td class="mono">${escapeHtml(entry.action)}</td>
            <td>${escapeHtml(entry.target_type)} ${escapeHtml(entry.target_id || "")}</td>
            <td class="mono">${escapeHtml(JSON.stringify(entry.before_state || {}))}</td>
            <td class="mono">${escapeHtml(JSON.stringify(entry.after_state || {}))}</td>
        `;
        tbody.appendChild(row);
    });
}

async function loadDataTables() {
    const tables = await apiFetch("/api/admin/data/tables");
    elements.dataTableSelect.innerHTML = "";
    tables.forEach(table => {
        const option = document.createElement("option");
        option.value = table.name;
        option.textContent = table.label;
        elements.dataTableSelect.appendChild(option);
    });
    if (!state.selectedDataTable && tables.length > 0) {
        state.selectedDataTable = tables[0].name;
        elements.dataTableSelect.value = state.selectedDataTable;
    }
}

function renderDataRows(data) {
    const thead = document.querySelector("#dataRowsTable thead");
    const tbody = document.querySelector("#dataRowsTable tbody");
    const rows = data.rows || [];
    const headers = rows[0] ? Object.keys(rows[0]) : [];
    thead.innerHTML = `<tr>${headers.map(header => `<th>${escapeHtml(header)}</th>`).join("")}</tr>`;
    tbody.innerHTML = rows.map(row => `
        <tr>${headers.map(header => {
            const value = row[header];
            if (value && typeof value === "object") {
                return `<td class="mono">${escapeHtml(JSON.stringify(value))}</td>`;
            }
            return `<td>${escapeHtml(String(value ?? "-"))}</td>`;
        }).join("")}</tr>
    `).join("") || `<tr><td class="muted" colspan="${Math.max(headers.length, 1)}">No rows.</td></tr>`;
}

function renderDataSchema(data) {
    const rows = (data.columns || []).map(column => `
        <tr>
            <td class="mono">${escapeHtml(column.name)}</td>
            <td>${escapeHtml(column.type)}</td>
            <td>${column.nullable ? "yes" : "no"}</td>
            <td>${column.primary_key ? "yes" : "no"}</td>
        </tr>
    `).join("");
    elements.dataDetailTitle.textContent = data.table.label;
    elements.dataDetailSummary.textContent = data.table.description;
    elements.dataDetailContent.innerHTML = `
        <div class="detail-section">
            <h4>Schema</h4>
            <div class="table-scroll">
                <table class="data-table compact-table">
                    <thead><tr><th>Name</th><th>Type</th><th>Nullable</th><th>PK</th></tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        </div>
        <div class="detail-section">
            <h4>Searchable Columns</h4>
            <div class="detail-block"><pre class="detail-pre detail-json">${escapeHtml(prettyJson(data.table.searchable_columns))}</pre></div>
        </div>
    `;
}

async function loadDataExplorer() {
    const table = elements.dataTableSelect.value || state.selectedDataTable;
    if (!table) {
        return;
    }
    state.selectedDataTable = table;
    const search = elements.dataSearch.value.trim();
    const [schema, rows] = await Promise.all([
        apiFetch(`/api/admin/data/tables/${table}/schema`),
        apiFetch(`/api/admin/data/tables/${table}/rows?${new URLSearchParams(search ? { search } : {}).toString()}`)
    ]);
    elements.dataTableLabel.textContent = `${schema.table.label} Rows`;
    elements.dataRowsMeta.textContent = `${formatNumber(rows.total)} matching rows • read-only whitelist explorer`;
    renderDataSchema(schema);
    renderDataRows(rows);
}

async function handleUserSave(button) {
    const row = button.closest("tr");
    if (!row) {
        return;
    }
    const userId = button.dataset.userId;
    const limitInput = row.querySelector('[data-field="limit"]');
    const activeInput = row.querySelector('[data-field="active"]');
    try {
        button.disabled = true;
        await apiFetch(`/api/admin/users/${userId}`, {
            method: "PATCH",
            body: JSON.stringify({
                daily_chat_limit: Number(limitInput.value),
                is_active: activeInput.checked
            })
        });
        await Promise.all([loadUsers(), loadAudit()]);
        if (state.selectedUserId === Number(userId)) {
            await loadUserDetail(userId);
        }
    } catch (error) {
        alert("Failed to update user. Check permissions.");
    } finally {
        button.disabled = false;
    }
}

function bindEvents() {
    if (state.eventsBound) {
        return;
    }
    state.eventsBound = true;

    navLinks.forEach(link => {
        link.addEventListener("click", () => {
            switchSection(link.dataset.section);
        });
    });

    document.body.addEventListener("click", async event => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
            return;
        }
        const action = target.dataset.action;
        if (action === "refresh-dashboard") {
            await loadSummary();
        } else if (action === "refresh-usage") {
            await loadUsage();
        } else if (action === "refresh-reliability") {
            await loadReliability();
        } else if (action === "refresh-users") {
            await loadUsers();
        } else if (action === "inspect-user") {
            await loadUserDetail(target.dataset.userId);
        } else if (action === "close-user-detail") {
            closeUserDetail();
        } else if (action === "refresh-queries") {
            await loadQueries();
        } else if (action === "view-query-detail") {
            await loadQueryDetail(target.dataset.messageId);
        } else if (action === "close-query-detail") {
            closeQueryDetail();
        } else if (action === "save-query-review") {
            await saveQueryReview(target.dataset.messageId);
        } else if (action === "refresh-audit") {
            await loadAudit();
        } else if (action === "save-user") {
            await handleUserSave(target);
        } else if (action === "inspect-session") {
            switchSection("queries");
            elements.querySession.value = target.dataset.sessionUuid || "";
            await loadQueries();
        } else if (action === "refresh-data") {
            await loadDataExplorer();
        }
    });

    elements.refreshAll.addEventListener("click", async () => {
        const tasks = [loadSummary(), loadUsage(), loadReliability(), loadUsers(), loadQueries(), loadDataExplorer()];
        if (state.canViewAudit) {
            tasks.push(loadAudit());
        }
        await Promise.all(tasks);
    });

    elements.dataTableSelect?.addEventListener("change", async () => {
        state.selectedDataTable = elements.dataTableSelect.value;
        await loadDataExplorer();
    });

    if (elements.adminLoginForm) {
        elements.adminLoginForm.addEventListener("submit", async event => {
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
    await loadDataTables();
    await loadSummary();
    await loadUsage();
    await loadReliability();
    await loadUsers();
    await loadQueries();
    await loadDataExplorer();
    if (state.canViewAudit) {
        await loadAudit();
    }
}

bootstrap();
