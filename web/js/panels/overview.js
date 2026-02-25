import { sevClass, shortAddr } from '../api/client.js';

export function renderKpis(summary) {
  const c = summary?.compact || {};
  const kpi = (label, value, sub = '') => `<article class="kpi"><div class="muted">${label}</div><div class="v">${value}</div><div class="muted">${sub}</div></article>`;
  document.getElementById('kpis').innerHTML = [
    kpi('Ingest Lag', c.ingest_lag_blocks ?? 'n/a', 'blocks'),
    kpi('Alerts 24h', c.alerts_24h ?? 0),
    kpi('Queue Pressure', c.backlog_pressure ?? 'n/a'),
    kpi('Dead-letter Open', c.dead_letter_open ?? 0),
  ].join('');
}

export function renderOverview(summary) {
  const s = summary?.summary || {};
  const hot = s.hot_alerts || [];
  document.getElementById('hotAlerts').innerHTML = `<table class="table"><thead><tr><th>Severity</th><th>Type</th><th>Address</th><th>Conf</th><th>Actions</th></tr></thead><tbody>${hot
    .map((r) => `<tr><td><span class="badge ${sevClass(r.severity)}">${r.severity}</span></td><td>${r.type || ''}</td><td><button class="addr-btn" data-address="${r.address || ''}">${shortAddr(r.address || '')}</button></td><td>${(r.confidence || 0).toFixed(2)}</td><td class="actions"><button class="secondary act-ack" data-id="${r.id}">Ack</button><button class="danger act-resolve" data-id="${r.id}">Resolve</button></td></tr>`)
    .join('')}</tbody></table>`;

  const q = s.queue || {}, d = s.dead_letter || {};
  document.getElementById('runbookOps').innerHTML = `
    <div class="row"><span>Queue New</span><strong>${(q.queue_counts || {}).new ?? 0}</strong></div>
    <div class="row"><span>Queue Ack</span><strong>${(q.queue_counts || {}).ack ?? 0}</strong></div>
    <div class="row"><span>Queue Resolved</span><strong>${(q.queue_counts || {}).resolved ?? 0}</strong></div>
    <div class="row"><span>Backlog Pressure</span><strong>${q.backlog_pressure ?? 'n/a'}</strong></div>
    <div class="row"><span>Dead-letter Open</span><strong>${d.open ?? 0}</strong></div>`;
}
