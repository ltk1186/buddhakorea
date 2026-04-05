"use strict";

const state = {
    adminUser: null,
    canEditUsers: false
};

const elements = {
    authStatus: document.getElementById("authStatus"),
    adminUser: document.getElementById("adminUser"),
    noticeBanner: document.getElementById("noticeBanner"),
    refreshAll: document.getElementById("refreshAll"),
    usageDays: document.getElementById("usageDays"),
    userSearch: document.getElementById("userSearch"),
    userStatus: document.getElementById("userStatus"),
    queryRole: document.getElementById("queryRole"),
    querySession: document.getElementById("querySession"),
    queryUserId: document.getElementById("queryUserId"),
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
        row.innerHTML = `
            <td class="mono">${escapeHtml(entry.created_at)}</td>
            <td>${escapeHtml(entry.role)}</td>
            <td class="mono">${escapeHtml(entry.session_uuid || "-")}</td>
            <td>${escapeHtml(entry.user_nickname || "-")}<br><span class="muted">${escapeHtml(entry.user_email || "-")}</span></td>
            <td>${escapeHtml(entry.content)}</td>
            <td class="mono">${escapeHtml(entry.model_used || "-")}</td>
            <td>${formatNumber(entry.sources_count)}</td>
        `;
        tbody.appendChild(row);
    });
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
        if (action === "refresh-users") {
            loadUsers();
        }
        if (action === "refresh-queries") {
            loadQueries();
        }
        if (action === "refresh-audit") {
            loadAudit();
        }
        if (action === "save-user") {
            handleUserSave(target);
        }
    });

    elements.refreshAll.addEventListener("click", async () => {
        await Promise.all([loadSummary(), loadUsage(), loadUsers(), loadQueries(), loadAudit()]);
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
    await loadUsers();
    await loadQueries();
    await loadAudit();
}

bootstrap();
