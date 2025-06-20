/* utils.js — общие помощники фронта */

export async function api(path, opts = {}) {
  const token = localStorage.getItem('token');
  const headers = opts.headers ? { ...opts.headers } : {};
  if (token) headers['Authorization'] = 'Bearer ' + token;

  // если запрошен /auth/…, не добавляем /api
  const url = path.startsWith('/auth') ? path : '/api' + path;

  const res = await fetch(url, { ...opts, headers });
  if (res.status === 401) {
    // не авторизованы
    localStorage.removeItem('token');
    window.location = '/login.html';
    return;
  }
  return res;
}

/* запрос к корневым маршрутам (/auth/…) без /api */
export function raw(path, opts = {}) {
  opts.headers = {
    ...(opts.headers || {}),
    Authorization: 'Bearer ' + (localStorage.token || '')
  };
  return fetch(path, opts);
}

/* ------------------------------------------------------------------ */
/*  кем я вошёл?  →  'admin' | 'collector' | null                      */
export async function whoAmI() {
  if (!localStorage.token) return null;

  const r = await raw('/auth/me');            // /auth/me доступен всем
  if (!r.ok)          return null;

  const { role } = await r.json();            // {username, role}
  return role;                                // 'admin' / 'collector'
}

/* ------------------------------------------------------------------ */
/*  Гарантируем, что текущая роль входит в allowed[]                  */
/*  иначе стираем токен и отправляем на /login.html                   */
export async function requireRole(roles) {
  const meResp = await api('/auth/me');
  if (!meResp?.ok) {
    location.href = '/login.html';
    return;
  }
  const me = await meResp.json();
  if (!roles.includes(me.role)) {
    alert('Доступ запрещён');
    window.location = '/login.html';
  }
}
