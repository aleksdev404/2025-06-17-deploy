import { whoAmI } from './utils.js';

const form   = document.getElementById('loginForm');
const errBox = document.getElementById('error');

form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const fd = new FormData(form);
  const r  = await fetch('/auth/login', { method: 'POST', body: fd });

  if (r.ok) {
    const { access_token } = await r.json();
    localStorage.token = access_token;

    /* сразу узнаём роль и переходим на нужную страницу */
    const role = await whoAmI();                // 'admin' | 'collector'
    location.href = role === 'collector' ? '/collector.html' : '/';
  } else {
    errBox.textContent = 'Неверный логин или пароль';
    errBox.classList.remove('d-none');
  }
});
