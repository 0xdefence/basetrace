export const API = '';

export async function jfetch(path, options = {}) {
  const res = await fetch(`${API}${path}`, options);
  if (!res.ok) throw new Error(`${path} -> ${res.status} ${await res.text()}`);
  return res.json();
}

export const shortAddr = (a = '') => (a ? `${a.slice(0, 6)}…${a.slice(-4)}` : '');
export const sevClass = (s) => (s === 'high' ? 'high' : s === 'medium' ? 'medium' : 'low');
