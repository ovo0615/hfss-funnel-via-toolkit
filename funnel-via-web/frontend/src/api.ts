export const API_BASE = '/api';

export async function connectAedt(version: string) {
  const res = await fetch(`${API_BASE}/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ version })
  });
  return res.json();
}

export async function releaseAedt() {
  const res = await fetch(`${API_BASE}/release`, {
    method: 'POST'
  });
  return res.json();
}

export async function readStackup() {
  const res = await fetch(`${API_BASE}/read_stackup`, {
    method: 'POST'
  });
  return res.json();
}

export async function grabVias(mode: 'selected' | 'prefix', prefix: string) {
  const res = await fetch(`${API_BASE}/grab`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode, prefix })
  });
  return res.json();
}

export async function buildFunnels(payload: any) {
  const res = await fetch(`${API_BASE}/build`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  return res.json();
}
