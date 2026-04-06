import asyncio
import re
from typing import Optional
from openai import AsyncOpenAI
from loguru import logger
from core.config import settings

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

_RELEVANCE_SYSTEM = (
    "Siz O'zbekiston davlat xaridlari va qonunchilik mutaxassisisiz.\n"
    "Faqat 'HA' yoki 'YOQ' deb javob bering.\n"
    "HA: davlat xaridlari, tender, qonun, farmon, qaror, normativ hujjat, "
    "shartnoma, soliq, tarif, byudjet, davlat xizmatlari, litsenziya, jarima.\n"
    "YOQ: reklama, sport, siyosat, shaxsiy hayot, ko'ngilochar kontent.\n"
    "Faqat bitta so'z yoz."
)

_POST_SYSTEM = (
    "Sen ikkita rolni birgalikda bajarasan:\n\n"
    "ROL 1 - Senior O'zbek Qonunshunos:\n"
    "  Qonun raqami, yil va kuchga kirish sanasini aniqla.\n"
    "  Kim uchun ta'sir qilishini batafsil yoz.\n"
    "  Amaliy oqibatlar, muddatlar, jarimalarni ko'rsat.\n\n"
    "ROL 2 - Senior Copywriter:\n"
    "  Murakkab qonuniy matnni oddiy, jonli, tushunarli tilga o'gir.\n"
    "  To'g'ridan-to'g'ri tarjima emas, tushuntirish yoz.\n"
    "  Hamma narsa shu postda bolsin, hech qayerga yonaltirma.\n\n"
    "TIL QOIDALARI (QATTIQ):\n"
    "  Faqat sof o'zbek tili, birorta ruscha soz ishlatma.\n"
    "  Taqiqlangan: tender, zakupka, zakup, rejestr, portal, konkurs,\n"
    "  operator, kontragent, yuridik shaxs, fizik shaxs.\n"
    "  To'g'ri: davlat xaridi, tanlov, royxat, xizmat korsatuvchi,\n"
    "  buyurtmachi, yetkazib beruvchi, shartnoma, tashkilot, fuqaro.\n\n"
    "FORMAT (majburiy):\n"
    "  emoji [Qisqa sarlavha]\n\n"
    "  [Yangilik nima - 2 gap]\n\n"
    "  [Kim uchun muhim - 2-3 gap]\n\n"
    "  [Nima ozgaradi, raqamlar, muddatlar - 2-3 gap]\n\n"
    "  [Nima qilish kerak - 1-2 gap]\n\n"
    "  [Qonun raqami va kuchga kirish sanasi]\n\n"
    "QATTIQ TAQIQLAR:\n"
    "  HECH QANDAY havola berma (sayt, manba, qollanma).\n"
    "  'Batafsil oqung', 'havolaga oting', 'qollanma bilan tanishing' dema.\n"
    "  Ruscha soz ishlatma.\n"
    "  Emoji: 2-3 ta (faqat emojidan biri: 📌 ⚡ ✅ ⚠️ 📋).\n"
    "  Uzunlik: 180-280 soz."
)

_WITH_LINK = (
    "TELEGRAM POST (manba ma'lumoti):\n{telegram_text}\n\n"
    "QO'SHIMCHA MA'LUMOT (link mazmuni — faqat o'zing uchun, postda ko'rsatma):\n"
    "{link_content}\n\n"
    "Yuqoridagi barcha ma'lumotdan foydalanib, O'zbek auditoriyasi uchun "
    "to'liq tushuntirilgan post yoz. Hamma kerakli ma'lumot postda bolsin. "
    "Hech qayerga yonaltirma, hech qanday havola qoshma.\n\n"
    "Faqat tayyor post matnini yoz:"
)

_NO_LINK = (
    "MATN:\n{text}\n\n"
    "Ushbu ma'lumot asosida O'zbek auditoriyasi uchun "
    "to'liq tushuntirilgan post yoz. Hamma kerakli ma'lumot postda bolsin. "
    "Hech qayerga yonaltirma.\n\n"
    "Faqat tayyor post matnini yoz:"
)


class Translator:
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile") -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
        self._model = model
        logger.info(f"Translator tayyor | Model: {model} | Groq API")

    async def is_relevant(self, text: str) -> bool:
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _RELEVANCE_SYSTEM},
                    {"role": "user",   "content": text[:800]},
                ],
                temperature=0.0,
                max_tokens=5,
            )
            answer = resp.choices[0].message.content.strip().upper()
            result = "HA" in answer
            logger.info(f"Relevantlik: {answer} -> {'TEGISHLI' if result else 'SKIP'}")
            return result
        except Exception as exc:
            logger.warning(f"Relevantlik xato: {exc} -- tegishli deb otiladi")
            return True

    async def create_post(self, telegram_text: str, link_content: Optional[str] = None) -> str:
        if link_content and len(link_content) > 150:
            prompt = _WITH_LINK.format(
                telegram_text=telegram_text[:1200],
                link_content=link_content[:2800],
            )
            logger.info("Post rejimi: telegram + link mazmuni (link postda yoq)")
        else:
            prompt = _NO_LINK.format(text=telegram_text[:3000])
            logger.info("Post rejimi: faqat telegram matni")

        for attempt in range(1, settings.MAX_RETRIES + 1):
            try:
                resp = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": _POST_SYSTEM},
                        {"role": "user",   "content": prompt},
                    ],
                    temperature=0.4,
                    max_tokens=1200,
                )
                result = resp.choices[0].message.content.strip()
                result = _remove_links(result)
                logger.info(f"Post yaratildi: {len(result)} belgi (urinish {attempt})")
                return result
            except Exception as exc:
                wait = settings.RETRY_DELAY_SECONDS * attempt
                logger.warning(f"Groq urinish {attempt}/{settings.MAX_RETRIES}: {exc} -- {wait}s")
                if attempt < settings.MAX_RETRIES:
                    await asyncio.sleep(wait)

        logger.error("Groq xato -- asl matn qaytarildi")
        return telegram_text


def _remove_links(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(
        r"(🔗|📎)?\s*(Batafsil|Manba|Havola|Ko'proq|Qo'shimcha)[:\s].*",
        "", text, flags=re.IGNORECASE | re.MULTILINE,
    )
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def extract_urls(text: str) -> list[str]:
    return re.compile(r"https?://[^\s\)\]\>\"\']+", re.I).findall(text)