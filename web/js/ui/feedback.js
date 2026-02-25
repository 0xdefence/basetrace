export function toast(message, kind = 'ok') {
  const host = document.getElementById('toastHost');
  if (!host) return;
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.textContent = message;
  host.appendChild(el);
  setTimeout(() => el.remove(), 2800);
}

export function setBusy(on) {
  document.querySelectorAll('button').forEach((b) => {
    b.disabled = on;
  });
}

export function setLoadingState(on) {
  ['kpis', 'hotAlerts', 'runbookOps', 'failures', 'topAddresses'].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle('skeleton', on);
  });
}
