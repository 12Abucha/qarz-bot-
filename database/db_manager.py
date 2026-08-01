# database/db_manager.py
import sqlite3
import os
from datetime import datetime, timedelta

class DebtBotDatabase:
    def __init__(self, db_name="database/debt_system.db"):
        # Papka mavjud bo'lmasa, yaratamiz
        os.makedirs(os.path.dirname(db_name), exist_ok=True)
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # 1. DO'KONLAR JADVALI
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS shops (
                shop_id INTEGER PRIMARY KEY,
                shop_name TEXT,
                owner_phone TEXT,
                card_number TEXT,
                subscription_end DATE,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # 2. QARZDORLAR JADVALI
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS debtors (
                debtor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id INTEGER,                    
                debtor_name TEXT,                   
                debtor_phone TEXT,                  
                total_debt REAL DEFAULT 0.0,        
                last_reminded_date DATE,            
                return_date DATE,                   
                is_blacklisted BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
            )
        ''')
        self.conn.commit()

    def add_shop(self, shop_id, shop_name, owner_phone, sub_days=30):
        # ⏱️ Sanani Python'ning o'zida aniq hisoblaymiz (Baza qotib qolmasligi uchun)
        future_date = datetime.now() + timedelta(days=sub_days)
        sub_end_str = future_date.strftime('%Y-%m-%d')
        
        self.cursor.execute('''
            INSERT OR REPLACE INTO shops (shop_id, shop_name, owner_phone, subscription_end, is_active)
            VALUES (?, ?, ?, ?, TRUE)
        ''', (shop_id, shop_name, owner_phone, sub_end_str))
        self.conn.commit()