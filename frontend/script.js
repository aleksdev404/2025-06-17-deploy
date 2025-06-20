/* jshint esversion: 11 */
import { api, requireRole } from './utils.js';
requireRole(['admin']);

let currentUserId = null;

(async () => {
  // Получаем ID текущего пользователя
  const meResp = await api('/auth/me');
  if (meResp.ok) {
    const me = await meResp.json();
    currentUserId = me.id;
  }

  const $ = sel => document.querySelector(sel);
  const $$ = sel => document.querySelectorAll(sel);

  $('#logout').onclick = () => {
    localStorage.removeItem('token');
    location.href = '/login.html';
  };

  /* ---------- навигация ---------- */
  $$('.nav-link').forEach(a => {
    a.onclick = e => {
      e.preventDefault();
      $$('.nav-link').forEach(x => x.classList.remove('active'));
      a.classList.add('active');

      ['orders','materials','stats','users'].forEach(id => {
        const page = $('#page-' + id);
        if (page) page.classList.toggle('d-none', a.dataset.page !== id);
      });

      if (a.dataset.page === 'stats') loadStats();
      if (a.dataset.page === 'users') loadUsers();
    };
  });

  /* ==============================================================
     =====================   ЗАКАЗЫ   ============================= */
  // === блок «ЗАКАЗЫ» ===
const ordersList = document.querySelector('#orders-list');

async function loadOrders() {
  const orders = await (await api('/orders/')).json();
  ordersList.innerHTML = '';
  orders.forEach(o => {
    ordersList.insertAdjacentHTML('beforeend', `
      <li class="list-group-item">
        <div class="d-flex justify-content-between">
          <div>
            <b>#${o.number}</b> — ${o.customer||'без имени'} —
            ${new Date(o.created_at + 'Z').toLocaleString('ru-RU')}
          </div>
          <button
            class="btn btn-sm ${o.ignored ? 'btn-success' : 'btn-outline-danger'}"
            data-toggle="${o.id}">
            ${o.ignored ? '⏎' : '🗑️'}
          </button>
        </div>
        <ul class="mt-2">
          ${o.lines.map(l=>`
            <li>${l.product_title.replace('<','&lt;')} × ${l.quantity}</li>
          `).join('')}
        </ul>
      </li>
    `);
  });
}

ordersList.onclick = async e => {
  const btn = e.target.closest('button[data-toggle]');
  if (!btn) return;

  const id     = btn.dataset.toggle;
  const isDel  = btn.classList.contains('btn-outline-danger');
  const url    = isDel
    ? `/orders/${id}`         // DELETE → игнорируем заказ
    : `/orders/${id}/enable`; // PATCH  → восстанавливаем
  const method = isDel ? 'DELETE' : 'PATCH';

  const res = await api(url, { method });
  if (!res.ok) {
    // если что-то пошло не так — покажем ошибку
    const text = await res.text();
    return alert(`Ошибка ${res.status}: ${text}`);
  }

  // и перерисуем всё сразу
  await loadOrders();
  await loadStock();
  await loadStats();
};

  $('#btn-import').onclick = async () => {
    const r = await api('/orders/import', { method:'POST' });
    if (r.ok) {
      const { imported } = await r.json();
      alert(`Импортировано: ${imported}`);
      await loadOrders(); await loadStock();
    } else alert('Ошибка импорта: ' + r.status);
  };

  /* ==============================================================
     =================  МАТЕРИАЛЫ + СКЛАД  ======================== */
  const matsList   = $('#materials-list');
  const stockBody  = $('#stock-table tbody');
  const selTpl     = document.createElement('select');
  selTpl.className = 'form-select sel-mat';

  async function loadMaterials() {
    const mats = await (await api('/materials/')).json();

    /* готовим шаблон селекта для правил */
    selTpl.innerHTML = '<option value="">Материал…</option>';
    mats.forEach(m=>selTpl.insertAdjacentHTML('beforeend',
      `<option value="${m.id}">${m.name}</option>`));

    /* список материалов слева */
    matsList.innerHTML = '';
    mats.forEach(m=>{
      matsList.insertAdjacentHTML('beforeend',`
        <li class="list-group-item d-flex justify-content-between align-items-center">
          <span>${m.name} (${m.unit}) баз.: ${m.base_qty}</span>
          <div>
            <button class="btn btn-sm btn-outline-primary me-1" data-edit="${m.id}">✏️</button>
            <button class="btn btn-sm btn-outline-danger"        data-del="${m.id}">🗑️</button>
          </div>
        </li>`);
    });
  }

  async function loadStock() {
    const rows = await (await api('/materials/stock')).json();
    stockBody.innerHTML = '';
    rows.forEach(r=>{
      stockBody.insertAdjacentHTML('beforeend',`
        <tr>
          <td>${r.name}</td>
          <td contenteditable class="qty" data-id="${r.id}">${r.qty}</td>
          <td contenteditable class="min" data-id="${r.id}">${r.min_qty}</td>
          <td>
            <button class="btn btn-sm btn-outline-secondary hist" data-hist="${r.id}">📑</button>
            <button class="btn btn-sm btn-outline-danger del-mat" data-delmat="${r.id}">🗑️</button>
          </td>
        </tr>`);
    });
  }

  /* inline-правки qty / min_qty */
  let prevVal = null;
  stockBody.addEventListener('focusin', e=>{
    if(e.target.matches('.qty,.min')) prevVal = e.target.innerText;
  });
  stockBody.addEventListener('keydown', async e=>{
    if(e.key==='Enter' && e.target.matches('.qty,.min')) {
      e.preventDefault();
      const after = parseFloat(e.target.innerText)||0;
      const before= parseFloat(prevVal)||0;
      if(after===before) return;
      const id = e.target.dataset.id;
      if(e.target.classList.contains('qty'))
        await api(`/materials/${id}/adjust?delta=${after-before}`,{method:'PATCH'});
      else
        await api(`/materials/${id}/min?value=${after}`,{method:'PATCH'});
      await loadStock();
    }
  });

  /* история перемещений и удаление материала */
  const histModal = new bootstrap.Modal('#histModal');

stockBody.onclick = async (e) => {
  const histBtn = e.target.closest('button[data-hist]');
  const delBtn  = e.target.closest('button[data-delmat]');

  if (histBtn) {
    const materialId = histBtn.dataset.hist;
    // запрашиваем до 50 последних записей
    const rows = await (await api(`/materials/${materialId}/history?limit=50`)).json();

    const list = document.querySelector('#hist-list');
    list.innerHTML = '';

    rows.forEach(r => {
  const num = r.order_number
    ? `#${r.order_number}`
    : '#руч.';
  const qty = (r.qty > 0 ? '+' : '') + r.qty;

  // Вот здесь — берём r.dt, конвертим в объект Date и вызываем toLocaleString
  const ts = new Date(r.dt).toLocaleString('ru-RU', {
    hour12: false,
    year:   'numeric',
    month:  '2-digit',
    day:    '2-digit',
    hour:   '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });

  list.insertAdjacentHTML('beforeend', `
    <li class="list-group-item">
      ${num} — ${qty} — ${ts}
    </li>
  `);
});

    histModal.show();
  }

  if (delBtn) {
    if (!confirm('Удалить материал и связанные правила?')) return;
    await api(`/materials/${delBtn.dataset.delmat}`, { method: 'DELETE' });
    await loadMaterials();
    await loadStock();
    await loadRules();
  }
};

  /* список материалов (buttons) */
  matsList.onclick = async e=>{
    if(e.target.dataset.del){
      if(!confirm('Удалить материал и связанные правила?')) return;
      await api(`/materials/${e.target.dataset.del}`,{method:'DELETE'});
      await loadMaterials(); await loadStock(); await loadRules();
    }
    if(e.target.dataset.edit){
      const m = (await (await api('/materials/')).json()).find(x=>x.id==e.target.dataset.edit);
      $('#mat-name').value=m.name; $('#mat-unit').value=m.unit; $('#mat-qty').value=m.base_qty;
      $('#mat-add').dataset.edit = m.id;
    }
  };

  $('#mat-add').onclick = async e=>{
    const body = JSON.stringify({
      name: $('#mat-name').value.trim(),
      unit: $('#mat-unit').value.trim()||'шт',
      base_qty: parseFloat($('#mat-qty').value)||0
    });
    if(!JSON.parse(body).name) return alert('Введите название!');
    if(e.target.dataset.edit){
      await api(`/materials/${e.target.dataset.edit}`,{
        method:'PUT', headers:{'Content-Type':'application/json'}, body});
      delete e.target.dataset.edit;
    }else{
      await api('/materials/',{
        method:'POST', headers:{'Content-Type':'application/json'}, body});
    }
    ['mat-name','mat-qty'].forEach(id=>$('#'+id).value=id==='mat-name'? '':'0');
    await loadMaterials(); await loadStock();
  };

  /* ==============================================================
     ====================   ПРАВИЛА   ============================= */
  const rulesList = $('#rules-list');
  const multiCont = $('#multi-container');
  function addRuleRow(){
    const row = document.createElement('div');
    row.className = 'row g-2 mb-2 rule-row';
    row.innerHTML = `
      <div class="col-4"></div>
      <div class="col-3"><input type="number" step="0.01" value="1" class="form-control inp-qty"></div>
      <div class="col-1"><button class="btn btn-danger btn-sm rem">✖</button></div>`;
    row.children[0].appendChild(selTpl.cloneNode(true));
    multiCont.appendChild(row);
  }
  $('#rule-add-row').onclick = addRuleRow;
  multiCont.onclick = e=>{
    if(e.target.classList.contains('rem')) e.target.closest('.rule-row').remove();
  };

  async function loadRules(){
    const rules = await (await api('/rules/')).json();
    const byPattern={};
    rules.forEach(r=>(byPattern[r.pattern]=byPattern[r.pattern]||[]).push(r));
    rulesList.innerHTML='';
    Object.entries(byPattern).forEach(([pat,items])=>{
      const li=document.createElement('li'); li.className='list-group-item';
      li.innerHTML = `
        <div class="fw-bold">«${pat}»</div>
        <ul class="list-group list-group-flush mt-1">
          ${items.map(it=>`
            <li class="list-group-item d-flex justify-content-between align-items-center ps-4">
              <span>${it.material.name} × ${it.qty}</span>
              <button class="btn btn-sm btn-outline-danger" data-del="${it.id}">🗑️</button>
            </li>`).join('')}
        </ul>`;
      rulesList.appendChild(li);
    });
  }
  rulesList.onclick = async e=>{
    if(e.target.dataset.del){
      await api(`/rules/${e.target.dataset.del}`,{method:'DELETE'});
      await loadRules();
    }
  };

  $('#rule-add').onclick = async ()=>{
    const pattern = $('#rule-pattern').value.trim();
    if(!pattern) return alert('Введите подстроку!');
    const payload = [...$$('.rule-row')].map(r=>({
      pattern,
      material_id:+r.querySelector('.sel-mat').value,
      qty:parseFloat(r.querySelector('.inp-qty').value)||1
    })).filter(r=>r.material_id);
    if(!payload.length) return alert('Выберите материал!');
    await api('/rules/',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)
    });
    $('#rule-pattern').value=''; multiCont.innerHTML=''; addRuleRow(); await loadRules();
  };

  /* ==============================================================
     ====================   СТАТИСТИКА   ========================== */
  let selMonth=null, chartObj=null;
  function ensureStatsElements(){
    selMonth = $('#stat-month');
    if(!selMonth) return false;
    if(!selMonth.dataset.filled){
      const now=new Date();
      for(let i=0;i<12;i++){
        const d=new Date(now.getFullYear(),now.getMonth()-i,1);
        const y=d.getFullYear(); const m=String(d.getMonth()+1).padStart(2,'0');
        selMonth.insertAdjacentHTML('beforeend',
          `<option value="${y}-${m}">${d.toLocaleString('ru-RU',{month:'long',year:'numeric'})}</option>`);
      }
      selMonth.dataset.filled='1';
      selMonth.onchange = loadStats;
    }
    return true;
  }
  async function loadStats(){
  if(!ensureStatsElements()) return;
  const val = selMonth.value;
  const url = val
    ? `/stats/totals?year=${val.slice(0,4)}&month=${+val.slice(5)}`
    : '/stats/totals';
  const totals = await (await api(url)).json();

  const labels = Object.keys(totals);
  const data   = Object.values(totals);

  // Мутные пастельные цвета: saturation=50%, lightness=70%
  const backgroundColors = labels.map((_, i) => {
    const hue = Math.round(i * 360 / labels.length);
    return `hsl(${hue}, 50%, 70%)`;
  });

  if(chartObj) chartObj.destroy();
  const canvas = $('#chart-day');
  chartObj = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: backgroundColors,
      }]
    },
    options: {
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        title: {
          display: true,
          text: val
            ? `Расход за ${selMonth.selectedOptions[0].textContent}`
            : 'Расход за последние 12 месяцев'
        }
      },
      responsive: true,
      maintainAspectRatio: false
    }
  });

}

 /* ====================   ПОЛЬЗОВАТЕЛИ   ======================== */
  // ───── Загрузка поставщиков ─────
 

  // ───── Пользователи ─────
  async function loadUsers() {
    const users = await (await api('/users/')).json();
    const tbody = document.querySelector('#tbl-users tbody');
    tbody.innerHTML = '';

    users.forEach(u => {
      const isAdmin = u.role === 'admin';

      // Роль: если admin — просто текст, иначе селект
      const roleCell = isAdmin
        ? `<span>admin</span>`
        : `<select class="form-select role" data-id="${u.id}">
             <option value="admin"    ${u.role==='admin'?'selected':''}>admin</option>
             <option value="collector"${u.role==='collector'?'selected':''}>collector</option>
           </select>`;

      // Активность: если admin — прочерк, иначе кнопка
      const activeCell = isAdmin
        ? `—`
        : `<button class="btn btn-sm ${u.is_active?'btn-success':'btn-outline-secondary'} toggle" data-id="${u.id}">
             ${u.is_active?'✔':'✖'}
           </button>`;

      // Смена пароля — только для сборщиков
      const passCell = u.role === 'collector'
        ? `<div class="d-flex">
             <input type="password" placeholder="Новый пароль"
                    class="form-control form-control-sm me-1 pass-input" data-id="${u.id}">
             <button class="btn btn-sm btn-outline-primary change-pass" data-id="${u.id}">
               Сменить
             </button>
           </div>`
        : `—`;

      tbody.insertAdjacentHTML('beforeend', `
        <tr>
          <td>${u.username}</td>
          <td>${roleCell}</td>
          <td>${activeCell}</td>
          <td>${passCell}</td>
        </tr>
      `);
    });
  }

  // Ловим изменение ролей
  document.querySelector('#tbl-users tbody').addEventListener('change', async e => {
    if (!e.target.classList.contains('role')) return;
    await api(`/users/${e.target.dataset.id}/role?role=${e.target.value}`, { method:'PATCH' });
    loadUsers();
  });

  // Ловим клики по кнопкам «toggle» и «change-pass»
  document.querySelector('#tbl-users tbody').addEventListener('click', async e => {
    // переключить активность
    if (e.target.classList.contains('toggle')) {
      await api(`/users/${e.target.dataset.id}/state`, { method:'PATCH' });
      return loadUsers();
    }
    // сменить пароль
    if (e.target.classList.contains('change-pass')) {
      const id = e.target.dataset.id;
      const inp = document.querySelector(`.pass-input[data-id="${id}"]`);
      const np = inp.value.trim();
      if (!np) return alert('Введите новый пароль');
      const res = await api(`/users/${id}/password`, {
        method: 'PATCH',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ new_password: np })
      });
      if (res.ok) {
        alert('Пароль успешно изменён');
        inp.value = '';
      } else {
        alert(`Ошибка ${res.status}: ${await res.text()}`);
      }
    }
  });

  // ───── Инициализация ─────
  await loadUsers();
  
  /* ==============================================================
     ====================   INIT   ================================ */
  const init = async ()=>{
    addRuleRow();
    await loadOrders(); await loadMaterials(); await loadStock();
    await loadRules();  await loadStats(); 
  };
  await init();
  
})();


