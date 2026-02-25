const API = '';

async function loadSummary() {
  const res = await fetch(`${API}/dashboard/summary`);
  if (!res.ok) throw new Error('summary failed');
  return res.json();
}

function kpi(label, value, sub='') {
  return `<article class="kpi"><div class="muted">${label}</div><div class="v">${value}</div><div class="muted">${sub}</div></article>`;
}

function renderKpis(c) {
  document.getElementById('kpis').innerHTML = [
    kpi('Ingest Lag', c.ingest_lag_blocks ?? 'n/a', 'blocks'),
    kpi('Alerts 24h', c.alerts_24h ?? 0),
    kpi('Queue Pressure', c.backlog_pressure ?? 'n/a'),
    kpi('Dead-letter Open', c.dead_letter_open ?? 0),
  ].join('');
}

function sevClass(s){return s==='high'?'high':s==='medium'?'medium':'low'}

function renderHotAlerts(rows=[]) {
  const html = `<table class="table"><thead><tr><th>Severity</th><th>Type</th><th>Address</th><th>Conf</th></tr></thead><tbody>$
{rows.map(r=>`<tr><td><span class="badge ${sevClass(r.severity)}">${r.severity}</span></td><td>${r.type}</td><td>${r.address||''}</td><td>${(r.confidence||0).toFixed(2)}</td></tr>`).join('')}</tbody></table>`;
  document.getElementById('hotAlerts').innerHTML = html;
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

async function refresh() {
  try {
    const data = await loadSummary();
    renderKpis(data.compact || {});
    renderHotAlerts((data.summary||{}).hot_alerts || []);
    renderRows('topTypes', (data.summary||{}).top_alert_types_24h || [], 'type');
    renderRows('topAddresses', (data.summary||{}).top_alert_addresses_24h || [], 'address');
    renderOps(data.summary || {});
    document.getElementById('healthDot').style.background = 'var(--ok)';
    document.getElementById('lastUpdated').textContent = new Date().toISOString();
  } catch (e) {
    document.getElementById('healthDot').style.background = 'var(--crit)';
    document.getElementById('lastUpdated').textContent = `error: ${e.message}`;
  }
}

document.getElementById('refreshBtn').addEventListener('click', refresh);
refresh();
