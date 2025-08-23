document.addEventListener('DOMContentLoaded', ()=>{
  const log = document.getElementById('chat-log');
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const submitBtn = form.querySelector('button[type="submit"]');

  const add = (who, html)=>{
    const div = document.createElement('div');
    div.className='msg';
    div.innerHTML=`<b>${who}:</b> ${html}`;
    log.appendChild(div);
    log.scrollTop=log.scrollHeight;
    return div;
  };

  const addTyping = ()=>{
    const div = document.createElement('div');
    div.className='msg';
    div.innerHTML = `<b>Бот:</b> <span class="dotpulse"><span></span><span></span><span></span></span>`;
    log.appendChild(div);
    log.scrollTop=log.scrollHeight;
    return div;
  };

  const removeNode = (el)=> el?.parentNode?.removeChild(el);

  const csrftoken = document.cookie.split('; ').find(r=>r.startsWith('csrftoken='))?.split('=')[1];

  form.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const text = input.value.trim(); if(!text) return;
    add('Вы', text);
    input.value=''; input.focus();
    submitBtn.disabled = true;
    const typing = addTyping();

    try{
      const r = await fetch('/api/chat/message/',{
        method:'POST',
        headers:{'Content-Type':'application/json','X-CSRFToken':csrftoken},
        body: JSON.stringify({message:text})
      });
      const data = await r.json();
      removeNode(typing);
      add('Бот', data.reply ? data.reply : '(нет ответа)');
    }catch(err){
      removeNode(typing);
      add('Бот', '<span style="color:#DC2626">Ошибка сети. Попробуйте ещё раз.</span>');
    }finally{
      submitBtn.disabled = false;
    }
  });
});
