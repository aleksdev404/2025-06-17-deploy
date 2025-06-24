import asyncio
import logging
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.app.database import Base, engine, SessionLocal
from backend.app.routes.auth import router as auth_router
from backend.app.routes.users import router as users_router
from backend.app.routes.films import router as films_router
from backend.app.routes.materials import router as materials_router
from backend.app.routes.rules import router as rules_router
from backend.app.routes.orders import router as orders_router
from backend.app.routes.stats import router as stats_router
from backend.app.security import admin_required
from backend.app import crud, telegram, models
from backend.app.services import insales


# ─────── Logging ───────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bg")

# ─────── Database ───────
Base.metadata.create_all(bind=engine)

# ─────── FastAPI ───────
app = FastAPI(title="Учёт материалов")

# rate-limit
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # в продакшне — ваш фронтенд
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────── Routers ───────
app.include_router(auth_router)                       # /auth/*
app.include_router(users_router, prefix="/api")     # /api/users
app.include_router(films_router, prefix="/api")     # /api/films
app.include_router(materials_router, prefix="/api")   # /api/materials

admin_deps = [Depends(admin_required)]
app.include_router(rules_router, prefix="/api", dependencies=admin_deps)
app.include_router(orders_router, prefix="/api", dependencies=admin_deps)
app.include_router(stats_router, prefix="/api", dependencies=admin_deps)


# Static files (SPA frontend)
app.mount("/", StaticFiles(directory="/app/frontend", html=True), name="frontend")

# ─────── Health ───────


@app.get("/api/health")
def health():
    return {"status": "ok"}

# ─────── Utils ───────


def cutoff_date() -> datetime:
    return datetime.utcnow() - timedelta(days=365)

# Low-stock alert helper


async def check_low_stock(db):
    for m in crud.list_materials(db):
        qty = crud._current_qty(db, m.id)
        if qty <= m.min_qty and not m.alerted:
            await telegram.low_stock(m.name, qty, m.min_qty)
            m.alerted = True
            db.commit()
        elif qty > m.min_qty and m.alerted:
            m.alerted = False
            db.commit()

# ID «складского» заказа готовых плёнок
READY_ORDER_ID = 109704738

# ─────── Background Fetch Loop ───────
# ─────── Background Fetch Loop ───────


@app.on_event("startup")
async def fetch_loop():
    async def loop():
        while True:
            db = SessionLocal()
            try:
                # ——— готовые плёнки (как было) ———
                ready = await insales.fetch_order_by_id(READY_ORDER_ID)
                if ready:
                    db.query(models.ReadyFilm).delete()
                    for ln in ready.get("order_lines", []):
                        db.add(models.ReadyFilm(
                            sku=ln.get("sku"),
                            title=ln.get("title"),
                            quantity=ln.get("quantity", 0),
                        ))
                    db.commit()

                ready_titles = {f.title for f in db.query(models.ReadyFilm)}

                # ——— для теста ———
                # ВСТАВЬ В НАЧАЛЕ ЦИКЛА
                # class FakeStatus:
                #     permalink = "novyy"

                # class FakeOrderLine:
                #     product_title = "Фейковый продукт"
                #     product_id = 1111
                #     quantity = 11

                # class FakeOrder:
                #     id = 999999
                #     created_at = '2025-06-22T23:31:27'
                #     customer = 'Aleksdev'
                #     ignored = False
                #     number = 999999
                #     custom_status = FakeStatus()
                #     lines = [FakeOrderLine()]
                #     source = "Тест"

                # ——— последние заказы ———
                # orders = [FakeOrder()]

                orders = await insales.fetch_orders(50)
                for o in orders:
                    if str(o.number) == str(READY_ORDER_ID):
                        continue

                    # upsert
                    db_order = crud.upsert_order(db, o)

                    # 1) Уведомление о «клиентском» заказе
                    if (
                        o.custom_status
                            and o.custom_status.permalink == "novyy"
                            and not db_order.client_notified
                    ):
                        logger.info("Пойман клиентский заказ %s, шлём уведомление", o.number)
                        await telegram.send(f"📞 Новый клиентский заказ #{o.number} от {o.customer} на сумму {o.total_price}")
                        db_order.client_notified = True
                        db.commit()

                    # 2) Уведомление о готовой плёнке (существующий код)
                    if not db_order.ready_notified:
                        hits = [ln.product_title for ln in o.lines if ln.product_title in ready_titles]
                        if hits:
                            channel = getattr(o, "source", "неизв.")
                            msg = f"✅ Готовая плёнка в заказе #{o.number} ({channel}): " + ", ".join(hits)
                            await telegram.send(msg)
                            db_order.ready_notified = True
                            db.commit()
                            logger.info("Отправлено уведомление по заказу %s", o.number)

                # 3) низкий остаток
                await check_low_stock(db)

            except Exception:
                logger.exception("Фоновый цикл упал")
            finally:
                db.close()

            await asyncio.sleep(60)

    asyncio.create_task(loop())


# ─────── Cleanup Old Movements ───────
@app.on_event("startup")
async def cleanup_old_moves():
    async def loop():
        while True:
            db = SessionLocal()
            try:
                db.query(models.StockMovement)\
                  .filter(models.StockMovement.created_at < cutoff_date())\
                  .delete()
                db.commit()
            finally:
                db.close()
            await asyncio.sleep(24 * 3600)  # раз в сутки
    asyncio.create_task(loop())
