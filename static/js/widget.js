(function () {
    const $ = (sel) => document.querySelector(sel);
    const panel = $('#fpw-panel');
    const btn = $('#fpw-toggle');
    const closeBtn = $('#fpw-close');
    const log = $('#fpw-log');
    const form = $('#fpw-form');
    const input = $('#fpw-input');

    function csrftoken() {
        return document.cookie.split('; ').find(r => r.startsWith('csrftoken='))?.split('=')[1];
    }

    function addMsg(who, html) {
        const div = document.createElement('div');
        div.className = 'fpw-msg';
        div.innerHTML = `<b>${who}:</b> ${html}`;
        log.appendChild(div);
        log.scrollTop = log.scrollHeight;
        return div;
    }

    function addTyping() {
        const div = document.createElement('div');
        div.className = 'fpw-msg';
        div.innerHTML = `<b>Бот:</b> <span class="dotpulse"><span></span><span></span><span></span></span>`;
        log.appendChild(div);
        log.scrollTop = log.scrollHeight;
        return div;
    }

    async function loadHistory() {
        try {
            const r = await fetch('/api/chat/history/', {credentials: 'same-origin'});
            const data = await r.json();
            log.innerHTML = '';
            (data.messages || []).forEach(m => {
                addMsg(m.role === 'user' ? 'Вы' : 'Бот', (m.text || '').replace(/\n/g, '<br>'));
            });
        } catch (e) {
            addMsg('Бот', 'Не удалось загрузить историю');
        }
    }

    async function sendMessage(text) {
        const typing = addTyping();
        try {
            const r = await fetch('/api/chat/message/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken()
                },
                credentials: 'same-origin',
                body: JSON.stringify({text: text, channel: 'widget'})
            });
            const data = await r.json();
            typing.remove();
            if (!r.ok) {
                addMsg('Бот', 'Ошибка: ' + (data.error || r.status));
                return;
            }
            addMsg('Бот', (data.reply || '').replace(/\n/g, '<br>'));
        } catch (e) {
            typing.remove();
            addMsg('Бот', 'Сеть недоступна');
        }
    }

    form?.addEventListener('submit', (e) => {
        e.preventDefault();
        const txt = (input?.value || '').trim();
        if (!txt) return;
        addMsg('Вы', txt);
        input.value = '';
        sendMessage(txt);
    });

    btn?.addEventListener('click', () => {
        panel?.classList.toggle('open');
        if (panel?.classList.contains('open')) loadHistory();
    });
    closeBtn?.addEventListener('click', () => panel?.classList.remove('open'));
})();
