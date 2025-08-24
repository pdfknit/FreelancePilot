function getCookie(name) {
  const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return m ? m.pop() : '';
}

document.addEventListener('DOMContentLoaded', () => {
  const forms = document.querySelectorAll('.status-form');

  forms.forEach(f => {
    const sel = f.querySelector('select[name="status"]');

    sel?.addEventListener('change', async () => {
      const tr = f.closest('tr');
      const badge = tr?.querySelector('.status-badge');

      // Выбранные значение/метка до отправки
      const newValue = sel.value;
      const newLabel = sel.options[sel.selectedIndex]?.text || newValue;

      const fd = new FormData(f);

      try {
        const r = await fetch(f.action, {
          method: 'POST',
          body: fd,
          credentials: 'same-origin',
          headers: { 'X-CSRFToken': getCookie('csrftoken') }, // на всякий случай
        });
        if (!r.ok) throw new Error(await r.text());

        // Обновляем бэйдж и классы строки по новому статусу
        if (badge) {
          badge.textContent = newLabel;
          // сброс классов status-*
          badge.className = 'badge status-badge';
          badge.classList.add('status-' + newValue);
        }
        if (tr) {
          tr.className = 'task-row';
          tr.classList.add('status-' + newValue, 'saved');
          setTimeout(() => tr.classList.remove('saved'), 600);
        }
      } catch (e) {
        alert('Не удалось сменить статус');
      }
    });
  });
});
