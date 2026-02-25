const API = '';

const state = {
  summary: null,
  failures: [],
};

async function jfetch(path, options = {}) {
  const res = await fetch(`${API}${path}`, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${path} -> ${res.status} ${text}`);
  }
  return res.json();
}

function kpi(label, value, sub='') {
  return `<article class="kpi"><div class="muted">${label}</div><div class="v">${value}</div><div class="muted">${sub}</div></article>`;
}

function sevClass(s){return s==='high'?'high':s==='medium'?'medium':'low'}

function renderKpis(c) {
  document.getElementById('kpis').innerHTML = [
    kpi('Ingest Lag', c.ingest_lag_blocks ?? 'n/a', 'blocks'),
    kpi('Alerts 24h', c.alerts_24h ?? 0),
    kpi('Queue Pressure', c.backlog_pressure ?? 'n/a'),
    kpi('Dead-letter Open', c.dead_letter_open ?? 0),
  ].join('');
}

function renderRows(id, rows, key='type') {
  document.getElementById(id).innerHTML = rows.map(r => `<div class="row"><span>${r[key]}</span><strong>${r.count}</strong></div>`).join('') || '<p class="muted">No data</p>';
}

function renderOps(summary){
  const q = summary.queue || {};
  const d = summary.dead_letter || {};
  document.getElementById('runbookOps').innerHTML = `
    <div class="row"><span>Queue New</span><strong>${(q.queue_counts||{}).new ?? 0}</strong></div>
    <div class="row"><span>Queue Ack</span><strong>${(q.queue_counts||{}).ack ?? 0}</strong></div>
    <div class="row"><span>Queue Resolved</span><strong>${(q.queue_counts||{}).resolved ?? 0}</strong></div>
    <div class="row"><span>Backlog Pressure</span><strong>${q.backlog_pressure ?? 'n/a'}</strong></div>
    <div class="row"><span>Dead-letter Open</span><strong>${d.open ?? 0}</strong></div>
  `;
}

function renderHotAlerts(rows=[]) {
  const html = `<table class="table"><thead><tr><th>Severity</th><th>Type</th><th>Address</th><th>Conf</th><th>Actions</th></tr></thead><tbody>${
rows.map(r=>`<tr>
  <td><span class="badge ${sevClass(r.severity)}">${r.severity}</span></td>
  <td>${r.type || ''}</td>
  <td><button class="addr-btn" data-address="${r.address || ''}">${r.address || ''}</button></td>
  <td>${(r.confidence||0).toFixed(2)}</td>
  <td class="actions">
    <button class="secondary act-ack" data-id="${r.id}">Ack</button>
    <button class="danger act-resolve" data-id="${r.id}">Resolve</button>
  </td>
</tr>`).join('')
}</tbody></table>`;
  document.getElementById('hotAlerts').innerHTML = html;
}

function renderFailures(rows=[]) {
  const html = `<table class="table"><thead><tr><th>ID</th><th>Range</th><th>Retries</th><th>Status</th><th>Actions</th></tr></thead><tbody>${
rows.map(r=>`<tr>
  <td>${r.id}</td>
  <td>${r.start_block ?? '-'} → ${r.end_block ?? '-'}</td>
  <td>${r.retry_count ?? 0}</td>
  <td>${r.status || ''}</td>
  <td class="actions">
    <button class="secondary fail-retry" data-id="${r.id}">Retry</button>
    <button class="danger fail-resolve" data-id="${r.id}">Resolve</button>
  </td>
</tr><tr><td></td><td colspan="4" class="muted">${(r.error||'').slice(0,180)}</td></tr>`).join('')
}</tbody></table>`;
  document.getElementById('failures').innerHTML = html;
}

function renderRisk(data) {
  const labels = (data.labels || []).slice(0,8).map(l => `<div class="row"><span>${l.label}</span><strong>${(l.confidence||0).toFixed(2)}</strong></div>`).join('') || '<p class="muted">No labels</p>';
  const f = data.factors || {};
  document.getElementById('riskContent').innerHTML = `
    <div class="row"><span>Address</span><strong>${data.address}</strong></div>
    <div class="row"><span>Risk Score</span><strong>${data.risk_score} (${data.band})</strong></div>
    <div class="factor"><span>Label Risk</span><strong>${f.label_risk ?? 0}</strong></div>
    <div class="factor"><span>Alert Risk</span><strong>${f.alert_risk ?? 0}</strong></div>
    <div class="factor"><span>Centrality Risk</span><strong>${f.centrality_risk ?? 0}</strong></div>
    <div class="factor"><span>Flow Risk</span><strong>${f.flow_risk ?? 0}</strong></div>
    <h3 style="margin-top:10px">Top Labels</h3>
    ${labels}
  `;
  document.getElementById('riskDrawer').classList.remove('hidden');
}

async function refresh() {
  const [summary, failures] = await Promise.all([
    jfetch('/dashboard/summary?hot_limit=20'),
    jfetch('/runbook/failures?limit=20'),
  ]);

  state.summary = summary;
  state.failures = failures.failures || [];

  renderKpis(summary.compact || {});
  renderHotAlerts((summary.summary||{}).hot_alerts || []);
  renderRows('topTypes', (summary.summary||{}).top_alert_types_24h || [], 'type');
  renderRows('topAddresses', (summary.summary||{}).top_alert_addresses_24h || [], 'address');
  renderOps(summary.summary || {});
  renderFailures(state.failures);

  document.getElementById('healthDot').style.background = 'var(--ok)';
  document.getElementById('lastUpdated').textContent = new Date().toISOString();
}

async function applyPreset(name) {
  await jfetch(`/runbook/threshold-presets/${name}`, { method: 'POST' });
  document.getElementById('presetStatus').textContent = `Applied preset: ${name}`;
  await refresh();
}

async function ackAlert(id) {
  await jfetch(`/alerts/${id}/ack?assignee=ui`, { method: 'POST' });
  await refresh();
}

async function resolveAlert(id) {
  await jfetch(`/alerts/${id}/resolve?assignee=ui`, { method: 'POST' });
  await refresh();
}

async function retryFailure(id) {
  await jfetch(`/runbook/failures/${id}/retry`, { method: 'POST' });
  await refresh();
}

async function resolveFailure(id) {
  await jfetch(`/runbook/failures/${id}/resolve`, { method: 'POST' });
  await refresh();
}

async function openRisk(address) {
  if (!address) return;
  const data = await jfetch(`/entity/${address}/risk`);
  renderRisk(data);
}

function bindActions() {
  document.getElementById('refreshBtn').addEventListener('click', () => runSafe(refresh));
  document.getElementById('closeDrawer').addEventListener('click', () => document.getElementById('riskDrawer').classList.add('hidden'));

  document.body.addEventListener('click', async (e) => {
    const t = e.target;
    if (t.matches('[data-preset]')) return runSafe(() => applyPreset(t.dataset.preset));
    if (t.matches('.act-ack')) return runSafe(() => ackAlert(t.dataset.id));
    if (t.matches('.act-resolve')) return runSafe(() => resolveAlert(t.dataset.id));
    if (t.matches('.fail-retry')) return runSafe(() => retryFailure(t.dataset.id));
    if (t.matches('.fail-resolve')) return runSafe(() => resolveFailure(t.dataset.id));
    if (t.matches('.addr-btn')) return runSafe(() => openRisk(t.dataset.address));
  });
}

async function runSafe(fn) {
  try {
    await fn();
  } catch (e) {
    document.getElementById('healthDot').style.background = 'var(--crit)';
    document.getElementById('lastUpdated').textContent = `error: ${String(e.message || e).slice(0,120)}`;
  }
}

bindActions();
runSafe(refresh);
