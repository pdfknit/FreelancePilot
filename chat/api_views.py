# chat/api_views.py
from __future__ import annotations

from decimal import Decimal
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MessageLog
from .serializers import MessageLogSerializer
from .utils import ensure_session_key

from tasks.models import Task, TimeEntry
from chat.services.estimator import estimate


def _get_rate(user):
    if user and hasattr(user, 'profile') and user.profile.hourly_rate:
        return user.profile.hourly_rate
    return getattr(settings, 'DEFAULT_RATE', 25)


def _fmt_money(x):
    return f"{float(x):.2f}"


def _title_from_text(text: str) -> str:
    return (text or "").strip().splitlines()[0][:80] or "Без названия"


def _create_task(
        title: str,
        raw_text: str,
        user,
        *,
        estimate_dict: dict | None = None,
        hmin: float | None = None,
        hmax: float | None = None,
        cost: float | None = None,
):
    """
    Создаёт задачу.
    - Если передан estimate_dict — заполняем поля оценкой ИИ.
    - Иначе используем ручные hmin/hmax/cost (что передано).
    НИКАКИХ вызовов ИИ внутри этой функции нет.
    """
    from tasks.models import Task

    t = Task.objects.create(title=title, raw_text=raw_text, status="open")

    if estimate_dict:
        t.summary = estimate_dict.get("summary", "")
        t.est_hours_min = estimate_dict.get("est_hours_min")
        t.est_hours_max = estimate_dict.get("est_hours_max")
        t.est_confidence = estimate_dict.get("confidence", "")
        t.est_cost = estimate_dict.get("est_cost")
    else:
        if hmin is not None:
            t.est_hours_min = hmin
        if hmax is not None:
            t.est_hours_max = hmax
        if cost is not None:
            t.est_cost = cost

    t.save()
    return t


def normalize_status(s: str) -> str | None:
    """Вернёт canonical ('open'|'in_progress'|'paused'|'done') или None."""
    if not s:
        return None
    key = " ".join(s.lower().strip().replace("_", " ").split())
    aliases = {
        "open": {"open", "открыта", "открыть", "новая", "new"},
        "in_progress": {"in progress", "in_progress", "progress", "в работе", "работа", "в процессе"},
        "paused": {"paused", "pause", "пауза", "приостановлена", "стоп"},
        "done": {"done", "completed", "готово", "сделано", "закрыта", "выполнено"},
    }
    for canon, names in aliases.items():
        if key in names:
            return canon
    return None


