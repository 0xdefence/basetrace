import { shortAddr } from '../api/client.js';

export function filteredGraph(graph, graphView) {
  const { nodes = [], edges = [], center = '' } = graph || {};
  const { minTx = 1, direction = 'both' } = graphView || {};
  const c = center.toLowerCase();
  const es = edges.filter((e) => {
    const txOk = (e.tx_count || 0) >= minTx;
    const dirOk = direction === 'both' || (direction === 'out' && e.src?.toLowerCase() === c) || (direction === 'in' && e.dst?.toLowerCase() === c);
    return txOk && dirOk;
  });
  const used = new Set([c]);
  es.forEach((e) => { used.add((e.src || '').toLowerCase()); used.add((e.dst || '').toLowerCase()); });
  return { center: c, nodes: nodes.filter((n) => used.has((n.id || '').toLowerCase())), edges: es };
}

export function renderFlowGraph(graph, graphView) {
  const svg = document.getElementById('graphSvg');
  const { scale = 1 } = graphView || {};
  const { nodes, edges, center } = filteredGraph(graph, graphView);
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
  document.getElementById('graphMeta').textContent = `nodes=${nodes.length} edges=${edges.length} center=${shortAddr(center)} minTx=${graphView.minTx} dir=${graphView.direction} zoom=${scale.toFixed(2)}x`;
}
