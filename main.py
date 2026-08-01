# main.py
import os
import sys
import asyncio
import logging
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Loyiha yo'llarini sozlash
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from database.db_manager import DebtBotDatabase
from services.scheduler import check_and_remind_debts

# Routerlarni to'g'ri import qilish
from handlers.admin import admin_router, get_admin_keyboard
from handlers.shop import shop_router, start_shop_registration, get_shop_keyboard
from handlers.debtor import router as debtor_router 

# Logging sozlamalari
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Ma'lumotlar bazasi va Bot obyektlarini yaratish
db = DebtBotDatabase()
bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Hamma routerlarni bir joyda ketma-ket ulaymiz
dp.include_router(admin_router)
dp.include_router(shop_router)
dp.include_router(debtor_router)

@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    user_name = html.bold(message.from_user.full_name)
    
    # 1. Agar Super-Admin kirsa
    if user_id == config.SUPER_ADMIN_ID:
        await message.answer(
            f"Salom, Xo'jayin! {user_name} (Super-Admin) paneliga xush kelibsiz!\n"
            f"Boshqarish uchun pastdagi tugmalardan foydalaning:",
            reply_markup=get_admin_keyboard()
        )
        return

    # 2. Do'konchi tizimda bormi yoki yo'qligini tekshiramiz
    db.cursor.execute("SELECT is_active, subscription_end FROM shops WHERE shop_id = ?", (user_id,))
    shop = db.cursor.fetchone()

    if shop:
        is_active, sub_end = shop
        if is_active:
            # Do'kon faol, asosiy menyuni chiqaramiz
            await message.answer(
                f"Xush kelibsiz, do'kon egasi!\n📅 Obuna muddati: {sub_end} gacha faol.",
                reply_markup=get_shop_keyboard()
            )
        else:
            # Obuna tugab bloklangan bo'lsa
            await message.answer(
                "❌ <b>Botdan foydalanish muddatingiz tugagan!</b>\n\n"
                "Iltimos, tizimni qayta faollashtirish uchun to'lov qiling va Super-Admin bilan bog'laning."
            )
    else:
        # Tizimda yo'q bo'lsa, ro'yxatdan o'tishga yuboramiz
        await start_shop_registration(message, state)

async def main() -> None:
    print("---------------------------------------")
    print("LOYIHA: Qarz Daftar SaaS Tizimi ishga tushdi!")
    print("---------------------------------------")
    
    # 🛠️ Ma'lumotlar bazasini routerlar ichiga xavfsiz uzatish (Circular import yechimi)
    dp["db"] = db

    # Scheduler ishga tushirish (db argumenti qo'shildi)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_and_remind_debts, "interval", minutes=30, args=[bot, db])  #[cite: 2, 3]
    scheduler.start()
    
    # 🛠️ 1-Migratsiya: debtors jadvaliga return_date ustunini qo'shish
    try:
        db.cursor.execute("ALTER TABLE debtors ADD COLUMN return_date DATE;")
        db.conn.commit()
        print("Baza yangilandi: debtors -> return_date ustuni faol!")
    except Exception:
        pass

    # 🌟 2-Migratsiya: shops jadvaliga card_owner ustunini qo'shish
    try:
        db.cursor.execute("ALTER TABLE shops ADD COLUMN card_owner TEXT;")
        db.conn.commit()
        print("Baza yangilandi: shops -> card_owner ustuni qo'shildi!")
    except Exception:
        pass

    # Botni ishga tushirish
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())