# -------- История чата --------
class ChatHistoryApi(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        sess = ensure_session_key(request)
        u = request.user if request.user.is_authenticated else None
        qs = (
            MessageLog.objects.filter(Q(user=u) | Q(session_key=sess))
            .filter(channel__in=["page", "widget"])
            .order_by("created_at")[:200]
        )
        return Response({"messages": MessageLogSerializer(qs, many=True).data})


# -------- Сообщения/команды --------
class ChatMessageApi(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        sess = ensure_session_key(request)
        u = request.user if request.user.is_authenticated else None
        text = (request.data.get("text") or "").strip()
        channel = request.data.get("channel") or "page"
        if not text:
            return Response({"error": "empty"}, status=400)

        # логируем вход
        MessageLog.objects.create(
            user=u, session_key=sess, channel=channel, role="user", text=text
        )

        low = text.lower()
        reply = None

        # HELP
        if low in ("команды", "help", "/help"):
            reply = (
                "Команды:\n"
                "• estimate <текст> — ИИ‑оценка без сохранения, затем вопрос «добавить?»\n"
                "• да / нет — подтвердить или отменить добавление после estimate\n"
                "• add Название, Время, Цена — создать задачу вручную (напр.: add Лендинг, 6-10, 250)\n"
                "• status <id> <status> — сменить статус задачи (например: status 5 done)\n"
                "• rate <число> — ставка, $/ч\n"
                "• start <task_id> — старт таймера по задаче (нужна авторизация)\n"
                "• stop — стоп активного таймера (нужна авторизация)\n"
                "• report week|month — отчёт по времени/стоимости (нужна авторизация)\n"
            )

        # RATE
        elif low.startswith("rate "):
            try:
                val = float(text.split(" ", 1)[1])
                if u and hasattr(u, "profile"):
                    u.profile.hourly_rate = val
                    u.profile.save(update_fields=["hourly_rate"])
                    reply = f"Ставка обновлена: {val}/ч"
                else:
                    reply = f"Ставка на сессию: {val}/ч (войдите, чтобы сохранить)"
            except Exception:
                reply = "Не удалось разобрать ставку. Пример: rate 25"

        # ESTIMATE (только подсказка, не создаёт задачу)
        # ESTIMATE (подсказка ИИ, потом спрашиваем подтвердить добавление)
        elif low.startswith("estimate "):
            raw = text.split(" ", 1)[1]
            est = estimate(raw_text=raw, hourly_rate=_get_rate(u))
            est_dict = {
                "summary": est.summary,
                "decomposition": est.decomposition,
                "risks": est.risks,
                "base_hours": est.base_hours,
                "confidence": est.confidence,
                "est_hours_min": est.est_hours_min,
                "est_hours_max": est.est_hours_max,
                "est_cost": est.est_cost,
                "raw_text": raw,
            }
            # сохраним в сессию «ожидается подтверждение»
            request.session['pending_estimate'] = est_dict
            request.session.modified = True

            reply = (
                    f"Summary: {est.summary}\n"
                    f"Диапазон: {est.est_hours_min}-{est.est_hours_max} ч (conf: {est.confidence})\n"
                    f"Стоимость: {_fmt_money(est.est_cost)}\n"
                    f"Декомпозиция: " + "; ".join(est.decomposition) + "\n"
                                                                       f"Риски: " + "; ".join(est.risks) + "\n\n"
                                                                                                           f"Добавить задачу с этой автооценкой? (да/нет)"
            )

        # CONFIRM YES/NO (используется после estimate)
        elif low in ("да", "yes", "y", "д"):
            pending = request.session.get('pending_estimate')
            if not pending:
                reply = "Нет ожидающей оценки. Сначала введите: estimate <текст>"
            else:
                title = _title_from_text(pending.get("raw_text", ""))
                t = _create_task(
                    _title_from_text(pending.get("raw_text", "")),
                    pending.get("raw_text", ""),
                    user=u,
                    estimate_dict=pending,
                )
                # очистим ожидание
                request.session['pending_estimate'] = None
                request.session.modified = True
                reply = (
                    f"Задача создана: #{t.id} — {t.title}\n"
                    f"Оценка: {t.est_hours_min}-{t.est_hours_max} ч (conf: {t.est_confidence})\n"
                    f"Стоимость: {_fmt_money(t.est_cost)}"
                )

        elif low in ("нет", "no", "n", "н"):
            if request.session.get('pending_estimate'):
                request.session['pending_estimate'] = None
                request.session.modified = True
                reply = "Ок, не создаю задачу."
            else:
                reply = "Нечего отменять."

        # ADD (ручное создание задачи)

        # ADD (просто "Название, Время, Цена")

        elif low.startswith("add "):

            payload = text.split(" ", 1)[1]
            parts = [p.strip() for p in payload.split(",")]
            title = parts[0] if len(parts) > 0 and parts[0] else "Без названия"
            hmin = hmax = cost = None

            # Время (второе поле): "6-10" или "8" (можно пусто)

            if len(parts) > 1 and parts[1]:
                p = parts[1]
                if "-" in p:
                    a, b = [s.strip() for s in p.split("-", 1)]
                    try:
                        hmin = float(a);
                        hmax = float(b)

                    except Exception:
                        hmin = hmax = None

                else:
                    try:
                        hmin = hmax = float(p)
                    except Exception:
                        hmin = hmax = None

            # Цена (третье поле): число (можно пусто)

            if len(parts) > 2 and parts[2]:
                try:
                    cost = float(parts[2])
                except Exception:
                    cost = None

            # создаём ТОЛЬКО руками, БЕЗ ИИ
            t = _create_task(
                title=title,
                raw_text=payload,
                user=u,
                hmin=hmin,
                hmax=hmax,
                cost=cost,
            )

            bits = [f"Задача создана: #{t.id} — {t.title}"]

            # время
            if hmin is not None and hmax is not None:
                bits.append(f"Оценка: {hmin}-{hmax} ч" if hmin != hmax else f"Оценка: {hmin} ч")
            else:
                bits.append("Оценка: —")

            # стоимость
            if cost is not None:
                bits.append(f"Стоимость: {cost:.2f}")
            else:
                bits.append("Стоимость: —")

            reply = "\n".join(bits)


        # STATUS / SET: status <id> <status>
        elif low.startswith("status ") or low.startswith("set "):
            parts = text.split()
            if len(parts) < 3:
                reply = "Формат: status <id> <status>. Примеры: status 12 done | status 7 \"в работе\""
            else:
                try:
                    task_id = int(parts[1])
                except ValueError:
                    reply = "ID должен быть числом. Пример: status 12 done"
                else:
                    status_text = " ".join(parts[2:])  # поддержка 'in progress' / 'в работе'
                    new_status = normalize_status(status_text)
                    if not new_status:
                        allowed = [lbl for _, lbl in Task.STATUS]
                        reply = "Недопустимый статус. Доступные: " + ", ".join(
                            allowed + ["open/in progress/paused/done"])
                    else:
                        try:
                            task = Task.objects.get(pk=task_id)
                            task.status = new_status
                            task.save(update_fields=["status"])
                            reply = f"Статус задачи #{task.id} обновлён на: {task.get_status_display()}"
                        except Task.DoesNotExist:
                            reply = f"Задача #{task_id} не найдена."





        # START TIMER
        elif low.startswith("start"):
            if not u or not u.is_authenticated:
                reply = "Нужна авторизация для учёта времени."
            else:
                parts = text.split()
                if len(parts) < 2 or not parts[1].isdigit():
                    reply = "Укажи ID задачи: start <task_id>"
                else:
                    task_id = int(parts[1])
                    try:
                        task = Task.objects.get(pk=task_id)
                        TimeEntry.objects.filter(
                            user=u, stopped_at__isnull=True
                        ).update(stopped_at=timezone.now())
                        TimeEntry.objects.create(
                            task=task, user=u, started_at=timezone.now()
                        )
                        reply = f"Таймер запущен для задачи #{task.id}."
                    except Task.DoesNotExist:
                        reply = f"Задача #{task_id} не найдена."

        # STOP TIMER
        elif low.startswith("stop"):
            if not u or not u.is_authenticated:
                reply = "Нужна авторизация для учёта времени."
            else:
                te = (
                    TimeEntry.objects.filter(user=u, stopped_at__isnull=True)
                    .order_by("-started_at")
                    .first()
                )
                if not te:
                    reply = "Нет активного таймера."
                else:
                    te.stop(timezone.now())
                    dur = int(te.duration_sec or 0)
                    h = round(dur / 3600, 2)
                    reply = f"Таймер остановлен. Длительность: {h} ч (задача #{te.task_id})."

        # REPORT
        elif low.startswith("report"):
            if not u or not u.is_authenticated:
                reply = "Нужна авторизация для отчётов."
            else:
                period = (low.split(" ", 1)[1] if " " in low else "week").strip()
                now = timezone.now()
                if period in ("week", "w"):
                    since = now - timezone.timedelta(days=7)
                    title = "за 7 дней"
                elif period in ("month", "m"):
                    since = now - timezone.timedelta(days=30)
                    title = "за 30 дней"
                else:
                    since = now - timezone.timedelta(days=7)
                    title = "за 7 дней"

                qs = TimeEntry.objects.filter(
                    user=u, stopped_at__isnull=False, started_at__gte=since
                )
                total_sec = sum(qs.values_list("duration_sec", flat=True) or [0])
                hours = round(total_sec / 3600, 2)
                cost = round(hours * float(_get_rate(u)), 2)
                reply = f"Отчёт {title}: {hours} ч, {_fmt_money(cost)} у.е."

        # FALLBACK
        if not reply:
            reply = f"Принято: {text}"

        # логируем исход
        MessageLog.objects.create(
            user=u, session_key=sess, channel=channel, role="assistant", text=reply
        )
        return Response({"reply": reply})
