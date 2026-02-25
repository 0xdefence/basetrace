const API = '';

const store = {
  state: {
    activePanel: 'overview',
    summary: null,
    failures: [],
    taxonomy: {},
    graph: { nodes: [], edges: [], center: '' },
    graphView: { minTx: 1, direction: 'both', scale: 1 },
  },
  set(patch) { this.state = { ...this.state, ...patch }; renderApp(); },
};

const panelMeta = {
  overview: { title: 'Overview', subtitle: 'Core operations dashboard' },
  flow: { title: 'Flow Graph', subtitle: 'Address neighbors and flow links' },
  taxonomy: { title: 'Taxonomy', subtitle: 'MVP label mapping and rules' },
  failures: { title: 'Failures', subtitle: 'Dead-letter queue operations' },
};

async function jfetch(path, options = {}) {
  const res = await fetch(`${API}${path}`, options);
  if (!res.ok) throw new Error(`${path} -> ${res.status} ${await res.text()}`);
  return res.json();
}

const shortAddr = (a = '') => (a ? `${a.slice(0, 6)}…${a.slice(-4)}` : '');
const sevClass = (s) => (s === 'high' ? 'high' : s === 'medium' ? 'medium' : 'low');

function showPanel(name) {
  document.querySelectorAll('.panel-view').forEach((el) => el.classList.remove('active'));
  document.querySelector(`#panel-${name}`)?.classList.add('active');
  document.querySelectorAll('.nav-btn').forEach((el) => el.classList.toggle('active', el.dataset.panel === name));
  const meta = panelMeta[name] || panelMeta.overview;
  document.getElementById('panelTitle').textContent = meta.title;
  document.getElementById('panelSubtitle').textContent = meta.subtitle;
}

function renderKpis() {
  const c = store.state.summary?.compact || {};
  const kpi = (label, value, sub = '') => `<article class="kpi"><div class="muted">${label}</div><div class="v">${value}</div><div class="muted">${sub}</div></article>`;
  document.getElementById('kpis').innerHTML = [
    kpi('Ingest Lag', c.ingest_lag_blocks ?? 'n/a', 'blocks'),
    kpi('Alerts 24h', c.alerts_24h ?? 0),
    kpi('Queue Pressure', c.backlog_pressure ?? 'n/a'),
    kpi('Dead-letter Open', c.dead_letter_open ?? 0),
  ].join('');
}

