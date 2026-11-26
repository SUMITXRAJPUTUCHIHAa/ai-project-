/* LPU Admission Intelligence — App JS (LPU UMS UI)
   Handles: view switching, chat, fee calculator, analytics, rule inspector,
            topic grid, theme toggle, sidebar collapse, bottom nav.
*/
(() => {
'use strict';

// ── Helpers ──────────────────────────────────────────────────────────────────
const $ = (s, ctx = document) => ctx.querySelector(s);
const $$ = (s, ctx = document) => [...ctx.querySelectorAll(s)];
const esc = s => String(s).replace(/[&<>"']/g, c =>
  ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));

// ── Session ───────────────────────────────────────────────────────────────────
let SID = localStorage.getItem('lpu_sid') ||
  (crypto.randomUUID ? crypto.randomUUID().slice(0, 12) : String(Date.now()));
localStorage.setItem('lpu_sid', SID);
let busy = false;
let currentTheme = localStorage.getItem('lpu_theme') || 'light';

// ── API ───────────────────────────────────────────────────────────────────────
async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText || 'Request failed');
  return j;
}
const post = (p, b) => api(p, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(b)
});

// ── View Management ───────────────────────────────────────────────────────────
let activeView = 'home';

function showView(name) {
  activeView = name;
  const isHome = (name || '').toLowerCase() === 'home';
  const homeEl = $('#viewHome');
  const chatEl = $('#viewChat');

  if (homeEl) homeEl.hidden = !isHome;
  if (chatEl) chatEl.hidden = isHome;

  // Sync sidebar nav active state
  $$('.nav-item[data-view]').forEach(el => {
    const isAct = el.dataset.view === name;
    el.classList.toggle('active', isAct);
    el.setAttribute('aria-current', isAct ? 'page' : 'false');
  });

  // Sync bottom nav
  $$('.bnav-item[data-view]').forEach(el => {
    el.classList.toggle('active', el.dataset.view === name);
  });

  // When switching to chat view, greet if empty and focus input
  if (!isHome) {
    const chatMsgContainer = $('#chat');
    if (chatMsgContainer && chatMsgContainer.children.length === 0) {
      appendMessage('ai', '👋 Hello! I am your **LPU Admission Intelligence** companion powered by Groq Cloud. Ask me anything about fees, programmes, eligibility, scholarships, or hostels!');
    }
    const inputEl = $('#input');
    if (inputEl) setTimeout(() => inputEl.focus(), 60);
  }
}

// ── Theme Toggle ──────────────────────────────────────────────────────────────
function applyTheme(theme) {
  currentTheme = theme;
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('lpu_theme', theme);
}

$('#themeToggle')?.addEventListener('click', () => {
  applyTheme(currentTheme === 'light' ? 'dark' : 'light');
});
applyTheme(currentTheme);

// ── Sidebar Collapse ──────────────────────────────────────────────────────────
let sidebarCollapsed = false;
$('#menuToggle')?.addEventListener('click', () => {
  if (window.innerWidth <= 768) {
    document.body.classList.toggle('sidebar-open');
  } else {
    sidebarCollapsed = !sidebarCollapsed;
    document.body.classList.toggle('sidebar-collapsed', sidebarCollapsed);
    $('#menuToggle').setAttribute('aria-expanded', !sidebarCollapsed);
  }
});

// Close sidebar overlay on mobile tap outside
document.addEventListener('click', e => {
  if (window.innerWidth <= 768 && document.body.classList.contains('sidebar-open')) {
    if (!e.target.closest('.sidebar') && !e.target.closest('#menuToggle')) {
      document.body.classList.remove('sidebar-open');
    }
  }
});

