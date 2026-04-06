import re
from loguru import logger

LEGAL_KEYWORDS = [
    "закон", "законодательство", "постановление", "приказ", "распоряжение",
    "решение", "регламент", "норматив", "положение", "изменени", "поправк",
    "введен", "вступает в силу", "утвержден", "опубликован", "государственн",
    "госзакупк", "тендер", "конкурс", "аукцион", "заявк", "поставщик",
    "заказчик", "контракт", "договор", "закупк", "электронн", "торги",
    "лот", "реестр", "портал", "нормативн", "правовой", "публичн",
    "бюджет", "субъект", "ценовой", "котировк", "тариф", "штраф",
    "лицензи", "разрешени",
]

NOISE_PATTERNS = [
    r"^\s*подпиш", r"^\s*реклам",
    r"^\s*@\w+\s*$", r"^\s*https?://\S+\s*$",
]


class ContentFilter:
    def is_relevant(self, text: str) -> bool:
        if not text:
            return False
        lower = text.lower()
        for p in NOISE_PATTERNS:
            if re.match(p, lower, re.IGNORECASE | re.MULTILINE):
                return False
        for kw in LEGAL_KEYWORDS:
            if kw in lower:
                logger.debug(f"Kalit so'z: '{kw}'")
                return True
        return False

    def is_russian(self, text: str) -> bool:
        if not text:
            return False
        alpha = [c for c in text if c.isalpha()]
        if not alpha:
            return False
        cyr = sum(1 for c in alpha if "\u0400" <= c <= "\u04ff")
        return (cyr / len(alpha)) >= 0.20