const API = '';

const store = {
  state: {
    activePanel: 'overview',
    summary: null,
    failures: [],
    taxonomy: {},
    graph: { nodes: [], edges: [], center: '' },
    graphView: { minTx: 1, direction: 'both' },
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

function toast(message, kind = 'ok') {
  const host = document.getElementById('toastHost');
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.textContent = message;
  host.appendChild(el);
  setTimeout(() => el.remove(), 2800);
}

function setBusy(on) {
  document.querySelectorAll('button').forEach((b) => { b.disabled = on; });
}

function setLoadingState(on) {
  ['kpis', 'hotAlerts', 'runbookOps', 'failures', 'topAddresses'].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle('skeleton', on);
  });
}

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

// ─── D3 force-directed graph ────────────────────────────────────────────────
let _graphSim = null;

function stopSim() {
  if (_graphSim) { _graphSim.stop(); _graphSim = null; }
}

function renderFlowGraph() {
  const svgEl = document.getElementById('graphSvg');
  const { center } = store.state.graph;
  const { nodes, edges } = filteredGraph();

  stopSim();

  if (!nodes.length || !edges.length) {
    d3.select(svgEl).selectAll('*').remove();
    d3.select(svgEl).append('text')
      .attr('x', 20).attr('y', 40)
      .attr('fill', '#8899bb').attr('font-size', 13)
      .text('No graph data. Load an address or click "Load Map".');
    document.getElementById('graphMeta').textContent = 'nodes=0 edges=0';
    return;
  }

  const W = svgEl.clientWidth || 760;
  const H = svgEl.clientHeight || 540;

  // Build unique node+edge sets for d3
  const nodeById = {};
  nodes.forEach(n => { nodeById[n.id] = { id: n.id, isCenter: n.id === center }; });
  const nodeArr = Object.values(nodeById);
  const linkArr = edges.map(e => ({ source: e.src, target: e.dst, tx_count: e.tx_count }));

  const maxTx = Math.max(1, ...linkArr.map(l => l.tx_count));

  const svg = d3.select(svgEl);
  svg.selectAll('*').remove();

  // Zoom + pan container
  const root = svg.append('g').attr('class', 'zoom-root');
  svg.call(
    d3.zoom()
      .scaleExtent([0.15, 4])
      .on('zoom', (event) => root.attr('transform', event.transform))
  );

  // Arrow marker
  svg.append('defs').append('marker')
    .attr('id', 'arrow')
    .attr('viewBox', '0 -4 8 8')
    .attr('refX', 18).attr('refY', 0)
    .attr('markerWidth', 5).attr('markerHeight', 5)
    .attr('orient', 'auto')
    .append('path').attr('d', 'M0,-4L8,0L0,4').attr('fill', '#3B82F6').attr('opacity', 0.7);

  const linkEl = root.append('g').selectAll('line')
    .data(linkArr).join('line')
    .attr('stroke', '#3B82F6')
    .attr('stroke-opacity', d => 0.25 + 0.55 * (d.tx_count / maxTx))
    .attr('stroke-width', d => 0.8 + 2.5 * (d.tx_count / maxTx))
    .attr('marker-end', 'url(#arrow)');

  const nodeEl = root.append('g').selectAll('g')
    .data(nodeArr).join('g')
    .attr('class', 'g-node-group')
    .call(
      d3.drag()
        .on('start', (event, d) => {
          if (!event.active) _graphSim.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
        .on('end', (event, d) => {
          if (!event.active) _graphSim.alphaTarget(0);
          d.fx = null; d.fy = null;
        })
    )
    .on('click', (event, d) => runSafe(() => loadGraph(d.id)));

  nodeEl.append('circle')
    .attr('r', d => d.isCenter ? 14 : 9)
    .attr('fill', d => d.isCenter ? '#5B8DFF' : '#22304e')
    .attr('stroke', d => d.isCenter ? '#fff' : '#3B82F6')
    .attr('stroke-width', d => d.isCenter ? 2.5 : 1.2)
    .attr('class', 'g-click')
    .attr('data-node', d => d.id)
    .style('cursor', 'pointer');

  nodeEl.append('text')
    .text(d => shortAddr(d.id))
    .attr('fill', '#c0cfee')
    .attr('font-size', 10)
    .attr('dx', 14).attr('dy', 4)
    .style('pointer-events', 'none');

  _graphSim = d3.forceSimulation(nodeArr)
    .force('link', d3.forceLink(linkArr).id(d => d.id).distance(90).strength(0.7))
    .force('charge', d3.forceManyBody().strength(-180))
    .force('center', d3.forceCenter(W / 2, H / 2))
    .force('collision', d3.forceCollide(22))
    .on('tick', () => {
      linkEl
        .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
      nodeEl.attr('transform', d => `translate(${d.x},${d.y})`);
    });

  document.getElementById('graphMeta').textContent =
    `nodes=${nodes.length} edges=${edges.length} center=${center ? shortAddr(center) : 'global'} minTx=${store.state.graphView.minTx} dir=${store.state.graphView.direction}`;
}
// ─── end graph ───────────────────────────────────────────────────────────────

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
  stopSim();
  const g = await jfetch(`/graph/neighbors/${a}?limit=60`);
  store.set({ graph: { ...g, center: a.toLowerCase() }, activePanel: 'flow' });
}

async function loadGlobalMap() {
  stopSim();
  const g = await jfetch('/graph/global?limit=80');
  store.set({ graph: { ...g, center: '' }, activePanel: 'flow' });
  document.getElementById('graphAddress').value = '';
}

async function openRisk(address) {
  const risk = await jfetch(`/entity/${address}/risk`);
  const f = risk.factors || {};
  document.getElementById('riskContent').innerHTML = `<div class="row"><span>Address</span><strong>${shortAddr(risk.address)}</strong></div><div class="row"><span>Risk Score</span><strong>${risk.risk_score} (${risk.band})</strong></div><div class="factor"><span>Label</span><strong>${f.label_risk ?? 0}</strong></div><div class="factor"><span>Alert</span><strong>${f.alert_risk ?? 0}</strong></div><div class="factor"><span>Centrality</span><strong>${f.centrality_risk ?? 0}</strong></div><div class="factor"><span>Flow</span><strong>${f.flow_risk ?? 0}</strong></div>`;
  const drawer = document.getElementById('riskDrawer');
  drawer.classList.remove('hidden');
  drawer.focus();
}

async function refreshAll() {
  setLoadingState(true);
  try {
    const [summary, failures, taxonomy] = await Promise.all([
      jfetch('/dashboard/summary?hot_limit=20'),
      jfetch('/runbook/failures?limit=20'),
      jfetch('/labels/taxonomy'),
    ]);
    const seed =
      (summary.summary?.hot_alerts || [])[0]?.address ||
      (summary.summary?.hot_addresses || [])[0]?.address ||
      '';
    let graph = store.state.graph;
    if (!graph.center && !graph.nodes?.length) {
      if (seed) {
        const g = await jfetch(`/graph/neighbors/${seed}?limit=60`);
        graph = { ...g, center: seed.toLowerCase() };
        document.getElementById('graphAddress').value = seed;
      } else {
        const g = await jfetch('/graph/global?limit=80');
        if (g.nodes?.length) {
          graph = { ...g, center: '' };
        }
      }
    }
    store.set({ summary, failures: failures.failures || [], taxonomy: taxonomy.labels || {}, graph });
    document.getElementById('healthDot').style.background = 'var(--ok)';
    document.getElementById('lastUpdated').textContent = new Date().toISOString();
    document.getElementById('statusBar').textContent = `lag=${summary.compact?.ingest_lag_blocks ?? 'n/a'} | dead-letter=${summary.compact?.dead_letter_open ?? 0}`;
    document.getElementById('degradedBanner').classList.add('hidden');
  } catch (e) {
    document.getElementById('degradedBanner').classList.remove('hidden');
    throw e;
  } finally {
    setLoadingState(false);
  }
}

async function runSafe(fn) {
  setBusy(true);
  try {
    await fn();
  } catch (e) {
    document.getElementById('healthDot').style.background = 'var(--crit)';
    document.getElementById('lastUpdated').textContent = `error: ${String(e.message || e).slice(0, 120)}`;
    toast(String(e.message || e).slice(0, 140), 'err');
  } finally {
    setBusy(false);
  }
}

function bind() {
  document.getElementById('refreshBtn').addEventListener('click', () => runSafe(refreshAll));
  document.getElementById('closeDrawer').addEventListener('click', () => document.getElementById('riskDrawer').classList.add('hidden'));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') document.getElementById('riskDrawer').classList.add('hidden'); });

  document.getElementById('panelNav').addEventListener('click', (e) => {
    const b = e.target.closest('.nav-btn'); if (!b) return; store.set({ activePanel: b.dataset.panel });
  });

  document.getElementById('graphLoadBtn').addEventListener('click', () => runSafe(() => loadGraph(document.getElementById('graphAddress').value)));
  document.getElementById('graphLoadMapBtn').addEventListener('click', () => runSafe(loadGlobalMap));

  document.getElementById('graphApplyFiltersBtn').addEventListener('click', () => {
    const minTx = Number(document.getElementById('graphMinTx').value || 1);
    const direction = document.getElementById('graphDirection').value;
    stopSim();
    store.set({ graphView: { ...store.state.graphView, minTx: Math.max(0, minTx), direction } });
  });
  document.getElementById('graphZoomInBtn').addEventListener('click', () => {
    const svgEl = document.getElementById('graphSvg');
    d3.select(svgEl).transition().call(d3.zoom().scaleBy, 1.3);
  });
  document.getElementById('graphZoomOutBtn').addEventListener('click', () => {
    const svgEl = document.getElementById('graphSvg');
    d3.select(svgEl).transition().call(d3.zoom().scaleBy, 0.77);
  });
  document.getElementById('graphResetBtn').addEventListener('click', () => {
    const svgEl = document.getElementById('graphSvg');
    d3.select(svgEl).transition().call(d3.zoom().transform, d3.zoomIdentity);
    store.set({ graphView: { minTx: 1, direction: 'both', scale: 1 } });
  });

  document.body.addEventListener('click', (e) => runSafe(async () => {
    const t = e.target;
    if (t.matches('[data-preset]')) { await jfetch(`/runbook/threshold-presets/${t.dataset.preset}`, { method: 'POST' }); document.getElementById('presetStatus').textContent = `Applied preset: ${t.dataset.preset}`; toast(`Preset applied: ${t.dataset.preset}`); return refreshAll(); }
    if (t.matches('.act-ack')) { await jfetch(`/alerts/${t.dataset.id}/ack?assignee=ui`, { method: 'POST' }); toast(`Alert ${t.dataset.id} acknowledged`); return refreshAll(); }
    if (t.matches('.act-resolve')) { await jfetch(`/alerts/${t.dataset.id}/resolve?assignee=ui`, { method: 'POST' }); toast(`Alert ${t.dataset.id} resolved`); return refreshAll(); }
    if (t.matches('.fail-retry')) { await jfetch(`/runbook/failures/${t.dataset.id}/retry`, { method: 'POST' }); toast(`Failure ${t.dataset.id} queued for retry`); return refreshAll(); }
    if (t.matches('.fail-resolve')) { await jfetch(`/runbook/failures/${t.dataset.id}/resolve`, { method: 'POST' }); toast(`Failure ${t.dataset.id} resolved`); return refreshAll(); }
    if (t.matches('.addr-btn')) { const address = t.dataset.address; if (address) { await openRisk(address); await loadGraph(address); } }
  }));
}

bind();
runSafe(refreshAll);
