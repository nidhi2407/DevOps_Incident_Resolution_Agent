// Global State
let rawPodsData = [];
let rawStats = {};
let namespacesList = [];
let autoPollingInterval = null;

document.addEventListener("DOMContentLoaded", () => {
    fetchClusterData();
    // Start Grafana 10-second auto-polling
    autoPollingInterval = setInterval(() => {
        fetchClusterData(false);
    }, 10000);
});

// View Navigation Switcher
function switchView(viewName) {
    document.querySelectorAll(".nav-btn").forEach(btn => btn.classList.remove("active"));
    document.querySelectorAll(".view-panel").forEach(panel => panel.classList.remove("active"));

    document.getElementById(`tab-${viewName}`).classList.add("active");
    document.getElementById(`view-${viewName}`).classList.add("active");
}

// Fetch Cluster Telemetry from FastAPI /pods
async function fetchClusterData(manual = false) {
    try {
        const response = await fetch("/pods");
        if (!response.ok) throw new Error("Failed to fetch pods data");

        const data = await response.json();
        rawPodsData = data.pods || [];
        rawStats = data.stats || {};
        namespacesList = data.namespaces || [];

        updateMetricCards(rawStats);
        updateNamespaceDropdown(namespacesList);
        renderPodsTable();
        renderIncidentsGrid();
    } catch (err) {
        console.error("Cluster telemetry fetch error:", err);
    }
}

// Update Top Metric Cards (Grafana Style)
function updateMetricCards(stats) {
    const healthPct = stats.health_pct !== undefined ? stats.health_pct : 100;
    const totalPods = stats.total_pods || 0;
    const healthyPods = stats.healthy_pods || 0;
    const unhealthyPods = stats.unhealthy_pods || 0;

    const healthValEl = document.getElementById("stat-health-pct");
    const healthFillEl = document.getElementById("stat-health-fill");
    const healthSubEl = document.getElementById("stat-health-subtext");

    healthValEl.textContent = `${healthPct}%`;
    healthFillEl.style.width = `${healthPct}%`;

    if (healthPct < 80) {
        healthFillEl.style.backgroundColor = "var(--color-red)";
        healthValEl.className = "metric-value red-text";
        healthSubEl.textContent = "Cluster degradation detected";
    } else if (healthPct < 95) {
        healthFillEl.style.backgroundColor = "var(--color-amber)";
        healthValEl.className = "metric-value";
        healthSubEl.textContent = "Minor warnings present";
    } else {
        healthFillEl.style.backgroundColor = "var(--color-openai-green)";
        healthValEl.className = "metric-value green-text";
        healthSubEl.textContent = "Cluster running optimally";
    }

    document.getElementById("stat-total-pods").textContent = totalPods;
    document.getElementById("stat-healthy-pods").textContent = healthyPods;
    document.getElementById("stat-unhealthy-pods").textContent = unhealthyPods;
    document.getElementById("incidents-count").textContent = unhealthyPods;
}

// Populate Namespace Filter
function updateNamespaceDropdown(namespaces) {
    const select = document.getElementById("filter-namespace");
    const currentVal = select.value;
    select.innerHTML = '<option value="all">All Namespaces</option>';

    namespaces.forEach(ns => {
        const option = document.createElement("option");
        option.value = ns;
        option.textContent = ns;
        select.appendChild(option);
    });

    select.value = currentVal || "all";
}

