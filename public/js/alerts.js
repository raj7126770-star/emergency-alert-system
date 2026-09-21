let selectedType = null;
let currentCoords = { lat: null, lng: null };

const typeButtons = document.querySelectorAll(".type-btn");
typeButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    typeButtons.forEach((b) => b.classList.remove("selected"));
    btn.classList.add("selected");
    selectedType = btn.dataset.type;
  });
});

// Grab geolocation as soon as the page loads
const locStatus = document.getElementById("location-status");
const refreshLocationButton = document.getElementById("refresh-location-btn");
const shareLocationButton = document.getElementById("share-location-btn");
if (navigator.geolocation && window.isSecureContext) {
  locStatus.textContent = "Detecting your location...";
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      currentCoords.lat = pos.coords.latitude;
      currentCoords.lng = pos.coords.longitude;
      locStatus.textContent = `Location captured (${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)})`;
      locStatus.className = "location-status ok";
    },
    () => {
      locStatus.textContent = "Location unavailable — alert will be sent without coordinates.";
      locStatus.className = "location-status err";
    }
  );
} else {
  locStatus.textContent = "Geolocation not supported by this browser.";
  locStatus.className = "location-status err";
}

function requestFreshLocation() {
  if (!navigator.geolocation) {
    locStatus.textContent = "Geolocation is not supported by this browser.";
    locStatus.className = "location-status err";
    return Promise.resolve(false);
  }
  if (!window.isSecureContext) {
    locStatus.textContent = "Location requires HTTPS (or localhost). Open this site securely and try again.";
    locStatus.className = "location-status err";
    return Promise.resolve(false);
  }

  locStatus.textContent = "Getting your current location...";
  locStatus.className = "location-status";
  refreshLocationButton.disabled = true;
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        currentCoords.lat = pos.coords.latitude;
        currentCoords.lng = pos.coords.longitude;
        locStatus.textContent = `Location captured (${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)})`;
        locStatus.className = "location-status ok";
        refreshLocationButton.disabled = false;
        resolve(true);
      },
      (error) => {
        const messages = {
          1: "Location permission was blocked. Allow location access in your browser, then try again.",
          2: "Your location is unavailable. Check GPS, Wi-Fi, or mobile data and try again.",
          3: "Location request timed out. Please try again.",
        };
        locStatus.textContent = messages[error.code] || "Could not get your location. Please try again.";
        locStatus.className = "location-status err";
        refreshLocationButton.disabled = false;
        resolve(false);
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
    );
  });
}

refreshLocationButton.addEventListener("click", requestFreshLocation);

// Shares only the current GPS position.  Unlike Send Emergency Alert, this
// does not create an SOS case; the backend stores it in location_shares.
shareLocationButton.addEventListener("click", async () => {
  const msgBox = document.getElementById("sos-msg");
  shareLocationButton.disabled = true;
  const foundLocation = await requestFreshLocation();
  if (!foundLocation) {
    shareLocationButton.disabled = false;
    showMsg(msgBox, "Location was not shared because it could not be captured.", "error");
    return;
  }

  try {
    const res = await fetch("/api/location", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ latitude: currentCoords.lat, longitude: currentCoords.lng }),
    });
    const data = await res.json();
    showMsg(msgBox, res.ok ? "Location shared with responders." : (data.error || "Could not share location."), res.ok ? "success" : "error");
  } catch (_) {
    showMsg(msgBox, "Network error. Please try again.", "error");
  } finally {
    shareLocationButton.disabled = false;
  }
});

if (!window.isSecureContext) {
  locStatus.textContent = "Location requires HTTPS (or localhost). Open this site securely and try again.";
  locStatus.className = "location-status err";
}

// Submit emergency alert
const sosForm = document.getElementById("sos-form");
sosForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const msgBox = document.getElementById("sos-msg");
  const message = document.getElementById("message").value.trim();

  if (!selectedType) {
    showMsg(msgBox, "Please select an emergency type.", "error");
    return;
  }

  const result = await sendAlert(selectedType, message);

  if (result.ok) {
    showMsg(msgBox, result.data.message, "success");
    document.getElementById("message").value = "";
    typeButtons.forEach((b) => b.classList.remove("selected"));
    selectedType = null;
    loadMyAlerts();
  } else {
    showMsg(msgBox, result.error, "error");
  }
});

// A direct SOS uses the existing "Other" category so it works with both new
// and existing databases, while its message lets responders identify it at once.
const quickSosButton = document.getElementById("quick-sos-btn");
const quickSosLabel = quickSosButton.querySelector(".quick-sos-label");
quickSosButton.addEventListener("click", async () => {
  const msgBox = document.getElementById("quick-sos-msg");
  if (!window.confirm("Send an SOS alert now?")) return;

  quickSosButton.disabled = true;
  quickSosButton.classList.add("sending");
  quickSosLabel.textContent = "Sending SOS...";

  const result = await sendAlert("Other", "SOS: Immediate assistance requested.");
  quickSosButton.disabled = false;
  quickSosButton.classList.remove("sending");
  quickSosLabel.textContent = "Send SOS now";

  if (result.ok) {
    showMsg(msgBox, "SOS sent. Responders have been notified.", "success");
    loadMyAlerts();
  } else {
    showMsg(msgBox, result.error, "error");
  }
});

async function sendAlert(alertType, message) {
  // Refresh immediately before sending so the alert contains the latest
  // available location. The alert still sends if location is unavailable.
  await requestFreshLocation();
  try {
    const res = await fetch("/api/send-alert", {  // past kar denaa
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        alert_type: alertType,
        name:"raj kumar",
        message,
        location:{
          latitude :currentCoords.lat,
          longitude:currentCoords.lng
        }
      }),
    });
    const data = await res.json();

    if(data.success === true){
      alert("email are send");
    }
    console.log(data);

    // res ==== result of API
    return res.ok
      ? { ok: true, data }
      : { ok: false, error: data.error || "Failed to send alert" };
  } catch (_) {
    return { ok: false, error: "Network error. Please try again." };
  }
}

// Load this user's alert history
async function loadMyAlerts() {
  const list = document.getElementById("my-alerts-list");
  const res = await fetch("/api/my-alerts");
  const alerts = await res.json();

  if (!alerts.length) {
    list.innerHTML = '<div class="empty-state">No alerts sent yet. Stay safe!</div>';
    return;
  }

  list.innerHTML = alerts
    .map(
      (a) => `
    <div class="alert-card status-${a.status}">
      <div class="alert-card-top">
        <div>
          <span class="alert-type-tag">${a.alert_type}</span>
        </div>
        <span class="status-badge ${a.status}">${a.status}</span>
      </div>
      ${a.message ? `<div class="alert-message">${escapeHtml(a.message)}</div>` : ""}
      <div class="alert-meta">Sent: ${new Date(a.created_at).toLocaleString()}</div>
    </div>
  `
    )
    .join("");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function showMsg(box, text, type) {
  box.textContent = text;
  box.className = "msg " + type;
}

loadMyAlerts();
// Refresh every 15s in case status changes
setInterval(loadMyAlerts, 15000);
