# handlers/admin.py
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import config
from database.db_manager import DebtBotDatabase

admin_router = Router()
db = DebtBotDatabase()

# 📝 Do'kon qo'shish bosqichlarini belgilab olamiz
class AddShopStates(StatesGroup):
    waiting_for_id = State()
    waiting_for_name = State()
    waiting_for_phone = State()

# Super-Admin boshqaruv tugmalari
def get_admin_keyboard():
    kb = [
        [KeyboardButton(text="🏬 Do'konlarni ko'rish"), KeyboardButton(text="➕ Yangi do'kon qo'shish")],
        [KeyboardButton(text="📊 Umumiy statistika")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# /admin buyrug'i yoki menyu
@admin_router.message(Command("admin"))
async def admin_menu(message: Message):
    if message.from_user.id != config.SUPER_ADMIN_ID:
        await message.answer("Siz bu buyruqdan foydalana olmaysiz!")
        return
    await message.answer("⚙️ <b>Super-Admin Panel:</b>", reply_markup=get_admin_keyboard())

# 1. Tizimdagi hamma do'konlarni ko'rish
@admin_router.message(F.text == "🏬 Do'konlarni ko'rish")
async def view_shops(message: Message):
    if message.from_user.id != config.SUPER_ADMIN_ID:
        return

    db.cursor.execute("SELECT shop_id, shop_name, subscription_end, is_active FROM shops")
    shops = db.cursor.fetchall()

    if not shops:
        await message.answer("Tizimda hali birorta ham do'kon yo'q.")
        return

    text = "<b>🏬 Tizimdagi do'konlar:</b>\n\n"
    for shop in shops:
        status = "✅ Faol" if shop[3] else "❌ Bloklangan"
        text += f"🏢 <b>Nomi:</b> {shop[1]}\n🆔 ID: <code>{shop[0]}</code>\n📅 Muddat: {shop[2]}\nStatus: {status}\n\n"
    await message.answer(text)

# 2. Yangi do'kon qo'shishni boshlash
@admin_router.message(F.text == "➕ Yangi do'kon qo'shish")
async def start_add_shop(message: Message, state: FSMContext):
    if message.from_user.id != config.SUPER_ADMIN_ID:
        return
    
    await state.set_state(AddShopStates.waiting_for_id)
    await message.answer(
        "📝 Yangi do'kon qo'shish jarayoni boshlandi.\n\n"
        "1️⃣ Do'kon egasining <b>Telegram ID</b> raqamini yuboring:",
        reply_markup=ReplyKeyboardRemove() # Vaqtincha eski tugmalarni yopib turamiz
    )

# 3. ID qabul qilish va Nomi so'rash
@admin_router.message(AddShopStates.waiting_for_id)
async def process_shop_id(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Iltimos, faqat raqamlardan iborat Telegram ID yuboring:")
        return
        
    await state.update_data(shop_id=int(message.text))
    await state.set_state(AddShopStates.waiting_for_name)
    await message.answer("2️⃣ Endi <b>Do'kon nomini</b> kiriting (Masalan: <i>Maroqand Kafe</i> yoki <i>E-Max Do'koni</i>):")

# 4. Nomi qabul qilish va Telefon so'rash
@admin_router.message(AddShopStates.waiting_for_name)
async def process_shop_name(message: Message, state: FSMContext):
    await state.update_data(shop_name=message.text)
    await state.set_state(AddShopStates.waiting_for_phone)
    await message.answer("3️⃣ Oxirgi qadam, do'kon egasining <b>Telefon raqamini</b> kiriting:")

# 5. Telefonni qabul qilib, bazaga saqlash
@admin_router.message(AddShopStates.waiting_for_phone)
async def process_shop_phone(message: Message, state: FSMContext):
    await state.update_data(owner_phone=message.text)
    
    # Hamma yig'ilgan ma'lumotlarni bitta joyga olamiz
    user_data = await state.get_data()
    
    # Bazaga qo'shamiz (Standart 30 kunlik obuna bilan)
    db.add_shop(
        shop_id=user_data['shop_id'],
        shop_name=user_data['shop_name'],
        owner_phone=user_data['owner_phone'],
        sub_days=30
    )
    
    # Holatni tozalaymiz
    await state.clear()
    
    await message.answer(
        f"🎉 <b>Muvaffaqiyatli qo'shildi!</b>\n\n"
        f"🏢 Do'kon: {user_data['shop_name']}\n"
        f"🆔 ID: {user_data['shop_id']}\n"
        f"📅 Obuna: 30 kunga faollashtirildi.",
        reply_markup=get_admin_keyboard() # Admin menyusini qaytaramiz
    )