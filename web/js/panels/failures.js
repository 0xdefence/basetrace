export function renderFailuresPanel(summary, failures) {
  const rows = failures || [];
  document.getElementById('failures').innerHTML = `<table class="table"><thead><tr><th>ID</th><th>Range</th><th>Retries</th><th>Status</th><th>Actions</th></tr></thead><tbody>${rows
    .map((r) => `<tr><td>${r.id}</td><td>${r.start_block ?? '-'} → ${r.end_block ?? '-'}</td><td>${r.retry_count ?? 0}</td><td>${r.status || ''}</td><td class="actions"><button class="secondary fail-retry" data-id="${r.id}">Retry</button><button class="danger fail-resolve" data-id="${r.id}">Resolve</button></td></tr><tr><td></td><td colspan="4" class="muted">${(r.error || '').slice(0, 160)}</td></tr>`)
    .join('')}</tbody></table>`;

  const topAddr = summary?.summary?.top_alert_addresses_24h || [];
  document.getElementById('topAddresses').innerHTML = topAddr.map((r) => `<div class="row"><span>${r.address}</span><strong>${r.count}</strong></div>`).join('') || '<p class="muted">No data</p>';
}
