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
function shortAddr(a=''){ return a ? `${a.slice(0,6)}…${a.slice(-4)}` : ''; }

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
  <td><button class="addr-btn" data-address="${r.address || ''}">${shortAddr(r.address||'')}</button></td>
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
    <div class="row"><span>Address</span><strong>${shortAddr(data.address)}</strong></div>
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

function renderFlowGraph(data, centerAddress){
  const svg = document.getElementById('graphSvg');
  const W = 760, H = 340, cx = W/2, cy = H/2, R = 125;
  const nodes = data.nodes || [];
  const edges = data.edges || [];
  const center = (centerAddress || '').toLowerCase();

  if (!center || nodes.length <= 1) {
    svg.innerHTML = `<text class="g-label" x="20" y="32">No graph data yet. Load an address with neighbors.</text>`;
    document.getElementById('graphMeta').textContent = 'nodes=0 edges=0';
    return;
  }

  const others = nodes.filter(n => (n.id||'').toLowerCase() !== center).slice(0, 14);
  const pos = {};
  pos[center] = {x: cx, y: cy};
  others.forEach((n, i) => {
    const a = (Math.PI * 2 * i) / Math.max(1, others.length);
    pos[n.id.toLowerCase()] = {x: cx + Math.cos(a) * R, y: cy + Math.sin(a) * (R * 0.85)};
  });

  const lines = edges
    .filter(e => pos[(e.src||'').toLowerCase()] && pos[(e.dst||'').toLowerCase()])
    .slice(0, 28)
    .map(e => {
      const s = pos[e.src.toLowerCase()], d = pos[e.dst.toLowerCase()];
      return `<line class="g-link" x1="${s.x}" y1="${s.y}" x2="${d.x}" y2="${d.y}"/>`;
    })
    .join('');

  const circles = Object.entries(pos).map(([id, p]) => {
    const isCenter = id === center;
    return `
      <circle class="g-node ${isCenter ? 'center' : ''}" cx="${p.x}" cy="${p.y}" r="${isCenter ? 16 : 11}" />
      <text class="g-label" x="${p.x + 12}" y="${p.y + 4}">${shortAddr(id)}</text>
    `;
  }).join('');

  svg.innerHTML = `${lines}${circles}`;
  document.getElementById('graphMeta').textContent = `nodes=${nodes.length} edges=${edges.length} center=${shortAddr(centerAddress||'')}`;
}

function renderTaxonomyMap(labelsMap){
  const svg = document.getElementById('taxonomySvg');
  const entries = Object.entries(labelsMap || {});
  if (!entries.length) {
    svg.innerHTML = `<text class="g-label" x="20" y="30">Taxonomy unavailable.</text>`;
    return;
  }

  const W = 760, H = 260;
  const root = {x: 130, y: H/2, label: 'MVP Taxonomy'};
  const yGap = H / (entries.length + 1);
  const nodes = entries.map((e, i) => ({x: 520, y: yGap * (i+1), label: e[0], rule: e[1]?.rule || ''}));

  const lines = nodes.map(n => `<line class="g-link" x1="${root.x+30}" y1="${root.y}" x2="${n.x-26}" y2="${n.y}"/>`).join('');
  const rootNode = `<rect x="${root.x-62}" y="${root.y-18}" width="124" height="36" rx="10" fill="#123064" stroke="#5B8DFF"/>
                    <text class="g-label" x="${root.x-44}" y="${root.y+5}">${root.label}</text>`;
  const leaves = nodes.map(n => `
    <rect x="${n.x-56}" y="${n.y-16}" width="112" height="32" rx="10" fill="#182844" stroke="#3B82F6"/>
    <text class="g-label" x="${n.x-44}" y="${n.y+4}">${n.label}</text>
  `).join('');

  svg.innerHTML = `${lines}${rootNode}${leaves}`;

  const notes = entries.map(([k,v]) => `<div class="row"><span>${k}</span><span class="muted">${v?.rule || ''}</span></div>`).join('');
  document.getElementById('taxonomyMeta').innerHTML = notes;
}

async function loadFlowGraph(address) {
  if (!address) return renderFlowGraph({nodes:[],edges:[]}, '');
  const data = await jfetch(`/graph/neighbors/${address}?limit=30`);
  renderFlowGraph(data, address);
}

async function loadTaxonomy() {
  const data = await jfetch('/labels/taxonomy');
  renderTaxonomyMap(data.labels || {});
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

  const seedAddress = ((summary.summary||{}).hot_alerts||[])[0]?.address || ((summary.summary||{}).top_alert_addresses_24h||[])[0]?.address;
  if (seedAddress) {
    document.getElementById('graphAddress').value = seedAddress;
    await loadFlowGraph(seedAddress);
  } else {
    renderFlowGraph({nodes:[],edges:[]}, '');
  }

  document.getElementById('healthDot').style.background = 'var(--ok)';
  document.getElementById('lastUpdated').textContent = new Date().toISOString();
}

async function applyPreset(name) {
  await jfetch(`/runbook/threshold-presets/${name}`, { method: 'POST' });
  document.getElementById('presetStatus').textContent = `Applied preset: ${name}`;
  await refresh();
}

async function ackAlert(id) { await jfetch(`/alerts/${id}/ack?assignee=ui`, { method: 'POST' }); await refresh(); }
async function resolveAlert(id) { await jfetch(`/alerts/${id}/resolve?assignee=ui`, { method: 'POST' }); await refresh(); }
async function retryFailure(id) { await jfetch(`/runbook/failures/${id}/retry`, { method: 'POST' }); await refresh(); }
async function resolveFailure(id) { await jfetch(`/runbook/failures/${id}/resolve`, { method: 'POST' }); await refresh(); }
async function openRisk(address) { if (!address) return; const data = await jfetch(`/entity/${address}/risk`); renderRisk(data); }

function bindActions() {
  document.getElementById('refreshBtn').addEventListener('click', () => runSafe(refresh));
  document.getElementById('closeDrawer').addEventListener('click', () => document.getElementById('riskDrawer').classList.add('hidden'));
  document.getElementById('graphLoadBtn').addEventListener('click', () => runSafe(() => loadFlowGraph(document.getElementById('graphAddress').value.trim())));

  document.body.addEventListener('click', async (e) => {
    const t = e.target;
    if (t.matches('[data-preset]')) return runSafe(() => applyPreset(t.dataset.preset));
    if (t.matches('.act-ack')) return runSafe(() => ackAlert(t.dataset.id));
    if (t.matches('.act-resolve')) return runSafe(() => resolveAlert(t.dataset.id));
    if (t.matches('.fail-retry')) return runSafe(() => retryFailure(t.dataset.id));
    if (t.matches('.fail-resolve')) return runSafe(() => resolveFailure(t.dataset.id));
    if (t.matches('.addr-btn')) return runSafe(async () => { await openRisk(t.dataset.address); document.getElementById('graphAddress').value = t.dataset.address; await loadFlowGraph(t.dataset.address); });
  });
}

async function runSafe(fn) {
  try { await fn(); }
  catch (e) {
    document.getElementById('healthDot').style.background = 'var(--crit)';
    document.getElementById('lastUpdated').textContent = `error: ${String(e.message || e).slice(0,120)}`;
  }
}

bindActions();
runSafe(async () => {
  await Promise.all([refresh(), loadTaxonomy()]);
});
