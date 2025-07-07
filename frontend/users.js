import {api} from './utils.js'

console.log(1)

// добавление пользователя
document.getElementById('addUser').addEventListener('submit', async e=>{
  e.preventDefault()
  console.log(1)
  const fd = new FormData(e.target)
  const body = Object.fromEntries(fd.entries())
  const r = await api('/users/',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)})
  if(r.ok){ e.target.reset(); load() }
  else alert('ошибка '+r.status)
})