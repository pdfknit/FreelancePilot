# chat/services/estimator.py
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from django.conf import settings
from openai import OpenAI

# ------------------------- Константы / help -------------------------

HELP_TEXT = (
    "Команды:\n"
    "• /add <текст> — добавить задачу и оценить\n"
    "• /estimate <текст> — оценить без сохранения (потом спросит «добавить?»)\n"
    "• /start <id> — старт трекинга времени\n"
    "• /stop — стоп трекинга\n"
    "• /rate <число> — установить ставку €/ч\n"
    "• /report week — быстрый отчёт\n\n"
    "• /faq <вопрос> — задать ИИ свободный вопрос и получить короткий ответ\n\n"
    "Также можешь просто прислать описание задачи — я сразу предложу оценку с декомпозицией."
)

GREETING_WORDS = [
    "привет", "здравствуй", "здравствуйте", "добрый день", "доброе утро",
    "добрый вечер", "hello", "hi", "hey"
]
HELP_WORDS = ["/help", "помощь", "команды", "что ты умеешь", "как пользоваться"]

# Вопросы
HOURS_PATTERNS = [r"\bскольк[оа]\s+час", r"\bчас(ов|ы)?\b", r"\bдлительн", r"\bсрок\b"]
COST_PATTERNS = [r"\bскольк[оа]\s+стоит\b", r"\bстоимост", r"\bцена\b", r"\bпо деньгам\b"]
CONF_PATTERNS = [r"\bуверенн", r"\bconfidence\b"]
STEPS_PATTERNS = [r"\bдекомпозици", r"\bшаги\b", r"\bэтапы\b", r"\bплан\b"]
RISKS_PATTERNS = [r"\bриски\b"]
RATE_PATTERNS = [
    r"\bставк[аиуые]\b",  # "ставка", "ставки"...
    r"\brate\b",  # "rate"
    r"\bпочем\b",
    r"\bчасов(ая|ой)?\s+ставк[аи]\b",  # "часовая ставка"
    r"\bчасов(ой|ая)\s+рейт\b",  # "часовой рейт"
    r"\bhourly\s+rate\b",  # англ.
    r"\bскольк[оа]\s+стоит\s+час\b",  # "сколько стоит час ..."
    r"\bскольк[оа]\s+будет\s+стоит\s+час\b",
    r"\bстоимость\s+часа\b",  # "стоимость часа"
    r"\bцен[ау]\s+часа\b",  # "цена часа"
    r"\bчас\s+мо(ей|ей)\s+работы\b",  # "час моей работы"
]

RATE_STRONG_PATTERNS = [
    r"\bскольк[оа]\s+стоит\s+час\b",
    r"\bстоимость\s+часа\b",
    r"\bчасов(ая|ой)?\s+ставк[аи]\b",
    r"\bhourly\s+rate\b",
    r"\bчас\s+мо(ей|ей)\s+работы\b",
]

# Эвристики «это похоже на ТЗ/описание задачи»
TECH_HINTS = [
    "сверстать", "лендинг", "react", "django", "fastapi", "бот", "telegram", "aiogram",
    "python", "vue", "next.js", "docker", "api", "интеграция", "парсинг", "crm", "postgres",
    "figma", "макет", "верстка", "миграция", "деплой", "ssl", "websocket", "чаты", "drf"
]

_CONFIDENCE_MAP = {"low": "L", "medium": "M", "high": "H", "l": "L", "m": "M", "h": "H"}


# ------------------------- Модели данных -------------------------

@dataclass
class Estimation:
    summary: str
    steps: List[str]
    risks: List[str]
    est_hours_min: float
    est_hours_max: float
    confidence: str  # "L" | "M" | "H"
    hourly_rate_eur: float
    est_cost: float

    # Алиасы для совместимости/удобства
    @property
    def decomposition(self) -> List[str]:
        return self.steps

    @decomposition.setter
    def decomposition(self, value: List[str]):
        self.steps = value or []

    @property
    def base_hours(self) -> float:
        return round((float(self.est_hours_min) + float(self.est_hours_max)) / 2.0, 2)

    @property
    def hours_min(self) -> float:
        return self.est_hours_min

    @property
    def hours_max(self) -> float:
        return self.est_hours_max

    @property
    def hourly_rate(self) -> float:
        return self.hourly_rate_eur