// ── Navigation Wiring ─────────────────────────────────────────────────────────
document.addEventListener('click', e => {
  // Nav items (sidebar)
  const navItem = e.target.closest('.nav-item[data-view]');
  if (navItem) { showView(navItem.dataset.view); return; }

  // Bottom nav items
  const bnavItem = e.target.closest('.bnav-item[data-view]');
  if (bnavItem) { showView(bnavItem.dataset.view); return; }

  // "Start Chatting" button
  if (e.target.closest('#btnStartChat') || e.target.closest('#navChat') || e.target.closest('#bnavChat')) {
    showView('chat'); return;
  }

  // New Chat button
  if (e.target.closest('#btnNewChat')) {
    clearChat(); return;
  }

  // Toggle Suggestions Hub
  if (e.target.closest('#btnToggleHub')) {
    const hub = $('#chatOptionsHub');
    if (hub) hub.hidden = !hub.hidden;
    return;
  }

  // Academic Viva & System Architecture Defense
  if (e.target.closest('#btnViva') || e.target.closest('#navViva') || e.target.closest('#btnVivaHome')) {
    openPanel('vivaOverlay');
    return;
  }

  // Chat Home button
  if (e.target.closest('#btnChatHome')) {
    showView('home'); return;
  }

  // Home chat search bar
  if (e.target.closest('#homeChatBtn')) {
    const q = ($('#homeChatInput')?.value || '').trim();
    if (q) {
      if ($('#homeChatInput')) $('#homeChatInput').value = '';
      sendMessage(q);
    }
    return;
  }

  // Quick grid cards / chips → auto-send query
  const dq = e.target.closest('[data-query]');
  if (dq) { sendMessage(dq.dataset.query); return; }

  const qcard = e.target.closest('.quick-card[data-p]');
  if (qcard) { sendMessage(qcard.dataset.p); return; }

  // Dock pills
  const pill = e.target.closest('.pill[data-act]');
  if (pill) { pillAction(pill.dataset.act); return; }

  // Panel close buttons
  const closer = e.target.closest('[data-close]');
  if (closer) {
    const target = $('#' + closer.dataset.close);
    if (target) target.hidden = true;
    return;
  }

  // Panel tab buttons
  const tabBtn = e.target.closest('.tab-btn[data-tab]');
  if (tabBtn) { switchTab(tabBtn); return; }

  const vtabBtn = e.target.closest('.tab-btn[data-vtab]');
  if (vtabBtn) {
    const tabGroup = vtabBtn.closest('.side-panel') || vtabBtn.closest('.panel-overlay');
    if (tabGroup) {
      $$('.tab-btn[data-vtab]', tabGroup).forEach(b => b.classList.toggle('active', b === vtabBtn));
      $$('.vtab-content', tabGroup).forEach(c => {
        const isAct = c.id === vtabBtn.dataset.vtab;
        c.classList.toggle('active', isAct);
        c.hidden = !isAct;
      });
    }
    return;
  }

  // Overlay backdrop click to close
  if (e.target.classList.contains('panel-overlay')) {
    e.target.hidden = true; return;
  }

  // Analytics
  if (e.target.closest('#btnAnalytics') || e.target.closest('#navAnalytics') || e.target.closest('#bnavAnalytics')) {
    openAnalytics(); return;
  }

  // Reset session
  if (e.target.closest('#btnReset')) { resetSession(); return; }

  // Fee calc
  if (e.target.closest('#navFeeCalc') || e.target.closest('#bnavCalc')) {
    openPanel('calcOverlay'); return;
  }

  // Rule inspector
  if (e.target.closest('#navRules') || e.target.closest('#bnavRules')) {
    openRuleInspector(); return;
  }

  // Slot state
  if (e.target.closest('#navSlots')) { openSlotState(); return; }
});

// ── Panel helpers ─────────────────────────────────────────────────────────────
function openPanel(id) {
  const el = $('#' + id);
  if (el) el.hidden = false;
}

function switchTab(btn) {
  const tabGroup = btn.closest('.side-panel') || btn.closest('.panel-overlay');
  if (!tabGroup) return;
  $$('.tab-btn', tabGroup).forEach(b => b.classList.toggle('active', b === btn));
  $$('.tab-content', tabGroup).forEach(c => {
    const isAct = c.id === `tab-${btn.dataset.tab}`;
    c.classList.toggle('active', isAct);
    c.hidden = !isAct;
  });
}

