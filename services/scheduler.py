from datetime import datetime
import sqlite3
import logging
from aiogram import Bot
from database.db_manager import DebtBotDatabase

async def check_and_remind_debts(bot: Bot, db_path: str = "database/debt_system.db"):
    # Bugungi sana (YYYY-MM-DD formatida)
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Bugun qaytarish muddati kelgan va qarzi 0 dan katta bo'lganlarni olamiz
    # last_reminded_date bugungi sana bo'lmasa (kuniga faqat 1 marta eslatish uchun)
    cursor.execute('''
        SELECT debtor_id, shop_id, debtor_name, total_debt, return_date 
        FROM debtors 
        WHERE return_date <= ? AND total_debt > 0.0 AND (last_reminded_date IS NULL OR last_reminded_date != ?)
    ''', (today_str, today_str))
    
    expired_debts = cursor.fetchall()
    
    for debt in expired_debts:
        debt_id, shop_id, name, total_debt, return_date = debt
        
        text = (
            f"⏰ **QARZ MUDDATI KELDI!**\n\n"
            f"👤 **Qarzdor:** {name}\n"
            f"💰 **Summa:** {total_debt:,} so'm\n"
            f"📅 **Muddat:** {return_date}\n\n"
            f"Ro'yxatni ko'rish va o'chirish uchun /qarzlar buyrug'ini bosing."
        )
        
        try:
            # Do'kon egasiga ogohlantirish yuboramiz
            await bot.send_message(chat_id=shop_id, text=text, parse_mode="Markdown")
            
            # Bugun eslatilganligini yozib qo'yamiz (baza qayta-qayta xabar yo'llamasligi uchun)
            cursor.execute('''
                UPDATE debtors 
                SET last_reminded_date = ? 
                WHERE debtor_id = ?
            ''', (today_str, debt_id))
            conn.commit()
            
        except Exception as e:
            logging.error(f"Eslatma yuborishda xatolik (Shop ID: {shop_id}): {e}")
            
    conn.close()