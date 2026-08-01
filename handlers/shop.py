from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db_manager import DebtBotDatabase
from datetime import datetime, timedelta

shop_router = Router()

class RegisterShopStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()

# Qarzdor qo'shish bosqichlari
class AddDebtorStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_amount = State()
    waiting_for_days = State() # Kunni so'rash

# 💳 Karta sozlash uchun yangilangan FSM bosqichlari
class SetupCardStates(StatesGroup):
    waiting_for_card_number = State() # Karta raqamini kutish
    waiting_for_card_owner = State()  # 🌟 Karta egasining ismini kutish bosqichi

def get_shop_keyboard():
    kb = [
        [KeyboardButton(text="➕ Yangi qarzdor qo'shish"), KeyboardButton(text="👥 Qarzdorlar ro'yxati")],
        [KeyboardButton(text="💳 Karta raqamni sozlash"), KeyboardButton(text="📊 Mening hisobim")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- RO'YXATDAN O'TISH QISMI ---
async def start_shop_registration(message: Message, state: FSMContext):
    await state.set_state(RegisterShopStates.waiting_for_name)
    await message.answer(
        "🚀 <b>Qarz Daftar tizimiga xush kelibsiz!</b>\n\n"
        "Sizga 🎁 <b>30 kunlik BEPUL sinov muddati</b> beriladi.\n"
        "Ro'yxatdan o'tish uchun, iltimos, <b>Do'koningiz nomini</b> kiriting:"
    )

@shop_router.message(RegisterShopStates.waiting_for_name)
async def process_shop_name(message: Message, state: FSMContext):
    await state.update_data(shop_name=message.text)
    await state.set_state(RegisterShopStates.waiting_for_phone)
    kb = [[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]]
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
    await message.answer("📞 Pastdagi tugmani bosib, <b>Telefon raqamingizni</b> yuboring:", reply_markup=markup)

@shop_router.message(RegisterShopStates.waiting_for_phone, F.contact)
async def process_shop_phone(message: Message, state: FSMContext, db: DebtBotDatabase):
    contact = message.contact
    user_data = await state.get_data()
    db.add_shop(
        shop_id=message.from_user.id,
        shop_name=user_data['shop_name'],
        owner_phone=contact.phone_number,
        sub_days=30
    )
    await state.clear()
    await message.answer(f"🎉 <b>Tabriklaymiz! Ro'yxatdan o'tdingiz.</b>", reply_markup=get_shop_keyboard())

# --- YANGI QARZDOR QO'SHISH (MUDDAT BILAN) ---
@shop_router.message(F.text == "➕ Yangi qarzdor qo'shish")
async def start_add_debtor(message: Message, state: FSMContext):
    await state.set_state(AddDebtorStates.waiting_for_name)
    await message.answer("👤 Qarzdorning <b>Ism va Familiyasini</b> kiriting:")

@shop_router.message(AddDebtorStates.waiting_for_name)
async def process_debtor_name(message: Message, state: FSMContext):
    await state.update_data(debtor_name=message.text)
    await state.set_state(AddDebtorStates.waiting_for_phone)
    await message.answer("📞 Qarzdorning <b>Telefon raqamini</b> kiriting (Masalan: +998901234567):")

@shop_router.message(AddDebtorStates.waiting_for_phone)
async def process_debtor_phone(message: Message, state: FSMContext):
    # Bu yerda bazaga ulanmaymiz, faqat raqamni tozalab xotiraga olamiz (Bot qotib qolmasligi uchun)
    clean_phone = message.text.replace(" ", "").strip()
    await state.update_data(debtor_phone=clean_phone)
    await state.set_state(AddDebtorStates.waiting_for_amount)
    await message.answer("💰 <b>Qarz summasini</b> kiriting (Faqat raqamda):")

@shop_router.message(AddDebtorStates.waiting_for_amount)
async def process_debtor_amount(message: Message, state: FSMContext):
    clean_amount = message.text.replace(" ", "")
    if not clean_amount.isdigit():
        await message.answer("⚠️ Iltimos qarz summasini faqat raqamda kiriting:")
        return
    await state.update_data(total_debt=float(clean_amount))
    
    await state.set_state(AddDebtorStates.waiting_for_days)
    await message.answer("⏱️ Qarz necha kunga berildi? (Faqat kun sonini kiriting, masalan: 10 yoki 30):")

# --- YANGI QARZDOR QO'SHISH (MUDDAT BILAN) ---
@shop_router.message(AddDebtorStates.waiting_for_days)
async def process_debtor_days(message: Message, state: FSMContext, db: DebtBotDatabase):
    if not message.text.isdigit():
        await message.answer("⚠️ Iltimos, kun sonini faqat raqamda kiriting (masalan: 10):")
        return
        
    days = int(message.text)
    user_data = await state.get_data()
    shop_id = message.from_user.id
    
    debtor_name = user_data['debtor_name'].strip()
    debtor_phone = user_data['debtor_phone']
    new_amount = float(user_data['total_debt'])

    # 🔍 Telefon raqam bo'yicha mijoz bazada bor-yo'qligini tekshiramiz
    db.cursor.execute('''
        SELECT total_debt FROM debtors 
        WHERE shop_id = ? AND debtor_phone = ?
    ''', (shop_id, debtor_phone))
    existing_debtor = db.cursor.fetchone()

    today = datetime.now()
    future_date = today + timedelta(days=days)
    return_date_str = future_date.strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')

    # ♻️ Agar bazada bunday telefon raqamli mijoz mavjud bo'lsa -> Qarzni yangilaymiz
    if existing_debtor:
        old_debt = existing_debtor[0]
        updated_debt = old_debt + new_amount

        db.cursor.execute('''
            UPDATE debtors 
            SET total_debt = ?, return_date = ?, last_reminded_date = ?
            WHERE shop_id = ? AND debtor_phone = ?
        ''', (updated_debt, return_date_str, today_str, shop_id, debtor_phone))
        db.conn.commit()
        
        await state.clear()
        await message.answer(
            f"♻️ <b>Mijoz bazada mavjud! Qarz summasi yangilandi.</b>\n\n"
            f"👤 Ismi: {debtor_name}\n"
            f"📈 Avvalgi qarz: {old_debt:,.0f} so'm\n"
            f"➕ Qo'shildi: {new_amount:,.0f} so'm\n"
            f"💰 <b>Jami qarz:</b> {updated_debt:,.0f} so'm\n"
            f"⏱️ Yangi qaytarish sanasi: <b>{return_date_str}</b>",
            reply_markup=get_shop_keyboard()
        )
        return

    # --- Agar takrorlanish bo'lmasa, bazaga yangi qarzdor sifatida qo'shamiz ---
    db.cursor.execute('''
        INSERT INTO debtors (shop_id, debtor_name, debtor_phone, total_debt, last_reminded_date, return_date)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (shop_id, debtor_name, debtor_phone, new_amount, today_str, return_date_str))
    db.conn.commit()
    
    await state.clear()
    await message.answer(
        f"✅ <b>Qarzdor ro'yxatga olindi!</b>\n\n"
        f"👤 Ismi: {debtor_name}\n"
        f"💰 Qarz: {int(new_amount):,} so'm\n"
        f"⏱️ Qaytarish sanasi: <b>{return_date_str}</b> ({days} kundan keyin)\n"
        f"⚡ Tizim avtomatik eslatishni boshlaydi.",
        reply_markup=get_shop_keyboard()
    )

# --- QARZDORLAR RO'YXATI ---
@shop_router.message(F.text == "👥 Qarzdorlar ro'yxati")
async def list_debtors(message: Message, db: DebtBotDatabase):
    shop_id = message.from_user.id
    db.cursor.execute("SELECT debtor_name, debtor_phone, total_debt, return_date FROM debtors WHERE shop_id = ?", (shop_id,))
    debtors = db.cursor.fetchall()
    
    if not debtors:
        await message.answer("Sizning do'koningizda hozircha qarzdorlar yo'q. 👍")
        return
        
    text = "<b>👥 Qarzdorlar ro'yxati va muddatlari:</b>\n\n"
    total_shop_debt = 0
    for idx, debtor in enumerate(debtors, 1):
        text += f"{idx}. 👤 <b>{debtor[0]}</b>\n   💰 Qarz: <b>{debtor[2]:,} so'm</b>\n   📅 To'lash muddati: {debtor[3]}\n\n"
        total_shop_debt += debtor[2]
        
    text += f"-----------------------\n📊 <b>Jami bozor qarz:</b> {total_shop_debt:,} so'm"
    await message.answer(text)

# --- 💳 KARTA SOZLASH INTEGRATSIYASI ---
@shop_router.message(F.text == "💳 Karta raqamni sozlash")
async def start_card_setup(message: Message, state: FSMContext):
    await state.set_state(SetupCardStates.waiting_for_card_number)
    await message.answer("💳 Plastik Karta raqamingizni kiriting:\n<i>Masalan: 8600123456789012</i>")

@shop_router.message(SetupCardStates.waiting_for_card_number)
async def process_card_number(message: Message, state: FSMContext):
    clean_card = message.text.replace(" ", "").strip()
    
    if not clean_card.isdigit() or len(clean_card) != 16:
        await message.answer("⚠️ Iltimos, 16 xonali to'g'ri karta raqamini kiriting:")
        return

    await state.update_data(card_number=clean_card)
    await state.set_state(SetupCardStates.waiting_for_card_owner)
    await message.answer("👤 Karta kimning nomida ekanligini kiriting (Ism va Familiya):\n<i>Masalan: Alijon Valiyev</i>")

@shop_router.message(SetupCardStates.waiting_for_card_owner)
async def process_card_owner(message: Message, state: FSMContext, db: DebtBotDatabase):
    card_owner = message.text.strip()
    user_data = await state.get_data()
    card_number = user_data['card_number']
    shop_id = message.from_user.id
    
    formatted_card = " ".join([card_number[i:i+4] for i in range(0, len(card_number), 4)])
    
    try:
        db.cursor.execute("UPDATE shops SET card_number = ?, card_owner = ? WHERE shop_id = ?", 
                          (formatted_card, card_owner, shop_id))
        db.conn.commit()
        
        await state.clear()
        await message.answer(
            f"✅ <b>Karta ma'lumotlari muvaffaqiyatli saqlandi!</b>\n\n"
            f"💳 Karta: `{formatted_card}`\n"
            f"👤 Egasi: <b>{card_owner}</b>", 
            reply_markup=get_shop_keyboard()
        )
    except Exception as e:
        await message.answer(f"❌ Saqlashda xatolik yuz berdi: {e}")
        await state.clear()

# --- HISOB MA'LUMOTLARI ---
@shop_router.message(F.text == "📊 Mening hisobim")
async def shop_account_info(message: Message, db: DebtBotDatabase):
    shop_id = message.from_user.id
    db.cursor.execute("SELECT shop_name, subscription_end, is_active, card_number, card_owner FROM shops WHERE shop_id = ?", (shop_id,))
    shop = db.cursor.fetchone()
    if shop:
        status = "🟢 Faol" if shop[2] else "🔴 Bloklangan"
        card_info = shop[3] if shop[3] else "Kiritilmagan"
        owner_info = shop[4] if shop[4] else "Kiritilmagan"
        
        await message.answer(
            f"🏬 <b>Do'kon:</b> {shop[0]}\n"
            f"📅 <b>Obuna:</b> {shop[1]}\n"
            f"⚡ <b>Holati:</b> {status}\n"
            f"-----------------------\n"
            f"💳 <b>Karta:</b> {card_info}\n"
            f"👤 <b>Egasi:</b> {owner_info}"
        )