@dataclass
class ChatReply:
    kind: Literal["help", "rate_answer", "estimation", "unknown", "hours", "cost", "confidence", "steps", "risks"]
    text: str
    estimation: Optional["Estimation"] = None


# ------------------------- Утилиты текста -------------------------

def _normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", (text or "")).strip().lower()
    return re.sub(r"\s+", " ", t)


def _match_any(patterns: List[str], text: str) -> bool:
    t = _normalize(text)
    return any(re.search(p, t) for p in patterns)


def _is_greeting(text: str) -> bool:
    t = _normalize(text)
    return any(w in t for w in GREETING_WORDS)


def _is_help_like(text: str) -> bool:
    t = _normalize(text)
    return any(w in t for w in HELP_WORDS) or t.startswith("/help")


def _is_rate_question(text: str) -> bool:
    return _match_any(RATE_PATTERNS, text)


def detect_question_kind(text: str) -> Optional[str]:
    t = _normalize(text)

    # сначала ловим "сильные" формулировки про ставку/цену часа
    if any(re.search(p, t) for p in RATE_STRONG_PATTERNS):
        return "rate_answer"

    # затем обычные упоминания ставки/рейта
    if any(re.search(p, t) for p in RATE_PATTERNS):
        return "rate_answer"

    # дальше уже остальные типы вопросов
    if _match_any(HOURS_PATTERNS, t):
        return "hours"
    if _match_any(COST_PATTERNS, t):
        return "cost"
    if _match_any(CONF_PATTERNS, t):
        return "confidence"
    if _match_any(STEPS_PATTERNS, t):
        return "steps"
    if _match_any(RISKS_PATTERNS, t):
        return "risks"
    return None


def _looks_like_project_description(text: str) -> bool:
    t = _normalize(text)
    if len(t) < 30:
        return False
    if any(h in t for h in TECH_HINTS):
        return True
    if re.search(r"\b(нужно|надо|сделать|реализовать|написать|собрать|сверстать|разработать)\b", t):
        return True
    if re.search(r"https?://|www\.|[a-z0-9-]+\.[a-z]{2,}", t):
        return True
    return False


# ------------------------- LLM взаимодействие -------------------------

