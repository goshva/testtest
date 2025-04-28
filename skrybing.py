import requests
import sqlite3
from datetime import datetime
import time
import json
import os

class SteamMarketMonitor:
    def __init__(self):
        self.config = self.load_config()
        self.items = self.config.get('items_to_track', [])
        self.check_interval = self.config.get('check_interval', 36)
        self.db_file = self.config.get('db_file', 'steam_prices.db')
        
        # Инициализация базы данных
        self.init_db()

    def load_config(self):
        """Загружаем конфигурацию из файла"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            default_config = {
                'items_to_track': [
                    'AK-47 | Redline (Field-Tested)',
                    'AWP | Asiimov (Field-Tested)'
                ],
                'check_interval': 3600,
                'db_file': 'steam_prices.db'
            }
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4)
            return default_config

    def init_db(self):
        """Инициализация базы данных SQLite"""
        self.conn = sqlite3.connect(self.db_file)
        self.cursor = self.conn.cursor()
        
        # Создаем таблицу если ее нет
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            price REAL NOT NULL,
            timestamp DATETIME NOT NULL,
            price_change REAL,
            UNIQUE(item_name, timestamp)
        )
        ''')
        
        # Создаем таблицу для последних цен
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS last_prices (
            item_name TEXT PRIMARY KEY,
            last_price REAL NOT NULL,
            last_update DATETIME NOT NULL
        )
        ''')
        
        self.conn.commit()

    def get_steam_market_price(self, item_name):
        """Получаем текущую цену предмета на Steam Market"""
        url = f"https://steamcommunity.com/market/priceoverview/?appid=730&currency=1&market_hash_name={item_name}"
        
        try:
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            data = response.json()
            
            if data.get('success') and 'lowest_price' in data:
                price = float(data['lowest_price'].replace('$', '').strip())
                return price
            return None
        except Exception as e:
            print(f"Ошибка при получении цены для {item_name}: {e}")
            return None

    def check_price_changes(self):
        """Проверяем изменения цен для всех предметов"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n{current_time} - Начинаем проверку цен...")
        
        for item in self.items:
            price = self.get_steam_market_price(item)
            if price is None:
                continue
                
            # Получаем последнюю цену из базы
            self.cursor.execute(
                'SELECT last_price FROM last_prices WHERE item_name = ?',
                (item,)
            )
            result = self.cursor.fetchone()
            previous_price = result[0] if result else None
            
            # Рассчитываем изменение цены
            price_change = None
            if previous_price is not None:
                price_change = price - previous_price
                print(
                    f"{item}: ${price:.2f} "
                    f"({price_change:+.2f} {'↑' if price_change >= 0 else '↓'})"
                )
            else:
                print(f"{item}: ${price:.2f} (новая запись)")
            
            # Записываем в историю
            self.cursor.execute('''
            INSERT OR IGNORE INTO price_history 
            (item_name, price, timestamp, price_change)
            VALUES (?, ?, ?, ?)
            ''', (item, price, current_time, price_change))
            
            # Обновляем последнюю цену
            self.cursor.execute('''
            INSERT OR REPLACE INTO last_prices 
            (item_name, last_price, last_update)
            VALUES (?, ?, ?)
            ''', (item, price, current_time))
            
            self.conn.commit()

    def get_price_history(self, item_name, limit=10):
        """Получаем историю цен для конкретного предмета"""
        self.cursor.execute('''
        SELECT item_name, price, timestamp, price_change 
        FROM price_history 
        WHERE item_name = ?
        ORDER BY timestamp DESC
        LIMIT ?
        ''', (item_name, limit))
        
        return self.cursor.fetchall()

    def export_to_csv(self, filename='steam_prices.csv'):
        """Экспорт данных в CSV файл"""
        try:
            self.cursor.execute('''
            SELECT item_name, price, timestamp, price_change 
            FROM price_history 
            ORDER BY timestamp DESC
            ''')
            
            import csv
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Item', 'Price', 'Timestamp', 'Price Change'])
                writer.writerows(self.cursor.fetchall())
            
            print(f"Данные экспортированы в {filename}")
        except Exception as e:
            print(f"Ошибка при экспорте в CSV: {e}")

    def run(self):
        """Запускаем мониторинг"""
        print("Steam Market Monitor (SQLite) запущен")
        print(f"Отслеживаем предметы: {', '.join(self.items)}")
        print(f"Интервал проверки: {self.check_interval} секунд")
        print(f"База данных: {self.db_file}")
        
        try:
            while True:
                self.check_price_changes()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            print("\nМониторинг остановлен")
            self.conn.close()

if __name__ == "__main__":
    monitor = SteamMarketMonitor()
    monitor.run()