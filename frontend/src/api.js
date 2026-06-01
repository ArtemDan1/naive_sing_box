const tokenKey = 'token'
export function setToken(t) { localStorage.setItem(tokenKey, t) }
export function getToken() { return localStorage.getItem(tokenKey) }
export function logout() { localStorage.removeItem(tokenKey) }

async function req(method, url, body) {
  const headers = { 'Content-Type': 'application/json' }
  const t = getToken()
  if (t) headers['Authorization'] = `Bearer ${t}`
  const res = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined })
  if (res.status === 401) { logout(); location.hash = '#/login' }
  if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`)
  return res.status === 204 ? null : res.json()
}

export const api = {
  login: (u, p) => req('POST', '/api/auth/login', { username: u, password: p }),
  clients: () => req('GET', '/api/clients'),
  createClient: (label) => req('POST', '/api/clients', { label }),
  updateClient: (id, patch) => req('PATCH', `/api/clients/${id}`, patch),
  deleteClient: (id) => req('DELETE', `/api/clients/${id}`),
  getSettings: () => req('GET', '/api/settings'),
  putSettings: (domain) => req('PUT', '/api/settings', { domain }),
}
