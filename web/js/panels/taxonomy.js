export function renderTaxonomy(labelsMap = {}) {
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
