from __future__ import annotations

import uuid

from django.conf import settings
from django.db.models import Q, Sum
from django.utils import timezone
from django.core.cache import cache
from openai import project
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import timedelta

from .auth.bot_key_permission import HasBotApiKey
from .models import MessageLog
from .serializers import MessageLogSerializer
from .utils import ensure_session_key

from tasks.models import Task, TimeEntry
from chat.services.estimator import estimate, faq_answer, handle_free_text


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
    permission_classes = [IsAuthenticated, HasBotApiKey]

    def post(self, request):
        sess = ensure_session_key(request)
        u = request.user if request.user.is_authenticated else None
        text = (request.data.get("message") or request.data.get("text") or "").strip()
        channel = request.data.get("channel") or "page"
        if not text:
            return Response({"error": "empty"}, status=400)

        # логируем вход
        MessageLog.objects.create(
            user=u, session_key=sess, channel=channel, role="user", text=text
        )

        low = text.lower()
        reply = None
        actions = None

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
        elif low.startswith("rate ") or low.startswith("/rate "):
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
        elif low.startswith("estimate ") or low.startswith("/estimate "):
            raw = text.split(" ", 1)[1]
            est = estimate(task_text=raw, user_profile=u, project=project if 'project' in locals() else None)

            est_dict = {
                "summary": est.summary,
                "decomposition": list(est.decomposition or []),
                "risks": list(est.risks or []),
                "base_hours": float(est.base_hours),
                "confidence": est.confidence,
                "est_hours_min": float(est.est_hours_min),
                "est_hours_max": float(est.est_hours_max),
                "est_cost": float(est.est_cost),
                "raw_text": raw,
            }
            # сохраняем pending в кэш по одноразовому id (15 минут)
            estimate_id = uuid.uuid4().hex
            pending = {
                "user_id": (request.user.id if request.user.is_authenticated else None),
                "est": est_dict,
                "raw_text": raw,
            }
            cache.set(f"pending_estimate:{estimate_id}", pending, 15 * 60)

            # inline-кнопки для Телеги (бот их покажет, если это поле придёт)
            actions = [
                {"type": "tg_inline", "text": "✅ Создать задачу", "callback": f"confirm|{estimate_id}|create"},
                {"type": "tg_inline", "text": "✖ Отмена", "callback": f"confirm|{estimate_id}|cancel"},
            ]
            reply = (
                f"Оценка задачи:\n"
                f"• {est.summary}\n"
                f"• Часы: {est.est_hours_min}-{est.est_hours_max} ч\n"
                f"• Уверенность: {est.confidence}\n"
                f"• Стоимость: {_fmt_money(est.est_cost)}\n\n"
                f"Создать задачу?"
            )
            return Response({
                "reply": reply,
                "actions": [
                    {"type": "tg_inline", "text": "✅ Создать задачу", "callback": f"confirm|{estimate_id}|create"},
                    {"type": "tg_inline", "text": "✖ Отмена", "callback": f"confirm|{estimate_id}|cancel"},
                ],
            })


        # YES/NO (используется после estimate)
        elif low in ("да", "yes", "y", "д"):
            pending = request.session.get('pending_estimate')
            if not pending:
                reply = "Нет ожидающей оценки. Сначала введите: estimate <текст>"
            else:
                t = _create_task(
                    _title_from_text(pending.get("raw_text", "")),
                    pending.get("raw_text", ""),
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

        elif low.startswith("add ") or low.startswith("/add "):

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
                        hmin = float(a)
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
                bits.append(f"Стоимость: {_fmt_money(cost)}")
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
                        allowed_labels = [lbl for _, lbl in getattr(Task, "STATUS", [])]
                        reply = "Недопустимый статус. Доступные: " + ", ".join(
                            allowed_labels or ["open", "in progress", "paused", "done"])

                    else:
                        try:
                            task = Task.objects.get(pk=task_id)
                            task.status = new_status
                            task.save(update_fields=["status"])
                            reply = f"Статус задачи #{task.id} обновлён на: {task.get_status_display()}"
                        except Task.DoesNotExist:
                            reply = f"Задача #{task_id} не найдена."





        # START TIMER
        elif low.startswith("start") or low.startswith("/start"):
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
        elif low.startswith("stop") or low.startswith("/stop"):
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
                    if hasattr(te, "stop"):
                        te.stop(timezone.now())
                    else:
                        te.stopped_at = timezone.now()
                        te.duration_sec = int((te.stopped_at - te.started_at).total_seconds())
                        te.save(update_fields=["stopped_at", "duration_sec"])

                    dur = int(te.duration_sec or 0)

                    h = round(dur / 3600, 2)
                    reply = f"Таймер остановлен. Длительность: {h} ч (задача #{te.task_id})."

        # REPORT
        elif low.startswith("report") or low.startswith("/report"):
            if not u or not u.is_authenticated:
                reply = "Нужна авторизация для отчётов."
            else:
                period = (low.split(" ", 1)[1] if " " in low else "week").strip()
                now = timezone.now()
                if period in ("week", "w"):
                    since = now - timedelta(days=7)
                    title = "за 7 дней"
                elif period in ("month", "m"):
                    since = now - timedelta(days=30)
                    title = "за 30 дней"
                else:
                    since = now - timedelta(days=7)
                    title = "за 7 дней"

                qs = TimeEntry.objects.filter(
                    user=u, stopped_at__isnull=False, started_at__gte=since
                )
                total_sec = qs.aggregate(total=Sum("duration_sec"))["total"] or 0
                hours = round(total_sec / 3600, 2)
                cost = round(hours * float(_get_rate(u)), 2)
                reply = f"Отчёт {title}: {hours} ч, {_fmt_money(cost)} у.е."
        # --- FAQ: прямой вопрос к ИИ без контекста ---
        elif low.startswith("/faq ") or low.startswith("faq "):
            question = text.split(" ", 1)[1].strip() if " " in text else ""
            if not question:
                reply = "Формат: /faq <вопрос>. Например: /faq Сколько просить в час мидлу Python 3 года?"
            else:
                reply = faq_answer(question)

            data = {"reply": reply, "kind": "faq"}
            MessageLog.objects.create(
                user=u, session_key=sess, channel=channel, role="assistant", text=reply
            )
            return Response(data, status=200)
        elif low.startswith("confirm "):
            parts = low.split()
            if len(parts) < 3:
                reply = "Неверный формат подтверждения."
                return Response({"reply": reply})

            _, est_id, action = parts[:3]
            key = f"pending_estimate:{est_id}"
            pending = cache.get(key)
            if not pending:
                return Response({"reply": "Оценка устарела. Сделайте /estimate ещё раз."})

            # безопасность: если pending помнит user_id — сверим
            if pending.get("user_id") and request.user.is_authenticated and request.user.id != pending["user_id"]:
                return Response({"reply": "Недостаточно прав для этого действия."}, status=403)

            if action == "cancel":
                cache.delete(key)
                return Response({"reply": "Отменено."})

            # action == create → создаём задачу из pending
            est = pending["est"]
            raw_text = pending.get("raw_text") or ""
            title = _title_from_text(raw_text)
            t = _create_task(
                title=title,
                raw_text=raw_text,
                estimate_dict=est,
            )
            cache.delete(key)
            return Response({
                "reply": f"Задача #{t.id} создана: {title} (план {est.get('est_hours_min')}-{est.get('est_hours_max')} ч)"})

        # текст свободный
        if not reply:
            # восстановим последнюю оценку при желании — можно добавить позже
            r = handle_free_text(text, user_profile=u, project=None)
            reply = r.text  # что напишем в лог и что увидит пользователь

            # базовый ответ для фронта
            data = {"reply": r.text, "kind": r.kind}

            # если это сразу получилась оценка — добавим поля и сохраним её в сессию
            if r.estimation:
                est = r.estimation
                data.update({
                    "summary": est.summary,
                    "decomposition": list(est.steps or []),
                    "risks": list(est.risks or []),
                    "hours_min": est.est_hours_min,
                    "hours_max": est.est_hours_max,
                    "base_hours": est.base_hours,
                    "confidence": est.confidence,
                    "hourly_rate": est.hourly_rate_eur,
                    "cost": est.est_cost,
                })
                # сохраним «последнюю оценку» для последующих вопросов
                request.session["last_estimation"] = {
                    "summary": est.summary,
                    "steps": list(est.steps or []),
                    "risks": list(est.risks or []),
                    "est_hours_min": float(est.est_hours_min),
                    "est_hours_max": float(est.est_hours_max),
                    "confidence": est.confidence,
                    "hourly_rate_eur": float(est.hourly_rate_eur),
                    "est_cost": float(est.est_cost),
                }
                request.session.modified = True
                # подготовим такие же кнопки для Телеги (и pending в кэше)
                est_dict = {
                    "summary": est.summary,
                    "decomposition": list(est.steps or []),
                    "risks": list(est.risks or []),
                    "base_hours": float(est.base_hours),
                    "confidence": est.confidence,
                    "est_hours_min": float(est.est_hours_min),
                    "est_hours_max": float(est.est_hours_max),
                    "est_cost": float(est.est_cost),
                    "raw_text": text,
                }
                estimate_id = uuid.uuid4().hex
                pending = {
                    "user_id": (request.user.id if request.user.is_authenticated else None),
                    "est": est_dict,
                    "raw_text": text,
                }
                cache.set(f"pending_estimate:{estimate_id}", pending, 15 * 60)

                actions = [
                    {"type": "tg_inline", "text": "✅ Создать задачу", "callback": f"confirm|{estimate_id}|create"},
                    {"type": "tg_inline", "text": "✖ Отмена", "callback": f"confirm|{estimate_id}|cancel"},
                ]
                data["actions"] = actions  # если actions есть
                return Response(data, status=200)


        else:
            data = {"reply": reply}

        if actions:
            data["actions"] = actions
        # лог исходящего
        MessageLog.objects.create(
            user=u, session_key=sess, channel=channel, role="assistant", text=reply
        )
        return Response(data, status=200)