function renderOverview() {
  const s = store.state.summary?.summary || {};
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

function renderFailuresPanel() {
  const rows = store.state.failures || [];
  document.getElementById('failures').innerHTML = `<table class="table"><thead><tr><th>ID</th><th>Range</th><th>Retries</th><th>Status</th><th>Actions</th></tr></thead><tbody>${rows
    .map((r) => `<tr><td>${r.id}</td><td>${r.start_block ?? '-'} → ${r.end_block ?? '-'}</td><td>${r.retry_count ?? 0}</td><td>${r.status || ''}</td><td class="actions"><button class="secondary fail-retry" data-id="${r.id}">Retry</button><button class="danger fail-resolve" data-id="${r.id}">Resolve</button></td></tr><tr><td></td><td colspan="4" class="muted">${(r.error || '').slice(0, 160)}</td></tr>`)
    .join('')}</tbody></table>`;

  const topAddr = store.state.summary?.summary?.top_alert_addresses_24h || [];
  document.getElementById('topAddresses').innerHTML = topAddr.map((r) => `<div class="row"><span>${r.address}</span><strong>${r.count}</strong></div>`).join('') || '<p class="muted">No data</p>';
}

function filteredGraph() {
  const { nodes, edges, center } = store.state.graph;
  const { minTx, direction } = store.state.graphView;
  const c = (center || '').toLowerCase();
  const es = (edges || []).filter((e) => {
    const txOk = (e.tx_count || 0) >= minTx;
    const dirOk = direction === 'both' || (direction === 'out' && e.src?.toLowerCase() === c) || (direction === 'in' && e.dst?.toLowerCase() === c);
    return txOk && dirOk;
  });
  const used = new Set([c]);
  es.forEach((e) => { used.add((e.src || '').toLowerCase()); used.add((e.dst || '').toLowerCase()); });
  return { center: c, nodes: (nodes || []).filter((n) => used.has((n.id || '').toLowerCase())), edges: es };
}

function renderFlowGraph() {
  const svg = document.getElementById('graphSvg');
  const { scale } = store.state.graphView;
  const { nodes, edges, center } = filteredGraph();
  if (!center || nodes.length <= 1) {
    svg.setAttribute('viewBox', `0 0 760 340`);
    svg.innerHTML = `<text class="g-label" x="20" y="32">No graph data yet. Load an address with neighbors.</text>`;
    document.getElementById('graphMeta').textContent = 'nodes=0 edges=0';
    return;
  }

  const baseW = 760, baseH = 340;
  const w = baseW / scale, h = baseH / scale;
  svg.setAttribute('viewBox', `${(baseW - w) / 2} ${(baseH - h) / 2} ${w} ${h}`);

  const cx = 380, cy = 170, R = 125;
  const pos = { [center]: { x: cx, y: cy } };
  const others = nodes.filter((n) => n.id.toLowerCase() !== center).slice(0, 16);
  others.forEach((n, i) => {
    const a = (Math.PI * 2 * i) / Math.max(1, others.length);
    pos[n.id.toLowerCase()] = { x: cx + Math.cos(a) * R, y: cy + Math.sin(a) * (R * 0.85) };
  });

  const lines = edges.filter((e) => pos[e.src.toLowerCase()] && pos[e.dst.toLowerCase()]).slice(0, 40).map((e) => {
    const s = pos[e.src.toLowerCase()], d = pos[e.dst.toLowerCase()];
    return `<line class="g-link" x1="${s.x}" y1="${s.y}" x2="${d.x}" y2="${d.y}"/>`;
  }).join('');

  const circles = Object.entries(pos).map(([id, p]) => `
    <circle class="g-node ${id === center ? 'center' : ''} g-click" data-node="${id}" cx="${p.x}" cy="${p.y}" r="${id === center ? 16 : 11}"/>
    <text class="g-label" x="${p.x + 12}" y="${p.y + 4}">${shortAddr(id)}</text>`).join('');

  svg.innerHTML = `${lines}${circles}`;
  document.getElementById('graphMeta').textContent = `nodes=${nodes.length} edges=${edges.length} center=${shortAddr(center)} minTx=${store.state.graphView.minTx} dir=${store.state.graphView.direction} zoom=${scale.toFixed(2)}x`;
}

function renderTaxonomy() {
  const labelsMap = store.state.taxonomy || {};
  const svg = document.getElementById('taxonomySvg');
  const entries = Object.entries(labelsMap);
  if (!entries.length) {
    svg.innerHTML = `<text class="g-label" x="20" y="30">Taxonomy unavailable.</text>`;
    return;
  }
  const root = { x: 130, y: 130, label: 'MVP Taxonomy' };
  const yGap = 260 / (entries.length + 1);
  const nodes = entries.map((e, i) => ({ x: 520, y: yGap * (i + 1), label: e[0] }));
  svg.innerHTML = `${nodes.map((n) => `<line class="g-link" x1="${root.x + 30}" y1="${root.y}" x2="${n.x - 26}" y2="${n.y}"/>`).join('')}
    <rect x="68" y="112" width="124" height="36" rx="10" fill="#123064" stroke="#5B8DFF"/>
    <text class="g-label" x="86" y="134">${root.label}</text>
    ${nodes.map((n) => `<rect x="${n.x - 56}" y="${n.y - 16}" width="112" height="32" rx="10" fill="#182844" stroke="#3B82F6"/><text class="g-label" x="${n.x - 44}" y="${n.y + 4}">${n.label}</text>`).join('')}`;
  document.getElementById('taxonomyMeta').innerHTML = entries.map(([k, v]) => `<div class="row"><span>${k}</span><span class="muted">${v?.rule || ''}</span></div>`).join('');
}

function renderApp() {
  showPanel(store.state.activePanel);
  renderKpis();
  renderOverview();
  renderFailuresPanel();
  renderFlowGraph();
  renderTaxonomy();
}

async function loadGraph(address) {
  const a = (address || '').trim();
  if (!a) return;
  const g = await jfetch(`/graph/neighbors/${a}?limit=40`);
  store.set({ graph: { ...g, center: a.toLowerCase() }, activePanel: 'flow' });
}

async function openRisk(address) {
  const risk = await jfetch(`/entity/${address}/risk`);
  const f = risk.factors || {};
  document.getElementById('riskContent').innerHTML = `<div class="row"><span>Address</span><strong>${shortAddr(risk.address)}</strong></div><div class="row"><span>Risk Score</span><strong>${risk.risk_score} (${risk.band})</strong></div><div class="factor"><span>Label</span><strong>${f.label_risk ?? 0}</strong></div><div class="factor"><span>Alert</span><strong>${f.alert_risk ?? 0}</strong></div><div class="factor"><span>Centrality</span><strong>${f.centrality_risk ?? 0}</strong></div><div class="factor"><span>Flow</span><strong>${f.flow_risk ?? 0}</strong></div>`;
  document.getElementById('riskDrawer').classList.remove('hidden');
}

async function refreshAll() {
  const [summary, failures, taxonomy] = await Promise.all([
    jfetch('/dashboard/summary?hot_limit=20'),
    jfetch('/runbook/failures?limit=20'),
    jfetch('/labels/taxonomy'),
  ]);
  const seed = (summary.summary?.hot_alerts || [])[0]?.address || '';
  let graph = store.state.graph;
  if (seed && !graph.center) {
    const g = await jfetch(`/graph/neighbors/${seed}?limit=40`);
    graph = { ...g, center: seed.toLowerCase() };
    document.getElementById('graphAddress').value = seed;
  }
  store.set({ summary, failures: failures.failures || [], taxonomy: taxonomy.labels || {}, graph });
  document.getElementById('healthDot').style.background = 'var(--ok)';
  document.getElementById('lastUpdated').textContent = new Date().toISOString();
  document.getElementById('statusBar').textContent = `lag=${summary.compact?.ingest_lag_blocks ?? 'n/a'} | dead-letter=${summary.compact?.dead_letter_open ?? 0}`;
}

async function runSafe(fn) {
  try { await fn(); }
  catch (e) {
    document.getElementById('healthDot').style.background = 'var(--crit)';
    document.getElementById('lastUpdated').textContent = `error: ${String(e.message || e).slice(0, 120)}`;
  }
}

function bind() {
  document.getElementById('refreshBtn').addEventListener('click', () => runSafe(refreshAll));
  document.getElementById('closeDrawer').addEventListener('click', () => document.getElementById('riskDrawer').classList.add('hidden'));

  document.getElementById('panelNav').addEventListener('click', (e) => {
    const b = e.target.closest('.nav-btn'); if (!b) return; store.set({ activePanel: b.dataset.panel });
  });

  document.getElementById('graphLoadBtn').addEventListener('click', () => runSafe(() => loadGraph(document.getElementById('graphAddress').value)));
  document.getElementById('graphLoadKnownBtn').addEventListener('click', () => runSafe(async () => {
    const known = ['0x4200000000000000000000000000000000000010', '0x4200000000000000000000000000000000000007', '0x4200000000000000000000000000000000000011'];
    for (const a of known) { try { await loadGraph(a); document.getElementById('graphAddress').value = a; return; } catch {} }
  }));

  document.getElementById('graphApplyFiltersBtn').addEventListener('click', () => {
    const minTx = Number(document.getElementById('graphMinTx').value || 1);
    const direction = document.getElementById('graphDirection').value;
    store.set({ graphView: { ...store.state.graphView, minTx: Math.max(0, minTx), direction } });
  });
  document.getElementById('graphZoomInBtn').addEventListener('click', () => store.set({ graphView: { ...store.state.graphView, scale: Math.min(2.5, store.state.graphView.scale + 0.2) } }));
  document.getElementById('graphZoomOutBtn').addEventListener('click', () => store.set({ graphView: { ...store.state.graphView, scale: Math.max(0.8, store.state.graphView.scale - 0.2) } }));
  document.getElementById('graphResetBtn').addEventListener('click', () => store.set({ graphView: { minTx: 1, direction: 'both', scale: 1 } }));

  document.body.addEventListener('click', (e) => runSafe(async () => {
    const t = e.target;
    if (t.matches('[data-preset]')) { await jfetch(`/runbook/threshold-presets/${t.dataset.preset}`, { method: 'POST' }); document.getElementById('presetStatus').textContent = `Applied preset: ${t.dataset.preset}`; return refreshAll(); }
    if (t.matches('.act-ack')) { await jfetch(`/alerts/${t.dataset.id}/ack?assignee=ui`, { method: 'POST' }); return refreshAll(); }
    if (t.matches('.act-resolve')) { await jfetch(`/alerts/${t.dataset.id}/resolve?assignee=ui`, { method: 'POST' }); return refreshAll(); }
    if (t.matches('.fail-retry')) { await jfetch(`/runbook/failures/${t.dataset.id}/retry`, { method: 'POST' }); return refreshAll(); }
    if (t.matches('.fail-resolve')) { await jfetch(`/runbook/failures/${t.dataset.id}/resolve`, { method: 'POST' }); return refreshAll(); }
    if (t.matches('.addr-btn')) { const address = t.dataset.address; if (address) { await openRisk(address); await loadGraph(address); } }
    if (t.matches('.g-click')) { const address = t.dataset.node; if (address) await openRisk(address); }
  }));
}

bind();
runSafe(refreshAll);
