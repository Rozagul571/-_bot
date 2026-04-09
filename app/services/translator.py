"""
translator.py — Bitta AI so'rovda:
  1. Post normativ-huquqiy hujjatga tegishlimi?
  2. Tegishli bo'lsa — to'liq, batafsil, professional o'zbek post yarat
"""

import asyncio
import json
import re
from typing import Optional, TypedDict

from openai import AsyncOpenAI
from loguru import logger
from core.config import settings


class PostResult(TypedDict):
    is_relevant: bool
    post: str


_SYSTEM = """\
Sen O'zbekiston qonunchilik va davlat xaridlari sohasidagi yurist va ekspertsan.

══════════════════════════════════════════════════
VAZIFA 1 — TEKSHIRUV
══════════════════════════════════════════════════

Post quyidagi kategoriyalardan biriga tegishlimi?

• Qonunlar (Oliy Majlis qabul qilgan)
• Prezident farmonlari (PF-raqam)
• Prezident qarorlari (PQ-raqam)
• Vazirlar Mahkamasi qarorlari
• Vazirlik buyruqlari va yo'riqnomalari
• Davlat xaridlari qoidalari va o'zgarishlari
• Soliq, tarif, to'lov, jarima o'zgarishlari
• Litsenziya, ruxsatnoma qoidalari
• 1gz.uz saytidan kelgan BARCHA hujjatlar

AGAR TEGISHLI BO'LSA — {"is_relevant": true, "post": "..."}
AGAR TEGISHLI BO'LMASA — {"is_relevant": false, "post": ""}

══════════════════════════════════════════════════
VAZIFA 2 — TO'LIQ BATAFSIL POST YARATISH
══════════════════════════════════════════════════

Sen hujjatni chuqur tahlil qilib, oddiy fuqaro ham, mutaxassis ham
tushunadigan professional Telegram post yozasan.

SARLAVHA QOIDASI:
  Sarlavha — hujjatning ASOSIY MAVZUSI bo'lsin.
  Hujjat raqami sarlavhada BO'LMASIN — faqat mazmun.
  NOTO'G'RI: "PF-259 ga o'zgarish kiritildi"
  TO'G'RI:   "Davlat xaridida jamoatchilik muhokamasi majburiy bo'ldi"
  TO'G'RI:   "Litsenziya olish tartibi soddalashtirildi"
  TO'G'RI:   "Soliq imtiyozlari bekor qilindi"

POST TUZILMASI (MAJBURIY, shu tartibda):

  🔥 [Diqqat tortadigan sarlavha — faqat mavzu, raqam yo'q]

  [Qanday yangilik joriy qilindi — 2-3 gap, oddiy til]

  ⚖️ Avval qanday edi?
  [Ilgari qanday tartib bo'lganligi — 2-3 gap]

  📋 Endi nima o'zgardi?
  [Yangi tartib, qoidalar, majburiyatlar — 3-4 gap]

  🔢 Qadam-baqadam jarayon:
  1. [Birinchi qadam]
  2. [Ikkinchi qadam]
  3. [Uchinchi qadam]
  (kerak bo'lsa davom ettir)

  ❓ Nima uchun bu qoida kiritildi?
  [Davlat maqsadi va sababi — 2-3 gap]

  👥 Kim rioya qilishi shart?
  [Aniq ro'yxat: tashkilotlar, mansabdorlar, fuqarolar]

  ⚠️ Buzilsa nima bo'ladi?
  [Jarima, oqibat, xavflar — 2-3 gap]

  💡 Amaliy maslahat:
  [Mutaxassislarga aniq ko'rsatma — 2-3 gap]

  📌 Xulosa:
  [Qisqa yakunlovchi fikr — 1-2 gap]

  🗓 [Hujjat nomi va raqami] | Kuchga kirdi: [sana]

TIL QOIDALARI (MAJBURIY):
  Faqat sof o'zbek tili — birorta ruscha so'z bo'lmasin.
  TAQIQLANGAN: tender, zakupka, zakup, rejestr, portal, konkurs,
               operator, kontragent, yuridik shaxs, fizik shaxs,
               otbor, dokumentatsiya (o'rniga: hujjat).
  TO'G'RI: davlat xaridi, tanlov, ro'yxat, xizmat ko'rsatuvchi,
           buyurtmachi, yetkazib beruvchi, shartnoma, tashkilot, fuqaro.

QATTIQ TAQIQLAR:
  ✗ Sayt nomi, URL, havola, 1gz.uz — hech qanday veb manzil qo'shma
  ✗ "Batafsil o'qing", "saytga o'ting", "hujjatga qarang" dema
  ✗ Sarlavhada hujjat raqami bo'lmasin
  ✗ Post to'liq bo'lsin — oxirigacha yozilsin, kesmang

UZUNLIK: 400-600 so'z (to'liq, batafsil yoz — kesmang)

JAVOB FORMATI — faqat sof JSON:
{"is_relevant": true/false, "post": "to'liq tayyor post matni"}\
"""