// Render Interactive Pod Inventory Table
function renderPodsTable() {
    const search = document.getElementById("search-pods").value.toLowerCase();
    const nsFilter = document.getElementById("filter-namespace").value;
    const statusFilter = document.getElementById("filter-status").value;

    const tbody = document.getElementById("pods-table-body");
    tbody.innerHTML = "";

    const filtered = rawPodsData.filter(pod => {
        const matchesSearch = pod.pod_name.toLowerCase().includes(search) ||
                              pod.namespace.toLowerCase().includes(search) ||
                              (pod.node || "").toLowerCase().includes(search);

        const matchesNs = (nsFilter === "all") || (pod.namespace === nsFilter);

        let matchesStatus = true;
        if (statusFilter === "unhealthy") matchesStatus = !pod.is_healthy;
        else if (statusFilter === "healthy") matchesStatus = pod.is_healthy;
        else if (statusFilter !== "all") matchesStatus = pod.status === statusFilter;

        return matchesSearch && matchesNs && matchesStatus;
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 30px;">No pods matching current filters.</td></tr>`;
        return;
    }

    filtered.forEach(pod => {
        const tr = document.createElement("tr");

        let statusDotClass = "healthy";
        let statusBadgeClass = "healthy";
        if (!pod.is_healthy) {
            if (pod.status === "Pending") {
                statusDotClass = "pending";
                statusBadgeClass = "pending";
            } else {
                statusDotClass = "unhealthy";
                statusBadgeClass = "unhealthy";
            }
        }

        const actionBtnHtml = !pod.is_healthy
            ? `<button class="btn-rca" onclick="openRcaForPod('${pod.pod_name}', '${pod.namespace}', '${pod.status}', \`${escapeStr(pod.alert || pod.pod_name + ' is failing')}\`)">⚡ Analyze RCA</button>`
            : `<button class="btn-view" onclick="openRcaForPod('${pod.pod_name}', '${pod.namespace}', 'Running', 'Pod is healthy and operational.')">Inspect</button>`;

        tr.innerHTML = `
            <td><span class="status-dot ${statusDotClass}"></span></td>
            <td><span class="pod-name-text">${pod.pod_name}</span></td>
            <td><span class="ns-tag">${pod.namespace}</span></td>
            <td><span class="reason-badge ${statusBadgeClass}">${pod.status}</span></td>
            <td>${pod.ready || "1/1"}</td>
            <td><span style="color: ${pod.restarts > 3 ? 'var(--color-red)' : 'inherit'}">${pod.restarts}</span></td>
            <td>${pod.node || "unassigned"}</td>
            <td>${pod.age || "active"}</td>
            <td align="right">${actionBtnHtml}</td>
        `;

        tbody.appendChild(tr);
    });
}

// Render Active Incidents Grid
function renderIncidentsGrid() {
    const container = document.getElementById("incidents-grid-container");
    container.innerHTML = "";

    const unhealthy = rawPodsData.filter(p => !p.is_healthy);
    if (unhealthy.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1/-1; background: var(--bg-card); border: 1px solid var(--border-subtle); padding: 40px; text-align: center; border-radius: 12px; color: var(--text-secondary);">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#10a37f" stroke-width="2" style="margin-bottom: 12px;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                <h3>All Cluster Services Nominal</h3>
                <p style="color: var(--text-muted); font-size: 13px; margin-top: 4px;">No active Kubernetes pod failures or crash loops detected.</p>
            </div>
        `;
        return;
    }

    unhealthy.forEach(pod => {
        const card = document.createElement("div");
        card.className = "incident-card";
        card.innerHTML = `
            <div class="incident-header">
                <div>
                    <span class="reason-badge unhealthy" style="margin-bottom: 6px;">${pod.status}</span>
                    <div class="incident-pod">${pod.pod_name}</div>
                    <div style="font-size: 12px; color: var(--text-muted);">Namespace: ${pod.namespace} • Node: ${pod.node}</div>
                </div>
            </div>
            <div class="incident-body">${pod.alert || pod.status_reason || 'Pod unhealthy'}</div>
            <button class="action-btn" style="width: 100%; justify-content: center; margin-top: 4px;" onclick="openRcaForPod('${pod.pod_name}', '${pod.namespace}', '${pod.status}', \`${escapeStr(pod.alert || pod.pod_name + ' unhealthy')}\`)">
                ⚡ Run OpenAI RAG Root Cause Analysis
            </button>
        `;
        container.appendChild(card);
    });
}

// Run Full AI Cluster Scan (/scan endpoint)
async function scanAndAnalyzeAll() {
    switchView("incidents");
    const container = document.getElementById("incidents-grid-container");
    container.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; padding: 50px;" class="analyzing-state">
            <span class="spinner" style="width: 24px; height: 24px;"></span> Running automated AI diagnosis across all cluster namespaces...
        </div>
    `;

    try {
        const response = await fetch("/scan");
        const data = await response.json();
        const issues = data.detected_issues || [];

        if (issues.length === 0) {
            container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--color-openai-green); padding: 40px;">No unhealthy pods found during cluster scan.</div>`;
            return;
        }

        container.innerHTML = "";
        issues.forEach(issue => {
            const card = document.createElement("div");
            card.className = "incident-card";
            card.innerHTML = `
                <div class="incident-header">
                    <div>
                        <span class="reason-badge unhealthy">${issue.status_reason}</span>
                        <div class="incident-pod" style="margin-top: 6px;">${issue.pod_name}</div>
                        <div style="font-size: 12px; color: var(--text-muted);">Namespace: ${issue.namespace}</div>
                    </div>
                    <span style="font-size: 11px; font-weight: 700; color: var(--color-openai-green); background: rgba(16,163,127,0.1); padding: 2px 8px; border-radius: 4px;">CONFIDENCE: ${issue.confidence}</span>
                </div>
                <div class="markdown-output" style="background: #09090b; padding: 12px; border-radius: 8px; font-size: 12px;">
                    ${marked.parse(issue.rca)}
                </div>
            `;
            container.appendChild(card);
        });
    } catch (err) {
        console.error("Scan error:", err);
        container.innerHTML = `<div style="grid-column: 1/-1; color: var(--color-red); padding: 40px; text-align: center;">Error scanning cluster. Check API connectivity.</div>`;
    }
}

// Open OpenAI Slide-over RCA Drawer
async function openRcaForPod(podName, namespace, statusReason, alertText) {
    document.getElementById("drawer-pod-name").textContent = podName;
    document.getElementById("drawer-namespace-sub").textContent = `Namespace: ${namespace} • Status: ${statusReason}`;
    document.getElementById("drawer-alert-content").textContent = alertText;

    const confidenceBox = document.getElementById("drawer-confidence-box");
    const confidenceVal = document.getElementById("drawer-confidence-val");
    const rcaOutput = document.getElementById("drawer-rca-output");

    confidenceVal.textContent = "ANALYZING...";
    confidenceVal.style.color = "var(--text-muted)";
    rcaOutput.innerHTML = `
        <div class="analyzing-state">
            <span class="spinner"></span> Consulting ChromaDB RAG Vector Store & Groq Llama-3.3-70B...
        </div>
    `;

    document.getElementById("rca-drawer-overlay").classList.add("active");
    document.getElementById("rca-drawer").classList.add("active");

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                alert: alertText,
                pod_name: podName,
                namespace: namespace,
                status_reason: statusReason
            })
        });

        const data = await response.json();

        confidenceVal.textContent = (data.confidence || "MEDIUM").toUpperCase();
        if (data.confidence === "High") confidenceVal.style.color = "var(--color-openai-green)";
        else if (data.confidence === "Medium") confidenceVal.style.color = "var(--color-amber)";
        else confidenceVal.style.color = "var(--color-red)";

        rcaOutput.innerHTML = marked.parse(data.rca || "No RCA generated.");
    } catch (err) {
        rcaOutput.innerHTML = `<div style="color: var(--color-red);">Error generating RCA report: ${err.message}</div>`;
    }
}

