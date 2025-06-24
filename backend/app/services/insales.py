import os
import datetime
import httpx
import asyncio
from typing import Union

from backend.app import schemas

INSALES_API_KEY = os.getenv("INSALES_API_KEY")
INSALES_API_PWD = os.getenv("INSALES_API_PWD")
INSALES_SHOP = os.getenv("INSALES_SHOP")
INSALES_API_URL = os.getenv("INSALES_API_URL") or f"https://{INSALES_SHOP}/admin"

TIMEOUT = httpx.Timeout(  # ⬅️  все четыре параметра!
    connect=5.0, read=40.0, write=10.0, pool=5.0
)
RETRIES = 3         # сколько раз пробуем
RETRY_PAUSE = 3       # секунд между попытками


async def fetch_orders(limit: int = 50) -> list[schemas.OrderOut]:
    """
    Тянем последние `limit` заказов, отдаём список моделей OrderOut.
    Пытаемся несколько раз прежде чем сдаться.
    """
    base = f"https://{INSALES_API_KEY}:{INSALES_API_PWD}@{INSALES_SHOP}/admin"

    last_exc: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            async with httpx.AsyncClient(base_url=base, timeout=TIMEOUT) as cli:
                resp = await cli.get(f"/orders.json?per_page={limit}")
                resp.raise_for_status()
                data = resp.json()
            break                                           # успех
        except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            last_exc = e  # noqa
            if attempt < RETRIES:
                await asyncio.sleep(RETRY_PAUSE)
                continue
            raise                                            # после N-й попытки – дальше наружу

    # ---- преобразуем в OrderOut, как раньше ----
    out: list[schemas.OrderOut] = []
    for it in data:
        # 1) собираем линии
        lines = [
            schemas.OrderLine(
                product_id=line["product_id"],
                product_title=line["title"],
                quantity=line["quantity"],
            )
            for line in it.get("order_lines", [])
        ]
        # 2) парсим дату
        created = datetime.datetime.fromisoformat(
            it["created_at"].replace("Z", "+00:00")
        )
        # 3) вынимаем кастомный статус (или None)
        cs = it.get("custom_status")

        out.append(
            schemas.OrderOut(
                id=it["id"],
                number=it["number"],
                customer=(it.get("client") or {}).get("full_name"),
                created_at=created,
                ignored=it.get("ignored", False),
                ready_notified=False,
                client_notified=False,
                custom_status=cs,
                lines=lines,
                total_price=it.get("total_price", 0)
            )
        )
    return out


async def fetch_order_by_id(order_id: Union[int, str]) -> dict:
    async with httpx.AsyncClient(base_url=INSALES_API_URL, auth=(INSALES_API_KEY, INSALES_API_PWD)) as cli:
        resp = await cli.get(f"/orders/{order_id}.json")
        resp.raise_for_status()
        payload = resp.json()
    return payload.get("order", {})
