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

    function addMsg(who, html, cls = '') {
        const div = document.createElement('div');
        div.className = 'fpw-msg';
        div.innerHTML = `<b>${who}:</b> <span class="${cls}">${html}</span>`;
        log.appendChild(div);
        log.scrollTop = log.scrollHeight;
    }

    function addTyping() {
        const div = document.createElement('div');
        div.className = 'fpw-msg';
        div.innerHTML = `<b>Бот:</b> <span class="dotpulse"><span></span><span></span><span></span></span>`;
        log.appendChild(div);
        log.scrollTop = log.scrollHeight;
        return div;
    }

    btn?.addEventListener('click', () => {
        panel.classList.toggle('open');
        if (panel.classList.contains('open')) input?.focus();
    });
    closeBtn?.addEventListener('click', () => panel.classList.remove('open'));

    // Закрытие Esc
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') panel.classList.remove('open');
    });

    // Отправка сообщения
    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const text = (input.value || '').trim();
        if (!text) return;
        addMsg('Вы', text);
        input.value = '';
        const typing = addTyping();
        try {
            const r = await fetch('/api/chat/message/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken()
                },
                body: JSON.stringify({message: text})
            });
            const data = await r.json();
            if (r.status === 403) {
                typing.remove();
                addMsg('Бот', 'Пожалуйста, авторизуйтесь: /accounts/login/', 'err');
                return;
            }

            typing.remove();
            addMsg('Бот', data.reply || '(нет ответа)');
        } catch (err) {
            typing.remove();
            addMsg('Бот', 'Ошибка сети. Попробуйте ещё раз.', 'err');
        }
    });
})();
