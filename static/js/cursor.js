// ═══════════════════════════════════════════════
// DevForge — cursor.js
// Handles: cursor, theme, sidebar, clock, notifications
// ═══════════════════════════════════════════════

// ── Custom Cursor (desktop only) ───────────────
const cursor = document.getElementById('cursor');
const ring   = document.getElementById('cursorRing');
if (cursor && ring && !('ontouchstart' in window)) {
  let mx = 0, my = 0, rx = 0, ry = 0;
  document.addEventListener('mousemove', e => {
    mx = e.clientX; my = e.clientY;
    cursor.style.left = (mx - 4) + 'px';
    cursor.style.top  = (my - 4) + 'px';
  });
  (function animRing() {
    rx += (mx - rx) * 0.18;
    ry += (my - ry) * 0.18;
    ring.style.left = (rx - 16) + 'px';
    ring.style.top  = (ry - 16) + 'px';
    requestAnimationFrame(animRing);
  })();
  const hoverEls = 'a,button,[onclick],.nav-item,.project-card,.task-card,.cal-day,.note-item,.event-pill';
  document.querySelectorAll(hoverEls).forEach(el => {
    el.addEventListener('mouseenter', () => {
      cursor.style.transform = 'scale(1.8)';
      ring.style.transform = 'scale(1.3)';
      ring.style.borderColor = 'var(--accent)';
    });
    el.addEventListener('mouseleave', () => {
      cursor.style.transform = 'scale(1)';
      ring.style.transform = 'scale(1)';
      ring.style.borderColor = '';
    });
  });
} else if (cursor && ring) {
  // Hide cursor elements on touch devices
  cursor.style.display = 'none';
  ring.style.display = 'none';
}

// ── Theme persistence ──────────────────────────
const savedTheme = localStorage.getItem('df-theme') || 'dark';
document.documentElement.setAttribute('data-theme', savedTheme);
document.querySelectorAll('.theme-swatch').forEach(sw => {
  sw.classList.toggle('active', sw.dataset.theme === savedTheme);
  sw.addEventListener('click', () => {
    const t = sw.dataset.theme;
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem('df-theme', t);
    document.querySelectorAll('.theme-swatch').forEach(s => s.classList.remove('active'));
    sw.classList.add('active');
  });
});

// ── Mobile sidebar ─────────────────────────────
const mobileBtn     = document.getElementById('mobileMenuBtn');
const sidebar       = document.getElementById('sidebar');
const mobileOverlay = document.getElementById('mobileOverlay');
if (mobileBtn && sidebar) {
  mobileBtn.addEventListener('click', () => {
    sidebar.classList.toggle('mobile-open');
    if (mobileOverlay) mobileOverlay.classList.toggle('show');
  });
}
if (mobileOverlay) {
  mobileOverlay.addEventListener('click', () => {
    if (sidebar) sidebar.classList.remove('mobile-open');
    mobileOverlay.classList.remove('show');
  });
}

// ── Notification panel ─────────────────────────
const notifPanel = document.getElementById('notifPanel');
const notifBtn   = document.getElementById('notifBtn');
const notifClose = document.getElementById('notifClose');
if (notifPanel && notifBtn) {
  notifBtn.addEventListener('click', e => {
    e.stopPropagation();
    notifPanel.classList.toggle('open');
  });
  if (notifClose) {
    notifClose.addEventListener('click', () => notifPanel.classList.remove('open'));
  }
  document.addEventListener('click', e => {
    if (notifPanel.classList.contains('open') &&
        !notifPanel.contains(e.target) &&
        !notifBtn.contains(e.target)) {
      notifPanel.classList.remove('open');
    }
  });
}

// ── Real-time clock (AM/PM, updates every second) ──
function updateClocks() {
  const now  = new Date();
  const h    = now.getHours();
  const m    = now.getMinutes();
  const s    = now.getSeconds();
  const ampm = h >= 12 ? 'PM' : 'AM';
  const h12  = h % 12 || 12;
  const pad  = n => String(n).padStart(2, '0');
  const time12   = `${pad(h12)}:${pad(m)} ${ampm}`;
  const timeFull = `${pad(h12)}<span style="opacity:.5">:</span>${pad(m)}<span class="clock-seconds"><span style="opacity:.4">:</span>${pad(s)}</span> <span style="font-size:.55em;opacity:.7">${ampm}</span>`;
  const dateStr  = now.toLocaleDateString('en-US', {weekday:'long',year:'numeric',month:'long',day:'numeric'});
  const greeting = h < 12 ? 'morning' : h < 17 ? 'afternoon' : 'evening';

  document.querySelectorAll('.clock-display').forEach(el => el.textContent = time12);
  document.querySelectorAll('.clock-time-full').forEach(el => el.innerHTML = timeFull);
  document.querySelectorAll('.clock-date-full').forEach(el => el.textContent = dateStr);
  document.querySelectorAll('.time-of-day').forEach(el => el.textContent = greeting);
}
updateClocks();
setInterval(updateClocks, 1000);

// ── Browser notifications (with de-duplication) ─
const _notifiedEvents = new Set();
function checkBrowserNotifications() {
  if (Notification.permission !== 'granted') return;
  const events = window.__events || [];
  const now    = new Date();
  events.forEach(ev => {
    const dateStr = ev.event_date || ev.date;
    const timeStr = ev.event_time || ev.time;
    if (!dateStr || !timeStr || !ev.notify) return;
    const evKey = `${ev.id || ev.title}-${dateStr}`;
    if (_notifiedEvents.has(evKey)) return;
    const evDt = new Date(`${dateStr}T${timeStr}`);
    const diff  = evDt - now;
    // Fire if event is 15 min away (with 2 min window to avoid repeat fires)
    if (diff > 0 && diff < 15 * 60 * 1000 && diff > 13 * 60 * 1000) {
      const mins = Math.round(diff / 60000);
      _notifiedEvents.add(evKey);
      new Notification(`⏰ Upcoming: ${ev.title}`, {
        body: `Starts in ${mins} minute${mins !== 1 ? 's' : ''}!`,
        icon: '/static/icon.png',
        tag: evKey,
      });
    }
  });
}

// Request notification permission on first load (won't spam)
if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
  // Only request if user has events with notify=true
  const hasNotifyEvents = (window.__events || []).some(e => e.notify);
  if (hasNotifyEvents) Notification.requestPermission();
}
if (typeof Notification !== 'undefined') {
  checkBrowserNotifications();
  setInterval(checkBrowserNotifications, 60 * 1000);
}