function pillAction(act) {
  if (act === 'calc') openPanel('calcOverlay');
  else if (act === 'inspect') openRuleInspector();
  else if (act === 'slots') openSlotState();
  else if (act === 'home') showView('home');
  else if (act === 'reset') resetSession();
}

// ── Topic Grid ────────────────────────────────────────────────────────────────
const TOPIC_ICONS = {
  fees: '💳', eligibility: '✅', scholarship: '🌟',
  hostel: '🏠', admission: '🎓', documents: '📄',
  programmes: '📚', general: '💡'
};
const TOPIC_SUBS = {
  fees: 'Tuition, exam and hostel fees',
  eligibility: 'Entry requirements by programme',
  scholarship: 'Merit and LPUNEST waivers',
  hostel: 'Rooms, mess and facilities',
  admission: 'Step-by-step procedure',
  documents: 'Mandatory verification docs',
  programmes: 'B.Tech, MBA, BCA and more',
  general: 'LPUNEST dates and eligibility'
};

const QUICK_TOPICS = [
  { id: 'fees',       label: 'Programme Fees',      p: 'What are the fees for BTech CSE?' },
  { id: 'eligibility',label: 'Eligibility',          p: 'Eligibility criteria for BTech admission' },
  { id: 'scholarship',label: 'Scholarships',          p: 'What scholarship slabs are available for BTech?' },
  { id: 'hostel',     label: 'Hostel & Mess',         p: 'Hostel room charges and mess facilities' },
  { id: 'admission',  label: 'How to Apply',          p: 'Step by step admission procedure at LPU' },
  { id: 'documents',  label: 'Documents Required',    p: 'What documents are required for admission?' },
  { id: 'programmes', label: 'Programmes Offered',    p: 'What programmes does LPU offer?' },
  { id: 'general',    label: 'LPUNEST Info',          p: 'Tell me about LPUNEST 2025 registration and dates' }
];

function buildQuickGrid() {
  const grid = $('#quickGrid');
  if (!grid) return;
  grid.innerHTML = QUICK_TOPICS.map(t => `
    <button class="quick-card" data-p="${esc(t.p)}" aria-label="Ask about ${esc(t.label)}">
      <div class="qc-icon">${TOPIC_ICONS[t.id] || '💡'}</div>
      <div class="qc-title">${esc(t.label)}</div>
      <div class="qc-sub">${esc(TOPIC_SUBS[t.id] || '')}</div>
      <svg class="qc-arrow" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
    </button>`).join('');
}

// ── Markdown Renderer ─────────────────────────────────────────────────────────
function renderMarkdown(raw) {
  const lines = esc(raw || '').split('\n');
  let out = '', inList = null;
  const closeList = () => { if (inList) { out += `</${inList}>`; inList = null; } };

  for (let line of lines) {
    if (/^\s*[-*]\s/.test(line)) {
      if (inList !== 'ul') { closeList(); out += '<ul>'; inList = 'ul'; }
      out += `<li>${line.replace(/^\s*[-*]\s/, '')}</li>`;
    } else if (/^\s*\d+\.\s/.test(line)) {
      if (inList !== 'ol') { closeList(); out += '<ol>'; inList = 'ol'; }
      out += `<li>${line.replace(/^\s*\d+\.\s/, '')}</li>`;
    } else if (/^\|(.+)\|$/.test(line)) {
      // Simple table row detection
      closeList();
      const cells = line.split('|').filter((_, i, a) => i > 0 && i < a.length - 1);
      if (cells.some(c => c.trim().startsWith('---'))) continue; // skip header divider
      out += `<div style="display:flex;gap:12px;padding:3px 0;font-size:12.5px;">` +
             cells.map(c => `<span style="flex:1;">${c.trim()}</span>`).join('') +
             `</div>`;
    } else {
      closeList();
      line = line
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g,     '<em>$1</em>')
        .replace(/`(.+?)`/g,       '<code>$1</code>');
      out += line ? `<p>${line}</p>` : '<br>';
    }
  }
  closeList();
  return out;
}

