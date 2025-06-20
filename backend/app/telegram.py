import os
import httpx
import logging
import asyncio
from typing import List, Union

TOKEN       = os.getenv("TG_BOT_TOKEN")
STOCK_CHAT  = os.getenv("TG_CHAT_ID")                          # общий чат для остатков и пингов
FILM_CHAT   = os.getenv("TG_FILM_CHAT_ID")      # чат для плёнок
CLIENT_CHAT = os.getenv("TG_CLIENT_CHAT_ID")    # чат для клиентских заказов
log         = logging.getLogger("tg")


async def _post(text: str, chat_id: str):
    if not TOKEN:
        log.warning("TG_BOT_TOKEN not set; skipping send")
        return
    if not chat_id:
        log.warning("chat_id not set; skipping send")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            await cli.post(url, data=data)
    except httpx.HTTPError as e:
        log.error("Telegram send failed: %s", e)


async def send(text: str):
    """
    Роутинг по префиксу:
    ✅ — в FILM_CHAT
    📞 — в CLIENT_CHAT
    иначе — в STOCK_CHAT
    """
    if text.startswith("✅"):
        target = FILM_CHAT
    elif text.startswith("📞"):
        target = CLIENT_CHAT
    else:
        target = STOCK_CHAT

    await _post(text, target)


async def info(msg: str):
    """ℹ️ Информационное сообщение — всегда в общий чат."""
    await send(f"ℹ️ {msg}")


async def low_stock(name: str, q: Union[int, float], m: Union[int, float]):
    """⚠️ Уведомление об остатках (в общий чат)."""
    await send(f"⚠️ Остаток «{name}» достиг минимума ({q} ≤ {m})")


async def film_hit(order_no: Union[str, int], channel: str, titles: List[str]):
    """✅ Уведомление о готовой плёнке (в чат плёнок)."""
    msg = f"✅ Готовая плёнка в заказе #{order_no} ({channel}): " + ", ".join(titles)
    await send(msg)


# при старте шлём «пинг» в общий чат
asyncio.create_task(info("бот запущен – оповещения готовы"))
