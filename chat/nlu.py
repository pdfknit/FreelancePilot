# chat/nlu.py
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional, Literal

IntentName = Literal[
    "HELP", "RATE_SET", "TASK_ADD", "ESTIMATE_TEXT", "ESTIMATE_ID",
    "TIME_START", "TIME_STOP", "REPORT_PERIOD", "REPORT_RANGE", "SMALLTALK"
]

@dataclass
class Intent:
    name: IntentName
    args: dict

# Компилируем часто используемые шаблоны (кириллица + латиница)
R_NUM = r"(\d+(?:[.,]\d+)?)"
R_ID  = r"(\d+)"
R_DATE = r"(\d{4}-\d{2}-\d{2})"

PATTERNS = [
    ("HELP",         re.compile(r"^(?:помощь|что (?:умеешь|можешь)|help|команды)\b", re.I)),
    ("RATE_SET",     re.compile(rf"(?:ставк[ауе]|rate)\s*{R_NUM}", re.I)),
    ("TIME_START",   re.compile(rf"(?:старт|запусти|начни).*(?:задач[уы]\s*#?|id\s*#?)\s*{R_ID}", re.I)),
    ("TIME_STOP",    re.compile(r"(?:стоп|останови|пауза)\b", re.I)),
    ("TASK_ADD",     re.compile(r"^(?:добавь|создай|add)\b(.+)$", re.I)),
    ("ESTIMATE_ID",  re.compile(rf"(?:оцени|estimate).*(?:задач[уы]\s*#?|id\s*#?)\s*{R_ID}", re.I)),
    ("ESTIMATE_TEXT",re.compile(r"^(?:оцени|estimate)\b(.+)$", re.I)),
    ("REPORT_PERIOD",re.compile(r"(?:отч[её]т|report).*\b(week|month|недел[ья]|месяц)\b", re.I)),
    ("REPORT_RANGE", re.compile(rf"(?:отч[её]т|report).*\b{R_DATE}\s*(?:-|до|to)\s*{R_DATE}\b", re.I)),
    ("SMALLTALK",    re.compile(r"^(?:привет|здравствуй|hi|hello|спасибо|ок|ага|да|нет)\b", re.I)),
]

def detect_intent(text: str) -> Optional[Intent]:
    t = (text or "").strip()
    if not t:
        return None
    for name, rx in PATTERNS:
        m = rx.search(t)
        if not m:
            continue
        if name == "RATE_SET":
            val = m.group(1).replace(",", ".")
            return Intent(name, {"rate": float(val)})
        if name == "TIME_START":
            return Intent(name, {"task_id": int(m.group(1))})
        if name == "TASK_ADD":
            return Intent(name, {"text": m.group(1).strip()})
        if name == "ESTIMATE_ID":
            return Intent(name, {"task_id": int(m.group(1))})
        if name == "ESTIMATE_TEXT":
            return Intent(name, {"text": m.group(1).strip()})
        if name == "REPORT_PERIOD":
            kw = m.group(1).lower()
            period = "week" if kw in ("week", "неделя", "неделю", "недели") else "month"
            return Intent(name, {"period": period})
        if name == "REPORT_RANGE":
            d1, d2 = m.group(1), m.group(2)
            return Intent(name, {"date_from": d1, "date_to": d2})
        if name == "SMALLTALK":
            return Intent(name, {})
        if name == "HELP":
            return Intent(name, {})
    return None