function closeRcaDrawer() {
    document.getElementById("rca-drawer-overlay").classList.remove("active");
    document.getElementById("rca-drawer").classList.remove("active");
}

// Chat View Functions
function sendPresetPrompt(text) {
    document.getElementById("chat-input").value = text;
    sendCustomChat();
}

function handleChatKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendCustomChat();
    }
}

async function sendCustomChat() {
    const input = document.getElementById("chat-input");
    const text = input.value.trim();
    if (!text) return;

    input.value = "";

    const chatMessages = document.getElementById("chat-messages");

    // Remove welcome card if present
    const welcomeCard = chatMessages.querySelector(".system-welcome-card");
    if (welcomeCard) welcomeCard.remove();

    // User Message Bubble
    const userBubble = document.createElement("div");
    userBubble.className = "chat-bubble user";
    userBubble.textContent = text;
    chatMessages.appendChild(userBubble);

    // Agent Loading Bubble
    const agentBubble = document.createElement("div");
    agentBubble.className = "chat-bubble agent";
    agentBubble.innerHTML = `<span class="spinner"></span> Analyzing alert trace with LangGraph Agent...`;
    chatMessages.appendChild(agentBubble);

    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ alert: text })
        });

        const data = await response.json();

        agentBubble.innerHTML = `
            <div style="width: 100%;">
                <div style="display: flex; gap: 8px; margin-bottom: 8px;">
                    <span class="reason-badge healthy" style="font-size: 11px;">CONFIDENCE: ${data.confidence || 'HIGH'}</span>
                    ${data.logs_used ? '<span class="ns-tag">Logs Extracted</span>' : ''}
                </div>
                <div class="markdown-output">${marked.parse(data.rca)}</div>
            </div>
        `;
    } catch (err) {
        agentBubble.innerHTML = `<div style="color: var(--color-red);">Error: ${err.message}</div>`;
    }

    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeStr(str) {
    return (str || "").replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, ' ');
}
