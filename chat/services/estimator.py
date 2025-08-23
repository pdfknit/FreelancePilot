from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


def _round_half(x):
    return (Decimal(x) * 2).to_integral_value(rounding=ROUND_HALF_UP) / 2


@dataclass
class Estimation:
    summary: str
    decomposition: list[str]
    risks: list[str]
    base_hours: float
    confidence: str
    est_hours_min: float
    est_hours_max: float
    est_cost: float


def estimate(raw_text: str, hourly_rate: float | Decimal, confidence: str = 'M') -> Estimation:
    txt = (raw_text or '').lower()
    base = 2.0
    if any(k in txt for k in ['лендинг', 'landing', 'простая страница']): base = 8
    if any(k in txt for k in ['админ', 'dashboard']): base += 4
    if any(k in txt for k in ['интеграция', 'api']): base += 3

    buf = {'L': 1.15, 'M': 1.25, 'H': 1.40}.get(confidence, 1.25)
    hmin = float(_round_half(base * 0.8))
    hmax = float(_round_half(base * buf))
    avg = (hmin + hmax) / 2
    rate = float(hourly_rate or 25)
    cost = round(avg * rate, 2)

    deco = ['Сбор требований', 'Разбиение задач', 'Реализация', 'Тестирование', 'Демо/правки'][:5]
    risks = ['Неполные требования', 'Интеграционные задержки', 'Непредвидимые баги'][:3]

    return Estimation(
        summary='Черновая оценка по правилам MVP',
        decomposition=deco, risks=risks, base_hours=base, confidence=confidence,
        est_hours_min=hmin, est_hours_max=hmax, est_cost=cost
    )
