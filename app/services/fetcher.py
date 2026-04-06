import re
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from loguru import logger

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}


async def fetch_url_content(url: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=15.0,
            follow_redirects=True, verify=False,
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            if "html" not in resp.headers.get("content-type", ""):
                return None
            text = _extract(resp.text)
            return text[:4000] if text and len(text) > 100 else None
    except Exception as exc:
        logger.warning(f"fetch_url xato: {exc}")
        return None


def _extract(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    main = (
        soup.find("article") or soup.find("main")
        or soup.find(class_=re.compile(r"content|article|text", re.I))
        or soup.body
    )
    if not main:
        return ""
    lines = [l.strip() for l in main.get_text("\n").splitlines() if len(l.strip()) > 20]
    return "\n".join(lines)