class Translator:
    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self._client  = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model   = model
        provider = "Groq" if "groq" in base_url else "OpenAI"
        logger.info(f"Translator tayyor | {provider} | Model: {model}")

    async def process(
        self,
        telegram_text: str,
        link_content: Optional[str] = None,
        has_1gz_link: bool = False,
    ) -> PostResult:
        hint = "\n[MUHIM: Bu 1gz.uz rasmiy hujjat — ALBATTA tegishli]" if has_1gz_link else ""

        if link_content and len(link_content) > 150:
            user_content = (
                f"TELEGRAM POST:{hint}\n{telegram_text[:1200]}\n\n"
                f"HUJJAT TO'LIQ MATNI (faqat ma'lumot uchun, postda ko'rsatma):\n"
                f"{link_content[:3000]}"
            )
        else:
            user_content = f"TELEGRAM POST:{hint}\n{telegram_text[:3000]}"

        for attempt in range(1, settings.MAX_RETRIES + 1):
            try:
                resp = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user",   "content": user_content},
                    ],
                    temperature=0.3,
                    max_tokens=2000,
                    response_format={"type": "json_object"},
                )
                raw    = resp.choices[0].message.content.strip()
                result = json.loads(raw)

                is_relevant = bool(result.get("is_relevant", False))
                post        = str(result.get("post", "")).strip()

                if is_relevant and post:
                    post = _remove_links(post)

                logger.info(
                    f"AI: tegishli={is_relevant} | "
                    f"{'post: ' + str(len(post)) + ' belgi' if is_relevant else 'skip'}"
                )
                return PostResult(is_relevant=is_relevant, post=post)

            except json.JSONDecodeError:
                raw_text = resp.choices[0].message.content if hasattr(resp, "choices") else ""
                if '"is_relevant": true' in raw_text:
                    return PostResult(is_relevant=True, post=telegram_text)
                return PostResult(is_relevant=False, post="")

            except Exception as exc:
                wait = settings.RETRY_DELAY_SECONDS * attempt
                logger.warning(f"AI urinish {attempt}/{settings.MAX_RETRIES}: {exc} — {wait}s")
                if attempt < settings.MAX_RETRIES:
                    await asyncio.sleep(wait)

        logger.error("AI barcha urinishlar xato")
        return PostResult(is_relevant=False, post="")


def _remove_links(text: str) -> str:
    """Postdan URL va havola qatorlarini tozalaydi."""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"1gz\.uz\S*", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"(🔗|📎)?\s*(Batafsil|Manba|Havola|Ko'proq|Sayt|To'liq)[:\s].*",
        "", text, flags=re.IGNORECASE | re.MULTILINE,
    )
    return re.sub(r"\n{3,}", "\n\n", text).strip()