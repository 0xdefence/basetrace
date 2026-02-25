import { jfetch, shortAddr } from './api/client.js';
import { store } from './state/store.js';
import { toast, setBusy, setLoadingState } from './ui/feedback.js';
import { renderKpis, renderOverview } from './panels/overview.js';
import { renderFailuresPanel } from './panels/failures.js';
import { renderFlowGraph } from './panels/graph.js';
import { renderTaxonomy } from './panels/taxonomy.js';

const panelMeta = {
  overview: { title: 'Overview', subtitle: 'Core operations dashboard' },
  flow: { title: 'Flow Graph', subtitle: 'Address neighbors and flow links' },
  taxonomy: { title: 'Taxonomy', subtitle: 'MVP label mapping and rules' },
  failures: { title: 'Failures', subtitle: 'Dead-letter queue operations' },
};

function showPanel(name) {
  document.querySelectorAll('.panel-view').forEach((el) => el.classList.remove('active'));
  document.querySelector(`#panel-${name}`)?.classList.add('active');
  document.querySelectorAll('.nav-btn').forEach((el) => el.classList.toggle('active', el.dataset.panel === name));
  const meta = panelMeta[name] || panelMeta.overview;
  document.getElementById('panelTitle').textContent = meta.title;
  document.getElementById('panelSubtitle').textContent = meta.subtitle;
}

function renderApp() {
  const s = store.state;
  showPanel(s.activePanel);
  renderKpis(s.summary);
  renderOverview(s.summary);
  renderFailuresPanel(s.summary, s.failures);
  renderFlowGraph(s.graph, s.graphView);
  renderTaxonomy(s.taxonomy);
}

store.subscribe(renderApp);

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
  try { await fn(); }
  catch (e) {
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
  const loadKnownBtn = document.getElementById('graphLoadKnownBtn') || document.getElementById('graphLoadMapBtn');
  if (loadKnownBtn) {
    loadKnownBtn.addEventListener('click', () => runSafe(async () => {
      const known = ['0x4200000000000000000000000000000000000010', '0x4200000000000000000000000000000000000007', '0x4200000000000000000000000000000000000011'];
      for (const a of known) { try { await loadGraph(a); document.getElementById('graphAddress').value = a; return; } catch {} }
    }));
  }

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
    if (t.matches('[data-preset]')) { await jfetch(`/runbook/threshold-presets/${t.dataset.preset}`, { method: 'POST' }); document.getElementById('presetStatus').textContent = `Applied preset: ${t.dataset.preset}`; toast(`Preset applied: ${t.dataset.preset}`); return refreshAll(); }
    if (t.matches('.act-ack')) { await jfetch(`/alerts/${t.dataset.id}/ack?assignee=ui`, { method: 'POST' }); toast(`Alert ${t.dataset.id} acknowledged`); return refreshAll(); }
    if (t.matches('.act-resolve')) { await jfetch(`/alerts/${t.dataset.id}/resolve?assignee=ui`, { method: 'POST' }); toast(`Alert ${t.dataset.id} resolved`); return refreshAll(); }
    if (t.matches('.fail-retry')) { await jfetch(`/runbook/failures/${t.dataset.id}/retry`, { method: 'POST' }); toast(`Failure ${t.dataset.id} queued for retry`); return refreshAll(); }
    if (t.matches('.fail-resolve')) { await jfetch(`/runbook/failures/${t.dataset.id}/resolve`, { method: 'POST' }); toast(`Failure ${t.dataset.id} resolved`); return refreshAll(); }
    if (t.matches('.addr-btn')) { const address = t.dataset.address; if (address) { await openRisk(address); await loadGraph(address); } }
    if (t.matches('.g-click')) { const address = t.dataset.node; if (address) await openRisk(address); }
  }));
}

bind();
runSafe(refreshAll);