// ── Chat ──────────────────────────────────────────────────────────────────────
function appendMessage(role, text, meta = {}) {
  const chat = $('#chat');
  if (!chat) return;
  const isUser = role === 'user';
  const avatarText = isUser ? 'You' : '🎓';
  const bubbleClass = isUser ? 'msg user' : 'msg ai';
  const contentHTML = isUser ? `<p>${esc(text)}</p>` : renderMarkdown(text);

  let metaHTML = '';
  if (!isUser && meta.confidence !== undefined) {
    const rawConf = meta.confidence;
    const pct = Math.round(rawConf > 1 ? rawConf : rawConf * 100);
    const cls = pct >= 80 ? 'conf-high' : pct >= 50 ? 'conf-med' : 'conf-low';
    metaHTML = `<div class="msg-meta">
      <span class="conf-badge ${cls}">${pct}% confidence</span>
      ${meta.intent ? `<span>Intent: <strong>${esc(meta.intent)}</strong></span>` : ''}
    </div>`;
  }

  // Follow-up suggestions/chips
  let chipsHTML = '';
  if (!isUser && Array.isArray(meta.chips) && meta.chips.length > 0) {
    chipsHTML = `<div class="msg-chips" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;">` +
      meta.chips.map(c => `
        <button class="chip" data-query="${esc(c.prompt || c.label)}" style="font-size:11.5px;padding:5px 12px;">
          ${esc(c.label)}
        </button>`).join('') +
      `</div>`;
  }

  const div = document.createElement('div');
  div.className = bubbleClass;
  div.innerHTML = `
    <div class="msg-avatar">${avatarText}</div>
    <div style="max-width:100%;overflow-x:auto;">
      <div class="msg-bubble">${contentHTML}</div>
      ${metaHTML}
      ${chipsHTML}
    </div>`;
  chat.appendChild(div);

  const scrollContainer = $('#chatScroll');
  if (scrollContainer) {
    scrollContainer.scrollTop = scrollContainer.scrollHeight;
  } else {
    div.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }
}

function appendTyping() {
  const chat = $('#chat');
  if (!chat) return;
  const div = document.createElement('div');
  div.className = 'msg ai';
  div.id = 'typingMsg';
  div.innerHTML = `
    <div class="msg-avatar">🎓</div>
    <div class="msg-bubble">
      <div class="typing-indicator">
        <span></span><span></span><span></span>
      </div>
    </div>`;
  chat.appendChild(div);
  const scrollContainer = $('#chatScroll');
  if (scrollContainer) scrollContainer.scrollTop = scrollContainer.scrollHeight;
}

function removeTyping() {
  const t = $('#typingMsg');
  if (t) t.remove();
}

async function sendMessage(text) {
  text = (text || '').trim();
  if (!text || busy) return;
  busy = true;

  // Switch to chat view
  showView('chat');

  // Hide starter options hub once chat begins
  const hub = $('#chatOptionsHub');
  if (hub) hub.hidden = true;

  appendMessage('user', text);
  appendTyping();

  const sendBtn = $('#send');
  if (sendBtn) sendBtn.disabled = true;

  try {
    const data = await post('/api/chat', { message: text, session_id: SID });
    removeTyping();

    const reply = data.reply || data.answer || data.response || 'No reply received.';
    const confidence = (data.meta && typeof data.meta.confidence === 'number')
      ? data.meta.confidence
      : (typeof data.confidence === 'number' ? data.confidence : undefined);
    const intent = (data.meta && data.meta.intent) || data.intent;

    appendMessage('ai', reply, {
      confidence: confidence,
      intent: intent,
      chips: data.chips
    });
    updateHealthStats();
  } catch (err) {
    removeTyping();
    appendMessage('ai', `⚠️ Connection error: ${esc(err.message)}`);
  } finally {
    busy = false;
    if (sendBtn) sendBtn.disabled = false;
    const inputEl = $('#input');
    if (inputEl) {
      inputEl.value = '';
      adjustTextarea();
      inputEl.focus();
    }
  }
}

