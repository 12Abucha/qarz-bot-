from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
# Inline tugmalar uchun elementlar
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton 
from database.db_manager import DebtBotDatabase 

router = Router()

# FSM Holatlari
class DebtStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_amount = State()
    waiting_for_time = State() # Qarz qaytarish vaqti

# --- 1. VAQTNI QABUL QILISH VA BAZAGA SAQLASH ---
# --- 1. VAQTNI QABUL QILISH VA BAZAGA SAQLASH ---
@router.message(DebtStates.waiting_for_time)
async def process_return_time(message: types.Message, state: FSMContext, db: DebtBotDatabase):
    user_data = await state.get_data()
    shop_id = message.from_user.id
    
    # Xotiradan ma'lumotlarni xavfsiz olish
    debtor_name = user_data.get('name', user_data.get('debtor_name', '')).strip()
    debtor_phone = user_data.get('phone', user_data.get('debtor_phone', '')).strip()
    amount = float(user_data.get('amount', user_data.get('total_debt', 0.0)))
    
    # Kiritilgan vaqt matni
    return_date = message.text.strip() 
    
    try:
        # 🔍 SHU YERDA DUBLIKAT BOR-YO'QLIGINI TEKSHIRAMIZ
        # id bilan birga total_debt (avvalgi qarz) ni ham olamiz
        db.cursor.execute('''
            SELECT id, total_debt FROM debtors 
            WHERE shop_id = ? AND debtor_phone = ?
        ''', (shop_id, debtor_phone))
        existing_debtor = db.cursor.fetchone()

        # 🔄 Agar bazada bunday telefonli mijoz mavjud bo'lsa
        if existing_debtor:
            debt_id, old_debt = existing_debtor
            new_debt = old_debt + amount # Eski qarzga yangisini qo'shamiz
            
            # Bazani yangilaymiz (qarzni va qaytarish muddatini yangilaymiz)
            db.cursor.execute('''
                UPDATE debtors 
                SET total_debt = ?, return_date = ?
                WHERE id = ?
            ''', (new_debt, return_date, debt_id))
            db.conn.commit()
            
            await message.reply(
                f"♻️ **Mijoz bazada mavjud! Qarz summasi yangilandi.**\n\n"
                f"👤 **Mijoz:** {debtor_name}\n"
                f"📈 **Avvalgi qarz:** {old_debt:,.0f} so'm\n"
                f"➕ **Qo'shildi:** {amount:,.0f} so'm\n"
                f"💰 **Jami qarz:** {new_debt:,.0f} so'm\n"
                f"📅 **Yangi muddat:** {return_date}",
                parse_mode="Markdown"
            )
            await state.clear()
            return

        # --- Agar takrorlanish bo'lmasa, bazaga yangi qarzdor sifatida qo'shish ---
        db.cursor.execute('''
            INSERT INTO debtors (shop_id, debtor_name, debtor_phone, total_debt, return_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (shop_id, debtor_name, debtor_phone, amount, return_date))
        db.conn.commit()
        
        await message.reply(
            f"✅ **Qarz muvaffaqiyatli daftaringizga qo'shildi!**\n\n"
            f"💰 **Jami qarz:** {amount:,.0f} so'm",
            parse_mode="Markdown"
        )
        await state.clear()
        
    except Exception as e:
        await message.reply(f"❌ Xatolik yuz berdi: {e}")
        await state.clear()

# --- 2. QARZLAR RO'YXATINI CHIQARISH ---
@router.message(Command("qarzlar"))
async def list_debts(message: types.Message, db: DebtBotDatabase):
    shop_id = message.from_user.id
    active_debts = db.get_active_debts(shop_id)
    
    if not active_debts:
        await message.reply("🎉 Hozircha faol qarzdorlaringiz yo'q!")
        return

    await message.reply("📋 **Sizning qarzdorlaringiz ro'yxati:**")
    
    for debt in active_debts:
        debt_id, name, phone, total_debt, return_date = debt
        
        text = (
            f"👤 **Qarzdor:** {name}\n"
            f"📞 **Tel:** {phone}\n"
            f"💰 **Qarz:** {total_debt:,} so'm\n"
            f"📅 **Muddat:** {return_date}"
        )
        
        # Inline tugma yaratish
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ To'landi", callback_data=f"pay_{debt_id}")]
        ])
        
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")

# --- 3. TUGMA BOSILGANDA QARZNI O'CHIRISH (TO'LANDI QILISH) ---
@router.callback_query(F.data.startswith("pay_"))
async def pay_debt_callback(call: types.CallbackQuery, db: DebtBotDatabase):
    debt_id = int(call.data.split("_")[1])
    
    # db_manager dagi metodni chaqiramiz
    debt_info = db.update_debt_status(debt_id)
    
    if debt_info:
        name, current_debt = debt_info
        await call.answer("Qarz yopildi!", show_alert=False)
        await call.message.edit_text(
            text=f"✅ **Qarz yopildi!**\n\n👤 {name} qarzini to'liq to'ladi.",
            parse_mode="Markdown"
        )
    else:
        await call.answer("Qarz topilmadi!", show_alert=True)