def _extract_json(text: str) -> Dict[str, Any]:
    """
    Берём JSON либо целиком, либо из ```json ... ``` блока; отрезаем мусор до/после скобок.
    """
    s = (text or "").strip()
    fence = re.search(r"```json\s*(\{.*?\})\s*```", s, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        s = fence.group(1)
    first = s.find("{")
    last = s.rfind("}")
    if first != -1 and last != -1 and last > first:
        s = s[first:last + 1]
    try:
        return json.loads(s)
    except Exception:
        return {}


def _build_prompt(task_text: str, profile: Optional[Any], project: Optional[Any]) -> str:
    profession = getattr(profile, "profession", None) or "unknown"
    country = getattr(profile, "country", None) or "unknown"
    years = getattr(profile, "experience_years", None)
    seniority = getattr(profile, "seniority", None)
    base_rate = getattr(profile, "hourly_rate", None)
    client_type = getattr(project, "client_type", None) if project else None

    return "\n".join([
        "Ты — опытный проджект-лид/архитектор. Твоя задача — быстро и строго оценить трудозатраты.",
        "Верни ТОЛЬКО один JSON в формате:",
        """{
  "summary": "краткое описание",
  "steps": ["2–6 пунктов декомпозиции"],
  "risks": ["2–4 ключевых риска"],
  "hours_min": 1.5,
  "hours_max": 2.5,
  "confidence": "L|M|H",
  "hourly_rate_eur": 75.0
}""",
        "Правила:",
        "- hours_min/max — честная инженерная оценка; округляй к 0.5 (мин. 0.5 ч).",
        "- confidence: L (низкая), M (средняя), H (высокая).",
        "- hourly_rate_eur — ориентир рынка (налоги/накрутки не учитывать).",
        "",
        f"Профиль: profession={profession}, country={country}, years={years}, seniority={seniority}, user_base_rate={base_rate}",
        f"Тип клиента/проекта: {client_type or 'unknown'}",
        "",
        f'Текст задачи: """{task_text}"""'
    ])


def estimate(task_text: str, user_profile=None, project=None) -> Estimation:
    """
    Запрашиваем LLM, парсим JSON, считаем стоимость.
    Стоимость считаем по ставке пользователя (или DEFAULT_RATE).
    При любой ошибке возвращаем безопасную базовую оценку.
    """

    # База на случай сбоев LLM/сети
    def _safe_rate() -> float:
        try:
            r = float(getattr(user_profile, "hourly_rate", None) or settings.DEFAULT_RATE or 25.0)
        except Exception:
            r = float(getattr(settings, "DEFAULT_RATE", 25.0))
        return round(max(10.0, min(r, 300.0)))

    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        prompt = _build_prompt(task_text, user_profile, project)

        resp = client.chat.completions.create(
            model=getattr(settings, "LLM_MODEL", "gpt-4o-mini"),
            temperature=getattr(settings, "LLM_TEMPERATURE", 0.2),
            max_tokens=getattr(settings, "LLM_MAX_TOKENS", 700),
            messages=[
                {"role": "system", "content": "Ты — строгий калькулятор оценок задач и ставок. Отвечай только JSON."},
                {"role": "user", "content": prompt},
            ],
        )
        content = (resp.choices[0].message.content or "").strip()
        data = _extract_json(content)

        # Часы
        def _to_half(x):
            try:
                v = float(x)
            except Exception:
                v = 1.0
            return max(0.5, round(v * 2) / 2.0)

        hmin = _to_half(data.get("hours_min"))
        hmax = _to_half(data.get("hours_max"))
        if hmax < hmin:
            hmin, hmax = hmax, hmin

        # Итоги
        summary = str(data.get("summary", "")).strip() or "Оценка сформирована"
        steps = [s for s in (data.get("steps") or []) if isinstance(s, str)][:6]
        risks = [s for s in (data.get("risks") or []) if isinstance(s, str)][:4]
        confidence = _CONFIDENCE_MAP.get(str(data.get("confidence", "M")).lower(), "M")

        rate = _safe_rate()  # ставка пользователя/дефолт
        est_cost = round(((hmin + hmax) / 2.0) * rate, 2)

        return Estimation(
            summary=summary,
            steps=steps,
            risks=risks,
            est_hours_min=hmin,
            est_hours_max=hmax,
            confidence=confidence,
            hourly_rate_eur=rate,
            est_cost=est_cost,
        )

    except Exception:
        # Фолбэк: минимальная базовая оценка
        rate = _safe_rate()
        hmin, hmax = 1.0, 1.5
        return Estimation(
            summary="Оценка сформирована",
            steps=[],
            risks=[],
            est_hours_min=hmin,
            est_hours_max=hmax,
            confidence="M",
            hourly_rate_eur=rate,
            est_cost=round(((hmin + hmax) / 2.0) * rate, 2),
        )


# ------------------------- Ответы на обычный текст -------------------------
def faq_answer(question: str) -> str:
    """
    Прямой короткий ответ ИИ на произвольный вопрос.
    Никаких контекстов/ставок/профилей — только текст вопроса.
    """
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=getattr(settings, "LLM_MODEL", "gpt-4o-mini"),
            temperature=0.3,  # чуть творчествa, но коротко и по делу
            max_tokens=500,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Отвечай кратко и по делу. 2–4 предложения максимум. "
                        "Без преамбул и списков, говори конкретные диапазоны и факторы, если уместно."
                    ),
                },
                {"role": "user", "content": question.strip()},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or "Сложно ответить однозначно."
    except Exception:
        # не падаем наружу
        return "Сейчас не могу ответить на вопрос. Попробуйте немного позже."


