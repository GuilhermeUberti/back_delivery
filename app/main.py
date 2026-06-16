from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.auth.router import router as auth_router
from app.bot.router import router as bot_router
from app.orders.router import router as orders_router
from app.menu.router import router as menu_router
from app.customers.router import router as customers_router
from app.analytics.router import router as analytics_router
from app.settings.router import router as settings_router

app = FastAPI(title="ZaPedido API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(bot_router, prefix="/bot", tags=["bot"])
app.include_router(orders_router, prefix="/orders", tags=["orders"])
app.include_router(menu_router, prefix="/menu", tags=["menu"])
app.include_router(customers_router, prefix="/customers", tags=["customers"])
app.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
app.include_router(settings_router, prefix="/settings", tags=["settings"])


@app.get("/health")
async def health():
    return {"status": "ok"}
