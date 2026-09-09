let currentFilter = "All";

document.querySelectorAll(".filter-bar button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".filter-bar button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentFilter = btn.dataset.filter;
    renderAlerts();
  });
});

let allAlerts = [];

async function loadStats() {
  const res = await fetch("/api/stats");
  const stats = await res.json();
  document.getElementById("stat-total").textContent = stats.total;
  document.getElementById("stat-pending").textContent = stats.pending;
  document.getElementById("stat-resolved").textContent = stats.resolved;
}

async function loadAllAlerts() {
  const res = await fetch("/api/all-alerts");
  allAlerts = await res.json();
  renderAlerts();
}

function renderAlerts() {
  const list = document.getElementById("all-alerts-list");
  const filtered =
    currentFilter === "All" ? allAlerts : allAlerts.filter((a) => a.status === currentFilter);

  if (!filtered.length) {
    list.innerHTML = '<div class="empty-state">No alerts in this category.</div>';
    return;
  }

  list.innerHTML = filtered
    .map((a) => {
      const isSos = a.message && a.message.startsWith("SOS:");
      const mapLink =
        a.latitude !== null && a.longitude !== null
          ? `<a href="https://www.google.com/maps?q=${a.latitude},${a.longitude}" target="_blank" rel="noopener">View location on map</a>`
          : "No location data";

      return `
      <div class="alert-card status-${a.status}">
        <div class="alert-card-top">
          <div>
            <span class="alert-type-tag">${a.alert_type}</span>
            ${isSos ? '<span class="alert-type-tag sos-tag">SOS</span>' : ""}
          </div>
          <span class="status-badge ${a.status}">${a.status}</span>
        </div>
        ${a.message ? `<div class="alert-message">${escapeHtml(a.message)}</div>` : ""}
        <div class="alert-meta">
          From: ${escapeHtml(a.full_name)} (${escapeHtml(a.username)}) · ${escapeHtml(a.phone || "no phone")}<br>
          Sent: ${new Date(a.created_at).toLocaleString()} · ${mapLink}
        </div>
        <div class="alert-actions">
          ${a.status !== "Acknowledged" ? `<button class="btn btn-secondary" onclick="updateStatus(${a.alert_id}, 'Acknowledged')">Acknowledge</button>` : ""}
          ${a.status !== "Resolved" ? `<button class="btn btn-primary" style="margin:0;width:auto" onclick="updateStatus(${a.alert_id}, 'Resolved')">Mark Resolved</button>` : ""}
        </div>
      </div>
    `;
    })
    .join("");
}

async function updateStatus(alertId, status) {
  try {
    const res = await fetch("/api/update-status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ alert_id: alertId, status }),
    });
    if (!res.ok) {
      const data = await res.json();
      window.alert(data.error || "Could not update this alert.");
      return;
    }
    loadAllAlerts();
    loadStats();
  } catch (_) {
    window.alert("Network error. Please try again.");
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

loadStats();
loadAllAlerts();
// Poll every 10s for a "near real-time" dashboard
setInterval(() => {
  loadStats();
  loadAllAlerts();
}, 10000);
