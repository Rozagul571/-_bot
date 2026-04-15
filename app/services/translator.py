"""
translator.py — Professional post + to'g'ri manba izohi
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
  [Ilgari qanday tartib bo'lganligi — 1-2.5 gap]

📋 Hozir qanday o'zgardi?
  [Yangi tartib, qoidalar, majburiyatlar — 2 gap]

  🔢 Qadam-baqadam jarayon:
  1. [Birinchi qadam]
  2. [Ikkinchi qadam]
  3. [Uchinchi qadam]
  (kerak bo'lsa davom ettir)

  ❓ Nima uchun bu qoida kiritildi?
  [Davlat maqsadi va sababi — 2-1 gap]

  👥 Kim rioya qilishi shart?
  
  
  🗓 [Hujjat nomi va raqami] | Kuchga kirdi: [sana]

TIL QOIDALARI (MAJBURIY):
  Faqat sof o'zbek tili — birorta ruscha so'z bo'lmasin.
  TAQIQLANGAN: tender, zakupka, zakup, rejestr, portal, konkurs,
               operator, kontragent, yuridik shaxs, fizik shaxs,
               otbor, dokumentatsiya (o'rniga: hujjat).
  TO'G'RI: davlat xaridi, tanlov, ro'yxat, xizmat ko'rsatuvchi,
           buyurtmachi, yetkazib beruvchi, shartnoma, tashkilot, fuqaro.

QATTIQ TAQIQLAR:
  ✗ 1gz.uz — shu saytni nomini qo'yma boshqa foydaalanganiningni aniq qilib ishlaydiganini qo'yaver. 
  ✗ Post to'liq bo'lsin — oxirigacha yozilsin, kesmang
  [Aniq ro'yxat: tashkilotlar, mansabdorlar, fuqarolarprofessional va batafsil yoz (200–250 so'z).


QOIDALAR:
# - Agar postda raqamlari va yili bo'lsa shu malumotlara kelib chiqb  link sifatida o'zing foydalangan saytni ni yozib qo'y bu qonun qayerda chop etilganini user isbot sifatida ko'rishi kerak 
- Boshqa postlarda faqat post mazmuniga mos keladigan haqiqiy ishlaydigan link qo'y.
- Hech qachon 404 beradigan yoki mavzuga mos kelmaydigan link qo'yma.
- "Taqiqlandi", "to'xtatildi", "spravka" kabi so'zlarni o'zingdan qo'shma.

JAVOB — FAQAT SOF JSON:
{"is_relevant": true/false, "post": "to'liq tayyor post matni"}
"""


class Translator:
    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        provider = "Groq" if "groq" in base_url else "OpenAI"
        logger.info(f"Translator tayyor | {provider} | Model: {model}")

    async def process(
        self,
        telegram_text: str,
        link_content: Optional[str] = None,
        has_1gz_link: bool = False,
    ) -> PostResult:

#         hint = """
# """

        if link_content and len(link_content) > 150:
            user_content = (
                # f"TELEGRAM POST:{hint}\n\n"
                f"ASLIY MATN:\n{telegram_text[:1500]}\n\n"
                f"HUJJAT MATNI:\n{link_content[:3500]}"
            )
        else:
            user_content = f"TELEGRAM POST:ASLIY MATN:\n{telegram_text[:4000]}"

        for attempt in range(1, settings.MAX_RETRIES + 1):
            try:
                resp = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=0.3,
                    max_tokens=2200,
                    response_format={"type": "json_object"},
                )
                raw = resp.choices[0].message.content.strip()
                result = json.loads(raw)

                is_relevant = bool(result.get("is_relevant", False))
                post = str(result.get("post", "")).strip()

                if is_relevant and post:
                    post = _clean_post(post)

                return PostResult(is_relevant=is_relevant, post=post)

            except Exception as exc:
                logger.warning(f"AI urinish {attempt}: {exc}")
                if attempt < settings.MAX_RETRIES:
                    await asyncio.sleep(settings.RETRY_DELAY_SECONDS)

        return PostResult(is_relevant=False, post="")


def _clean_post(text: str) -> str:
    text = re.sub(r"https?://1gz\.uz\S*", "", text, flags=re.IGNORECASE)
    return re.sub(r"\n{3,}", "\n\n", text).strip()