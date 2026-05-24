import os
import asyncio
import json
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, LabeledPrice, PreCheckoutQuery,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

import database as db
from config import BOT_TOKEN, ADMIN_ID, WEBAPP_URL, STARS_PER_PACK, SLOTS_PER_PACK

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBAPP_URL}{WEBHOOK_PATH}"


# ─── Helpers ────────────────────────────────────────────────────────────────────

def main_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🎮 Open NickMint",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )
    )
    if telegram_id == ADMIN_ID:
        builder.row(
            InlineKeyboardButton(
                text="⚙️ Admin Panel",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/admin.html")
            )
        )
    return builder.as_markup()


# ─── /start ─────────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user = db.register_user(message.from_user.id, message.from_user.username)
    if user["is_banned"]:
        await message.answer("🚫 You are banned from NickMint.")
        return

    await message.answer(
        f"👋 Welcome to <b>NickMint</b>!\n\n"
        f"🎭 Create unique Telegram usernames\n"
        f"💫 Trade them on the marketplace\n"
        f"📦 Manage your inventory\n\n"
        f"Press the button below to open the app 👇",
        parse_mode="HTML",
        reply_markup=main_keyboard(message.from_user.id)
    )


# ─── Telegram Stars payment ──────────────────────────────────────────────────────

@dp.message(Command("buy_slots"))
async def cmd_buy_slots(message: types.Message):
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer("Please use /start first.")
        return

    slots = db.get_user_slots(message.from_user.id)
    max_extra = 50  # MAX_SLOTS - BASE_SLOTS
    if slots["extra"] >= max_extra:
        await message.answer("You already have the maximum number of slots (100)!")
        return

    await bot.send_invoice(
        chat_id=message.chat.id,
        title="📦 Expand Inventory",
        description=f"Add {SLOTS_PER_PACK} slots to your NickMint inventory",
        payload=f"slots_{message.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=f"+{SLOTS_PER_PACK} Slots", amount=STARS_PER_PACK)],
        provider_token="",
    )


@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    if payload.startswith("slots_"):
        db.add_stars(message.from_user.id, STARS_PER_PACK)
        result = db.expand_slots(message.from_user.id, STARS_PER_PACK)
        if result["ok"]:
            await message.answer(
                f"✅ Payment successful!\n"
                f"➕ Added {result['slots_added']} slots to your inventory.",
                reply_markup=main_keyboard(message.from_user.id)
            )
        else:
            await message.answer(f"Payment received but error: {result['reason']}")


# ─── Web App data handler ────────────────────────────────────────────────────────

@dp.message(F.web_app_data)
async def web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")
        user_id = message.from_user.id

        user = db.get_user(user_id)
        if not user:
            db.register_user(user_id, message.from_user.username)

        if action == "create_nickname":
            result = db.create_nickname(user_id)
            if result["ok"]:
                nick = result["nickname"]["nickname"]
                await message.answer(f"✅ Created: <b>{nick}</b>", parse_mode="HTML")
            else:
                await message.answer(f"❌ {result['reason']}")

        elif action == "buy_slots_stars":
            # Trigger invoice
            slots = db.get_user_slots(user_id)
            if slots["extra"] >= 50:
                await message.answer("Already at max slots!")
                return
            await bot.send_invoice(
                chat_id=message.chat.id,
                title="📦 Expand Inventory",
                description=f"Add {SLOTS_PER_PACK} slots to your NickMint inventory",
                payload=f"slots_{user_id}",
                currency="XTR",
                prices=[LabeledPrice(label=f"+{SLOTS_PER_PACK} Slots", amount=STARS_PER_PACK)],
                provider_token="",
            )

        elif action == "sell_nickname":
            nickname_id = data.get("nickname_id")
            price = data.get("price", 1)
            result = db.list_on_market(user_id, nickname_id, price)
            if result["ok"]:
                await message.answer(f"✅ Listed on market for {price} ⭐")
            else:
                await message.answer(f"❌ {result['reason']}")

        elif action == "delist_nickname":
            nickname_id = data.get("nickname_id")
            result = db.delist_from_market(user_id, nickname_id)
            if result["ok"]:
                await message.answer("✅ Removed from market")
            else:
                await message.answer(f"❌ {result['reason']}")

        elif action == "buy_nickname":
            market_id = data.get("market_id")
            result = db.buy_from_market(user_id, market_id)
            if result["ok"]:
                await message.answer(
                    f"✅ Purchased <b>{result['nickname']}</b> for {result['price']} ⭐",
                    parse_mode="HTML"
                )
            else:
                await message.answer(f"❌ {result['reason']}")

        elif action == "delete_nickname":
            nickname_id = data.get("nickname_id")
            result = db.delete_nickname(user_id, nickname_id)
            if result["ok"]:
                await message.answer("🗑 Nickname deleted")
            else:
                await message.answer(f"❌ {result['reason']}")

        # Admin actions
        elif action == "admin_ban" and user_id == ADMIN_ID:
            target_id = data.get("target_id")
            db.ban_user(target_id, True)
            await message.answer(f"✅ User {target_id} banned")

        elif action == "admin_unban" and user_id == ADMIN_ID:
            target_id = data.get("target_id")
            db.ban_user(target_id, False)
            await message.answer(f"✅ User {target_id} unbanned")

        elif action == "admin_add_stars" and user_id == ADMIN_ID:
            target_id = data.get("target_id")
            amount = data.get("amount", 0)
            db.add_stars(target_id, amount)
            await message.answer(f"✅ Added {amount} ⭐ to user {target_id}")

    except Exception as e:
        logger.error(f"WebApp data error: {e}")
        await message.answer("Something went wrong. Please try again.")


# ─── API endpoints for Web App ───────────────────────────────────────────────────

async def api_handler(request: web.Request) -> web.Response:
    """REST API for the Web App to fetch data."""
    path = request.path
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }

    if request.method == "OPTIONS":
        return web.Response(status=200, headers=headers)

    # Validate Telegram user from query param
    user_id_str = request.rel_url.query.get("user_id", "")
    try:
        user_id = int(user_id_str)
    except ValueError:
        return web.json_response({"error": "invalid user_id"}, status=400, headers=headers)

    if path == "/api/me":
        user = db.get_user(user_id)
        if not user:
            return web.json_response({"error": "not found"}, status=404, headers=headers)
        slots = db.get_user_slots(user_id)
        return web.json_response({**user, **slots}, headers=headers)

    elif path == "/api/inventory":
        nicks = db.get_user_nicknames(user_id)
        return web.json_response(nicks, headers=headers)

    elif path == "/api/market":
        listings = db.get_market_listings()
        return web.json_response(listings, headers=headers)

    elif path == "/api/admin/users" and user_id == ADMIN_ID:
        users = db.get_all_users()
        return web.json_response(users, headers=headers)

    return web.json_response({"error": "not found"}, status=404, headers=headers)


async def health_handler(request: web.Request) -> web.Response:
    return web.Response(text="NickMint bot is running ✅")


async def on_startup(app: web.Application):
    db.init_db()
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")


async def on_shutdown(app: web.Application):
    await bot.delete_webhook()


def create_app() -> web.Application:
    app = web.Application()

    # Static files
    app.router.add_static("/", path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "web"), name="static", show_index=True)

    # API routes
    app.router.add_route("*", "/api/{tail:.*}", api_handler)
    app.router.add_get("/health", health_handler)

    # Webhook
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=8080)