// ── Input handling ────────────────────────────────────────────────────────────
function adjustTextarea() {
  const ta = $('#input');
  if (!ta) return;
  ta.style.height = 'auto';
  ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
}

$('#input')?.addEventListener('input', adjustTextarea);
$('#input')?.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage($('#input').value);
  }
});
$('#send')?.addEventListener('click', () => sendMessage($('#input')?.value || ''));

$('#homeChatInput')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    e.preventDefault();
    const q = ($('#homeChatInput')?.value || '').trim();
    if (q) {
      $('#homeChatInput').value = '';
      sendMessage(q);
    }
  }
});

// ── Reset & Clear Chat ────────────────────────────────────────────────────────
async function clearChat() {
  try { await post('/api/reset', { session_id: SID }); } catch {}
  SID = crypto.randomUUID ? crypto.randomUUID().slice(0, 12) : String(Date.now());
  localStorage.setItem('lpu_sid', SID);
  const chat = $('#chat');
  if (chat) chat.innerHTML = '';
  const hub = $('#chatOptionsHub');
  if (hub) hub.hidden = false;
  showView('chat');
}

async function resetSession() {
  try { await post('/api/reset', { session_id: SID }); } catch {}
  SID = crypto.randomUUID ? crypto.randomUUID().slice(0, 12) : String(Date.now());
  localStorage.setItem('lpu_sid', SID);
  const chat = $('#chat');
  if (chat) chat.innerHTML = '';
  const hub = $('#chatOptionsHub');
  if (hub) hub.hidden = false;
  showView('home');
}

// ── Health Stats ──────────────────────────────────────────────────────────────
async function updateHealthStats() {
  try {
    const data = await api('/api/analytics');
    const logged = data.total_queries ?? data.total ?? data.logged ?? 0;
    const rate   = data.recognition_rate ?? data.rate ?? 100;
    const unres  = data.unresolved ?? 0;

    $$('#hLogged').forEach(el => { if (el) el.textContent = String(logged).padStart(2, '0'); });
    $$('#hRate').forEach(el => { if (el) el.textContent = Math.round(rate); });

    const counter = $('#unresolvedCount');
    if (counter) {
      counter.textContent = unres;
      counter.hidden = unres === 0;
    }
  } catch {}
}

// ── Analytics Panel ───────────────────────────────────────────────────────────
async function openAnalytics() {
  openPanel('analyticsOverlay');
  try {
    const data = await api('/api/analytics');
    $('#aTotalQ').textContent   = data.total_queries ?? data.total ?? '—';
    $('#aResolved').textContent = data.resolved ?? '—';
    $('#aUnresolved').textContent = data.unresolved ?? '—';
    $('#aRecRate').textContent  = (data.recognition_rate ?? data.rate ?? '—') + '%';
  } catch {
    $('#aTotalQ').textContent = '—';
  }

  try {
    const logs = await api('/api/analytics?include=logs&limit=20');
    const list = logs.logs || logs.queries || [];
    const qList = $('#queryList');
    if (qList) {
      qList.innerHTML = list.length
        ? list.map(q => `
            <div class="query-item">
              ${q.intent ? `<span class="query-intent">${esc(q.intent)}</span>` : ''}
              <div>${esc(q.query || q.user_query || q.message || '')}</div>
            </div>`).join('')
        : '<p style="color:var(--text-muted);text-align:center;padding:20px">No queries logged yet</p>';
    }
  } catch {}

  try {
    const esc2 = await api('/api/escalations');
    const escList = esc2.escalations || esc2 || [];
    const eList = $('#escalationList');
    if (eList) {
      eList.innerHTML = Array.isArray(escList) && escList.length
        ? escList.map(e => `
            <div class="query-item">
              <span class="query-intent" style="background:rgba(239,68,68,0.1);color:#ef4444">ESCALATED</span>
              <div>${esc(e.user_query || e.query || '')}</div>
              <div style="font-size:11px;color:var(--text-muted);margin-top:4px">${e.status || 'pending'}</div>
            </div>`).join('')
        : '<p style="color:var(--text-muted);text-align:center;padding:20px">No escalations</p>';
    }
  } catch {}
}

