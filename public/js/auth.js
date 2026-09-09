// ---------- Login form ----------
const loginForm = document.getElementById("login-form");
if (loginForm) {
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    const msgBox = document.getElementById("msg");

    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();

      if (res.ok) {
        showMsg(msgBox, data.message, "success");
        window.location.href = data.redirect;
      } else {
        showMsg(msgBox, data.error, "error");
      }
    } catch (err) {
      showMsg(msgBox, "Network error. Please try again.", "error");
    }
  });
}

// ---------- Register form ----------
const registerForm = document.getElementById("register-form");
if (registerForm) {
  registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const full_name = document.getElementById("full_name").value.trim();
    const phone = document.getElementById("phone").value.trim();
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    const msgBox = document.getElementById("msg");

    try {
      const res = await fetch("/api/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name, phone, username, password }),
      });
      const data = await res.json();

      if (res.ok) {
        showMsg(msgBox, data.message + " Redirecting to login...", "success");
        setTimeout(() => (window.location.href = "/login"), 1200);
      } else {
        showMsg(msgBox, data.error, "error");
      }
    } catch (err) {
      showMsg(msgBox, "Network error. Please try again.", "error");
    }
  });
}

// ---------- Logout (used on dashboard/admin pages) ----------
function attachLogout() {
  const btn = document.getElementById("logout-btn");
  if (btn) {
    btn.addEventListener("click", async () => {
      await fetch("/api/logout", { method: "POST" });
      window.location.href = "/login";
    });
  }
}
attachLogout();

function showMsg(box, text, type) {
  if (!box) return;
  box.textContent = text;
  box.className = "msg " + type;
}
