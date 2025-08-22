document.addEventListener('DOMContentLoaded', ()=>{
  const log = document.getElementById('chat-log');
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const add = (who, text)=>{
    const div = document.createElement('div');
    div.className='msg';
    div.innerHTML=`<b>${who}:</b> ${text}`;
    log.appendChild(div); log.scrollTop=log.scrollHeight;
  };
  const csrftoken = document.cookie.split('; ').find(r=>r.startsWith('csrftoken='))?.split('=')[1];
  form.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const text = input.value.trim(); if(!text) return;
    add('Вы', text); input.value='';
    const r = await fetch('/api/chat/message/',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-CSRFToken':csrftoken},
      body: JSON.stringify({message:text})
    });
    const data = await r.json();
    add('Бот', data.reply || '(нет ответа)');
  });
});