// ── Rule Inspector ────────────────────────────────────────────────────────────
async function openRuleInspector() {
  openPanel('ruleOverlay');
  const body = $('#ruleBody');
  if (body) body.textContent = 'Loading rules…';
  try {
    const data = await api('/api/rules');
    const rules = data.rules || data || {};
    if (body) body.textContent = JSON.stringify(rules, null, 2);
  } catch (err) {
    if (body) body.textContent = `Error: ${err.message}`;
  }
}

// ── Slot State ────────────────────────────────────────────────────────────────
async function openSlotState() {
  openPanel('slotOverlay');
  const body = $('#slotBody');
  if (body) body.textContent = 'Loading slot state…';
  try {
    const data = await api('/api/slot-state');
    if (body) body.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    if (body) body.textContent = `Error: ${err.message}`;
  }
}

// ── Fee Calculator ────────────────────────────────────────────────────────────
async function loadFeeCalcData() {
  try {
    const data = await api('/api/topics');
    const topics = data.topics || data || [];
    const prog = $('#cProg');
    if (prog) {
      topics.filter(t => t.fee_per_sem).forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.id || t.programme_id || t.label;
        opt.textContent = t.label || t.name;
        opt.dataset.fee = t.fee_per_sem || 0;
        prog.appendChild(opt);
      });
    }
  } catch {}

  try {
    const data = await api('/api/hostel-tiers');
    const tiers = data.tiers || data || [];
    const hostelSel = $('#cHostel');
    if (hostelSel) {
      tiers.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.annual || t.fee || 0;
        opt.textContent = `${t.type || t.name} — ₹${Number(t.annual || 0).toLocaleString('en-IN')}/yr`;
        hostelSel.appendChild(opt);
      });
    }
  } catch {}
}

$('#calcBtn')?.addEventListener('click', async () => {
  const prog = $('#cProg');
  const pct  = parseInt($('#cPct')?.value || '0', 10);
  const hostel = parseFloat($('#cHostel')?.value || '0');
  const mess = $('#cMess')?.checked;

  try {
    const data = await post('/api/calc-fee', {
      programme: prog?.value,
      scholarship_pct: pct,
      hostel_tier: hostel,
      include_mess: mess
    });
    const result = $('#calcResult');
    if (result) {
      result.hidden = false;
      result.innerHTML = `
        <strong>Fee Breakdown</strong><br>
        Tuition (after scholarship): <strong>₹${Number(data.tuition_annual || 0).toLocaleString('en-IN')}</strong>/yr<br>
        Hostel: <strong>₹${Number(data.hostel_annual || 0).toLocaleString('en-IN')}</strong>/yr<br>
        Mess: <strong>₹${Number(data.mess_annual || 0).toLocaleString('en-IN')}</strong>/yr<br>
        <hr style="border:none;border-top:1px solid var(--border);margin:8px 0">
        <strong>Total: ₹${Number(data.total_annual || 0).toLocaleString('en-IN')}/year</strong>`;
    }
  } catch (err) {
    const result = $('#calcResult');
    if (result) {
      result.hidden = false;
      result.textContent = `Error: ${err.message}`;
    }
  }
});

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  buildQuickGrid();
  updateHealthStats();
  loadFeeCalcData();
  showView('home');

  // Double ann-inner for seamless scroll loop
  const inner = $('#annTicker');
  if (inner && !inner.dataset.looped) {
    inner.innerHTML += inner.innerHTML;
    inner.dataset.looped = 'true';
  }
}

init();

})();
