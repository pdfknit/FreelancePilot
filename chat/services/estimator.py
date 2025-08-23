# chat/services/estimator.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import List


def _round_half(x: float | Decimal) -> float:
    """Округление к ближайшим 0.5 часа."""
    return float((Decimal(x) * 2).to_integral_value(rounding=ROUND_HALF_UP) / 2)


@dataclass
class Estimation:
    summary: str
    decomposition: List[str]
    risks: List[str]
    base_hours: float
    confidence: str  # 'L' | 'M' | 'H'
    est_hours_min: float
    est_hours_max: float
    est_cost: float


# Буферы по ТЗ (MVP)
CONFIDENCE_BUFFERS = {
    "H": 1.40,
    "M": 1.25,
    "L": 1.15,
}

# Простейшие правила (MVP) — на основе ключевых слов
KEYWORD_RULES = [
    # (список ключевых слов, базовые часы или добавка, replace_если_true)
    (["лендинг", "landing", "простая страница"], 8.0, True),
    (["админ", "dashboard", "админка"], 4.0, False),
    (["интеграция", "api", "вебхук", "webhook"], 3.0, False),
    (["аутентификация", "jwt", "oauth"], 2.0, False),
    (["postgres", "redis", "celery"], 2.0, False),
]


def _base_hours_from_keywords(text: str) -> float:
    """
    Базовая оценка часов по ключевым словам.
    Первое «replace» правило может задать базу, остальные — добавки.
    Если ничего не сработало — вернём разумный минимум 2.0 часа.
    """
    txt = (text or "").lower()

    base = None
    add = 0.0
    for words, hours, replace in KEYWORD_RULES:
        if any(w in txt for w in words):
            if replace and base is None:
                base = float(hours)
            else:
                add += float(hours)

    if base is None:
        base = 2.0  # дефолт для мелких задач
    return max(0.5, base + add)


def _build_decomposition(text: str) -> List[str]:
    steps = [
        "Сбор и уточнение требований",
        "Декомпозиция и план работ",
        "Реализация",
        "Тестирование и фикса багов",
        "Демо и финальные правки",
    ]
    # 2–6 подпунктов
    return steps[: max(2, min(6, len(steps)))]


def _build_risks(text: str) -> List[str]:
    risks = [
        "Неполные/неясные требования",
        "Интеграционные задержки/нестабильные API",
        "Неожиданные баги и переделки",
        "Смена приоритетов",
    ]
    # 2–4 риска
    return risks[:4]


def estimate(raw_text: str, hourly_rate: float | Decimal, confidence: str = "M") -> Estimation:
    """
    Главная точка входа (сохраняем имя функции для совместимости со всем проектом).
    Возвращает Estimation с диапазоном часов и расчётом стоимости.
    """
    # Валидация confidence
    conf = (confidence or "M").upper()
    if conf not in CONFIDENCE_BUFFERS:
        conf = "M"

    # Базовые часы по ключевым словам (MVP-правила)
    base_hours = _base_hours_from_keywords(raw_text)

    # Диапазон: min — 80% от базы, max — база * буфер
    hmin = _round_half(base_hours * 0.8)
    hmax = _round_half(base_hours * CONFIDENCE_BUFFERS[conf])
    if hmax < hmin:  # на всякий
        hmax = hmin

    # Стоимость = среднее часов × ставка
    rate = float(hourly_rate or 25)
    avg_hours = (hmin + hmax) / 2.0
    est_cost = float((Decimal(avg_hours) * Decimal(rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    return Estimation(
        summary=(raw_text or "").strip()[:200] + ("…" if raw_text and len(raw_text.strip()) > 200 else ""),
        decomposition=_build_decomposition(raw_text),
        risks=_build_risks(raw_text),
        base_hours=float(base_hours),
        confidence=conf,
        est_hours_min=float(hmin),
        est_hours_max=float(hmax),
        est_cost=est_cost,
    )