def _answer_rate_text(user_profile=None) -> str:
    try:
        user_rate = float(getattr(user_profile, "hourly_rate", None) or settings.DEFAULT_RATE or 25.0)
    except Exception:
        user_rate = float(getattr(settings, "DEFAULT_RATE", 25.0))
    user_rate = round(max(10.0, min(user_rate, 300.0)))
    return (
        f"Текущая ставка (цена часа): {user_rate} €/ч.\n"
        f"Изменить: /rate <число> (например, /rate 35)."
    )


def answer_with_estimation(kind: str, est: "Estimation") -> str:
    if kind == "rate_answer":
        return f"Ставка: {est.hourly_rate_eur} €/ч."
    if kind == "hours":
        return f"Часы: {est.est_hours_min}–{est.est_hours_max} ч (среднее {est.base_hours})."
    if kind == "cost":
        return f"Стоимость ≈ {est.est_cost} € при ставке {est.hourly_rate_eur} €/ч."
    if kind == "confidence":
        return f"Уверенность: {est.confidence}."
    if kind == "steps":
        return "Декомпозиция:\n- " + "\n- ".join(est.steps or []) if est.steps else "Декомпозиция пока пустая."
    if kind == "risks":
        return "Риски:\n- " + "\n- ".join(est.risks or []) if est.risks else "Риски не выявлены."
    return est.summary


def handle_free_text(
        text: str,
        user_profile=None,
        project=None,
        last_estimation: Optional["Estimation"] = None,
) -> ChatReply:
    """
    Логика:
    1) привет/помощь → HELP
    2) вопрос (ставка/часы/стоимость/уверенность/шаги/риски)
       - если есть last_estimation → короткий ответ по ней
       - если текста хватает для оценки → считаем и отвечаем
       - иначе: для ставки скажем текущую ставку пользователя, для остального — попросим описать задачу
    3) описание задачи → сразу оценка
    4) остальное → HELP
    """
    if not (text or "").strip():
        return ChatReply(kind="help", text=HELP_TEXT)

    if _is_help_like(text) or _is_greeting(text):
        return ChatReply(kind="help", text=f"Привет! 👋\n\n{HELP_TEXT}")

    qkind = detect_question_kind(text)
    if qkind:
        if last_estimation:
            return ChatReply(kind=qkind, text=answer_with_estimation(qkind, last_estimation))
        if qkind == "rate_answer":
            return ChatReply(kind="rate_answer", text=_answer_rate_text(user_profile))
        if _looks_like_project_description(text):
            est = estimate(task_text=text, user_profile=user_profile, project=project)
            return ChatReply(kind=qkind, text=answer_with_estimation(qkind, est), estimation=est)
        return ChatReply(kind="unknown", text="Нужен контекст задачи. Опиши задачу или отправь: estimate <описание>.")

    if _looks_like_project_description(text):
        est = estimate(task_text=text, user_profile=user_profile, project=project)
        msg = (
            f"Оценка задачи:\n"
            f"• {est.summary}\n"
            f"• Часы: {est.est_hours_min}–{est.est_hours_max} ч (среднее {est.base_hours})\n"
            f"• Уверенность: {est.confidence}\n"
            f"• Ставка: {est.hourly_rate_eur} €/ч\n"
            f"• Стоимость: ≈ {est.est_cost} €\n\n"
            f"Создать задачу и запустить трекинг?"
        )
        return ChatReply(kind="estimation", text=msg, estimation=est)

    return ChatReply(kind="help", text=HELP_TEXT)
