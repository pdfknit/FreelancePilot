document.addEventListener('DOMContentLoaded', () => {
  const log = document.getElementById('chat-log');
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  if (!log || !form || !input) return;

  const submitBtn = form.querySelector('button[type="submit"]');
  const channel = form.getAttribute('data-channel') || 'page';

  function csrftoken() {
    return document.cookie.split('; ').find(r => r.startsWith('csrftoken='))?.split('=')[1];
  }

  function addMsg(who, html) {
    // убираем «пустышку»
    const empty = log.querySelector('.empty');
    if (empty) empty.remove();
    const div = document.createElement('div');
    div.className = 'msg';
    div.innerHTML = `<b>${who}:</b> ${html}`;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  function addTyping() {
    const div = document.createElement('div');
    div.className = 'msg';
    div.innerHTML = `<b>Бот:</b> <span class="dotpulse"><span></span><span></span><span></span></span>`;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  async function loadHistory() {
    try {
      const r = await fetch('/api/chat/history/', { credentials: 'same-origin' });
      const data = await r.json();
      log.innerHTML = '';
      (data.messages || []).forEach(m => {
        addMsg(m.role === 'user' ? 'Вы' : 'Бот', escapeHtml(m.text).replace(/\n/g, '<br>'));
      });
      if (!(data.messages || []).length) {
        // оставим приветствие, если история пуста
        const empty = document.createElement('div');
        empty.className = 'empty';
        empty.innerHTML = `<div class="icon">🤖</div>Напишите сообщение…`;
        log.appendChild(empty);
      }
    } catch (e) {
      addMsg('Бот', 'Не удалось загрузить историю');
    }
  }

  function escapeHtml(s) {
    return (s || '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
  }

  async function sendMessage(text) {
    const payload = { text: text, channel: channel };
    const typing = addTyping();
    submitBtn.disabled = true;
    try {
      const r = await fetch('/api/chat/message/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrftoken()
        },
        credentials: 'same-origin',
        body: JSON.stringify(payload)
      });
      const data = await r.json();
      typing.remove();
      if (!r.ok) {
        addMsg('Бот', 'Ошибка: ' + (data.error || r.status));
        return;
      }
      addMsg('Бот', escapeHtml(data.reply).replace(/\n/g, '<br>'));
    } catch (e) {
      typing.remove();
      addMsg('Бот', 'Сеть недоступна');
    } finally {
      submitBtn.disabled = false;
    }
  }

  form.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const txt = input.value.trim();
    if (!txt) return;
    addMsg('Вы', escapeHtml(txt));
    input.value = '';
    sendMessage(txt);
  });

  // начальная подгрузка
  loadHistory();
});
