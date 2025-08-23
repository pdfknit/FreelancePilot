document.addEventListener('DOMContentLoaded', () => {
    const log = document.getElementById('chat-log');
    const form = document.getElementById('chat-form');
    const input = document.getElementById('chat-input');
    const submitBtn = form.querySelector('button[type="submit"]');
    if (!log || !form || !input || !submitBtn) return;

    //история
    const add = (who, html) => {
        const div = document.createElement('div');
        div.className = 'msg';
        div.innerHTML = `<b>${who}:</b> ${html}`;
        log.appendChild(div);
        log.scrollTop = log.scrollHeight;
    };


    fetch('/api/chat/history/?limit=50')
        .then(async r => {
            if (!r.ok) throw new Error(r.status);
            return r.json();
        })
        .then(data => {
            log.innerHTML = '';
            (data.messages || []).forEach(m => {
                add(m.role === 'user' ? 'Вы' : 'Бот', m.text);
            });
        })
        .catch(() => add('Бот', 'Не удалось загрузить историю'));

    // отправка сообщения
    const csrftoken = document.cookie.split('; ').find(r => r.startsWith('csrftoken='))?.split('=')[1];


    const addTyping = () => {
        const div = document.createElement('div');
        div.className = 'msg';
        div.innerHTML = `<b>Бот:</b> <span class="dotpulse"><span></span><span></span><span></span></span>`;
        log.appendChild(div);
        log.scrollTop = log.scrollHeight;
        return div;
    };

    const removeNode = (el) => el?.parentNode?.removeChild(el);


    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        add('Вы', text);
        input.value = '';
        input.focus();
        submitBtn.disabled = true;
        const typing = addTyping();

        try {
            const r = await fetch('/api/chat/message/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrftoken},
                body: JSON.stringify({message: text, channel: 'page'})
            });
            if (r.status === 403) {
                removeNode(typing);
                add('Бот', 'Нужен вход: <a href="/accounts/login/">войти</a> или <a href="/accounts/signup/">зарегистрироваться</a>');
                submitBtn.disabled = false;
                return;
            }
            const data = await r.json();
            removeNode(typing);
            add('Бот', data.reply ? data.reply : '(нет ответа)');
        } catch (err) {
            removeNode(typing);
            add('Бот', '<span style="color:#DC2626">Ошибка сети. Попробуйте ещё раз.</span>');
        } finally {
            submitBtn.disabled = false;
        }
    });
});


